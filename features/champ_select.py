"""Champion select auto-ban/auto-pick feature."""
import logging
import time
import threading
import random
from typing import Optional, Dict, Any, List, Set
from features.base_feature import BaseFeature
from features.champion_data import ChampionDataProvider
from features.champ_select_logic import (
    get_assigned_position,
    flatten_actions,
    find_my_action,
    get_banned_champions,
    get_picked_champions,
    get_teammate_intents,
    filter_available_champions,
    should_hover_during_planning
)

logger = logging.getLogger(__name__)


class ChampSelectFeature(BaseFeature):
    """Automatically ban and pick champions during champion select."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_client = None
        self.enabled = True  # Feature is always initialized, but auto_ban and auto_pick have their own flags
        
        # Config
        self.auto_ban_enabled = config.get('auto_ban_enabled', False)
        self.auto_pick_enabled = config.get('auto_pick_enabled', False)
        self.pick_mode = config.get('pick_mode', 'hover')  # 'hover' or 'lock'
        
        # Per-role champion preferences (stored as IDs)
        self.role_preferences = config.get('champ_select_preferences', {
            'default': {'bans': [], 'picks': []},
            'top': {'bans': [], 'picks': []},
            'jungle': {'bans': [], 'picks': []},
            'middle': {'bans': [], 'picks': []},
            'bottom': {'bans': [], 'picks': []},
            'utility': {'bans': [], 'picks': []}
        })
        
        # Random delays with backward compatibility
        # Ban delay range
        self.ban_delay_min = config.get('ban_delay_min_seconds', 
                                        config.get('auto_ban_delay_seconds', 1.0))
        self.ban_delay_max = config.get('ban_delay_max_seconds', 3.0)
        self._validate_delay_range('ban', self.ban_delay_min, self.ban_delay_max)
        
        # Pick delay range (replaces old lock_delay)
        self.pick_delay_min = config.get('pick_delay_min_seconds',
                                        config.get('auto_pick_delay_seconds', 
                                                  config.get('auto_lock_delay_seconds', 1.0)))
        self.pick_delay_max = config.get('pick_delay_max_seconds', 3.0)
        self._validate_delay_range('pick', self.pick_delay_min, self.pick_delay_max)
        
        # Safety margin (seconds to leave before timer expires)
        self.timer_safety_margin = 3.0
        
        # Test mode: when True, execute actions synchronously without delays
        self._test_mode = config.get('_test_mode', False)
        self._test_delay_override = None  # For tests to control delay
        
        # State tracking
        self.processed_actions = set()  # Track action IDs we've already processed
        self.champion_provider = ChampionDataProvider()
        self.champion_map = {}  # name -> id mapping
        self.champion_reverse_map = {}  # id -> name mapping
        self.last_session_state = None
        self.current_hover = None  # Track current hover to avoid duplicate hover calls
        self.pending_action_thread = None  # Track pending delayed action
        self.cancel_pending_action = threading.Event()  # Signal to cancel pending action
        self.action_completed = threading.Event()  # Signal that action completed (for tests)
    
    def initialize(self, event_bus, api_client):
        """Initialize the champion select feature."""
        self.api_client = api_client
        
        # Subscribe to champ select session events
        event_bus.subscribe('/lol-champ-select/v1/session', self._on_champ_select_event)
        
        # Load champion data
        self._load_champion_data()
        
        logger.info(
            f"Champion select feature initialized (auto_ban: {self.auto_ban_enabled}, "
            f"auto_pick: {self.auto_pick_enabled}, pick_mode: {self.pick_mode}, "
            f"ban_delay: {self.ban_delay_min}-{self.ban_delay_max}s, "
            f"pick_delay: {self.pick_delay_min}-{self.pick_delay_max}s)"
        )
    
    def get_name(self) -> str:
        return "Champion Select"
    
    def _validate_delay_range(self, name: str, min_val: float, max_val: float):
        """Validate delay range values."""
        if min_val < 0:
            logger.warning(f"{name} delay min ({min_val}) is negative, using 0")
            setattr(self, f'{name}_delay_min', 0.0)
        if max_val < 0:
            logger.warning(f"{name} delay max ({max_val}) is negative, using 0")
            setattr(self, f'{name}_delay_max', 0.0)
        if min_val > max_val:
            logger.warning(f"{name} delay min ({min_val}) > max ({max_val}), swapping")
            setattr(self, f'{name}_delay_min', max_val)
            setattr(self, f'{name}_delay_max', min_val)
    
    def _load_champion_data(self):
        """Load champion name<->ID mapping from client."""
        if not self.api_client:
            return
        
        try:
            # Get client's champion-summary first
            client_champions = []
            response = self.api_client.get('/lol-game-data/assets/v1/champion-summary.json')
            if response and isinstance(response, list):
                client_champions = response
                logger.info(f"Got {len(client_champions)} champions from client")
            
            # Fetch bilingual champion data
            champion_data = self.champion_provider.fetch_champion_data(client_champions)
            
            # Build legacy maps for compatibility
            for champ_id, champ_info in champion_data.items():
                name_en = champ_info.get('name_en', '')
                if name_en:
                    self.champion_map[name_en.lower()] = champ_id
                    self.champion_reverse_map[champ_id] = name_en
            
            logger.info(f"Loaded {len(champion_data)} champions with bilingual support")
            
        except Exception as e:
            logger.warning(f"Failed to load champion data: {e}")
    
    def _on_champ_select_event(self, uri: str, event_data: dict):
        """Handle champion select session events."""
        try:
            event_type = event_data.get('eventType', '')
            data = event_data.get('data')
            
            # Handle null data (champ select ended)
            if data is None:
                logger.debug(f"Champion select ended (null data, eventType={event_type})")
                self._cancel_pending_actions()
                self.processed_actions.clear()
                self.current_hover = None
                return
            
            # Process the session
            self._process_session(data)
            
        except Exception as e:
            logger.error(f"Error handling champ select event: {e}", exc_info=True)
    
    def _cancel_pending_actions(self):
        """Cancel any pending delayed actions."""
        self.cancel_pending_action.set()
        if self.pending_action_thread and self.pending_action_thread.is_alive():
            logger.debug("Canceling pending action")
            self.pending_action_thread.join(timeout=0.5)
        self.cancel_pending_action.clear()
    
    def _get_time_left(self, session: Dict[str, Any]) -> Optional[float]:
        """Get adjusted time left in phase from session timer (in seconds)."""
        timer = session.get('timer', {})
        if not timer:
            return None
        
        adjusted_time_ms = timer.get('adjustedTimeLeftInPhase')
        if adjusted_time_ms is None or adjusted_time_ms < 0:
            return None
        
        return adjusted_time_ms / 1000.0  # Convert ms to seconds
    
    def _calculate_safe_delay(self, session: Dict[str, Any], min_delay: float, max_delay: float) -> float:
        """
        Calculate a safe random delay that won't exceed the timer.
        
        Args:
            session: Champion select session
            min_delay: Minimum delay (seconds)
            max_delay: Maximum delay (seconds)
            
        Returns:
            Safe delay in seconds (may be capped)
        """
        # Test mode override
        if self._test_delay_override is not None:
            return self._test_delay_override
        
        # In test mode with no override, use zero delay
        if self._test_mode:
            return 0.0
        
        # Generate random delay in range
        delay = random.uniform(min_delay, max_delay)
        
        # Check timer
        time_left = self._get_time_left(session)
        if time_left is not None:
            # Cap delay to leave safety margin
            max_safe_delay = max(0, time_left - self.timer_safety_margin)
            if delay > max_safe_delay:
                logger.debug(f"Capping delay {delay:.1f}s to {max_safe_delay:.1f}s (time_left: {time_left:.1f}s)")
                delay = max_safe_delay
        
        return delay
    
    def _get_current_session(self) -> Optional[Dict[str, Any]]:
        """Re-fetch current champion select session."""
        if not self.api_client:
            return None
        
        try:
            response = self.api_client.get('/lol-champ-select/v1/session')
            return response if response else None
        except Exception as e:
            logger.debug(f"Failed to fetch current session: {e}")
            return None
    
    def _process_session(self, session: Dict[str, Any]):
        """Process champion select session and take actions."""
        if not session:
            return
        
        # Get local player cell ID
        local_player_cell_id = session.get('localPlayerCellId')
        if local_player_cell_id is None:
            return
        
        # Find current action
        my_action = find_my_action(session, local_player_cell_id)
        
        # If no action, check for PLANNING phase hover
        if not my_action:
            if self.auto_pick_enabled and should_hover_during_planning(session):
                self._handle_planning_hover(session, local_player_cell_id)
            return
        
        # Get action details
        action_id = my_action.get('id')
        action_type = my_action.get('type')  # 'ban' or 'pick'
        
        # Check if already processed
        if action_id in self.processed_actions:
            return
        
        # Process based on type
        if action_type == 'ban' and self.auto_ban_enabled:
            self._handle_ban_action(session, my_action, local_player_cell_id)
        elif action_type == 'pick' and self.auto_pick_enabled:
            self._handle_pick_action(session, my_action, local_player_cell_id)
    
    def _handle_planning_hover(self, session: Dict[str, Any], local_player_cell_id: int):
        """Hover top pick during PLANNING phase with delay."""
        # Cancel any existing pending action
        self._cancel_pending_actions()
        
        # Mark as processing to prevent duplicate handling
        planning_key = 'planning_hover'
        if planning_key in self.processed_actions:
            return
        self.processed_actions.add(planning_key)
        
        # In test mode, execute synchronously
        if self._test_mode:
            self._execute_planning_hover(session, local_player_cell_id)
            self.action_completed.set()
        else:
            # Start delayed action in background thread
            self.action_completed.clear()
            self.pending_action_thread = threading.Thread(
                target=self._execute_planning_hover_wrapper,
                args=(session, local_player_cell_id),
                daemon=True
            )
            self.pending_action_thread.start()
    
    def _execute_planning_hover_wrapper(self, session: Dict[str, Any], local_player_cell_id: int):
        """Wrapper to signal completion."""
        try:
            self._execute_planning_hover(session, local_player_cell_id)
        finally:
            self.action_completed.set()
    
    def _execute_planning_hover(self, session: Dict[str, Any], local_player_cell_id: int):
        """Execute planning phase hover after delay."""
        try:
            position = get_assigned_position(session, local_player_cell_id)
            role_to_use = position if position else 'default'
            
            preferences = self.role_preferences.get(role_to_use, {})
            pick_candidates = preferences.get('picks', [])
            
            # Fall back to default if role list is empty
            if not pick_candidates and role_to_use != 'default':
                logger.info(f"No picks for {role_to_use}, falling back to default")
                role_to_use = 'default'
                preferences = self.role_preferences.get('default', {})
                pick_candidates = preferences.get('picks', [])
            
            if not pick_candidates:
                return
            
            # Get available picks
            pickable_ids = self._get_pickable_champions()
            banned = get_banned_champions(session)
            picked = get_picked_champions(session)
            teammate_intents = get_teammate_intents(session, local_player_cell_id)
            
            available = filter_available_champions(
                pick_candidates,
                pickable_ids,
                set(),  # No bannable IDs for picks
                'pick',
                banned,
                picked,
                teammate_intents
            )
            
            if not available:
                return
            
            champ_id = available[0]
            champ_name = self.champion_provider.get_display_name(champ_id)
            
            # Calculate safe delay
            delay = self._calculate_safe_delay(session, self.pick_delay_min, self.pick_delay_max)
            
            # In test mode, execute immediately without delay
            if self._test_mode:
                logger.debug(f"PLANNING hover: test mode, hovering {champ_name} immediately")
            elif delay <= 0:
                logger.info("PLANNING hover: no time left for delay")
                return
            else:
                logger.info(f"PLANNING hover: waiting {delay:.1f}s before hovering {champ_name}")
                
                # Wait with cancellation check
                if self.cancel_pending_action.wait(delay):
                    logger.debug("PLANNING hover cancelled")
                    return
            
            # Re-fetch session and validate
            current_session = self._get_current_session()
            if not current_session:
                logger.debug("PLANNING hover: session ended during delay")
                return
            
            # Check still in PLANNING phase
            if not should_hover_during_planning(current_session):
                logger.debug("PLANNING hover: no longer in PLANNING phase")
                return
            
            # Re-select candidates (may have changed)
            pickable_ids = self._get_pickable_champions()
            banned = get_banned_champions(current_session)
            picked = get_picked_champions(current_session)
            teammate_intents = get_teammate_intents(current_session, local_player_cell_id)
            
            available = filter_available_champions(
                pick_candidates,
                pickable_ids,
                set(),
                'pick',
                banned,
                picked,
                teammate_intents
            )
            
            if available and available[0] != self.current_hover:
                champ_id = available[0]
                champ_name = self.champion_provider.get_display_name(champ_id)
                logger.info(f"PLANNING phase: hovering {champ_name} (assigned role: {position or 'none'}, using {role_to_use.capitalize()} list)")
                
                # Hover via any pick action
                actions = flatten_actions(current_session)
                for action in actions:
                    if action.get('type') == 'pick':
                        self._patch_action(action['id'], champ_id, completed=False)
                        self.current_hover = champ_id
                        break
        except Exception as e:
            logger.error(f"Error in planning hover: {e}", exc_info=True)
    
    def _handle_ban_action(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Handle ban action with delay."""
        action_id = action['id']
        
        # Check if already processed
        if action_id in self.processed_actions:
            return
        
        # Mark as processing
        self.processed_actions.add(action_id)
        
        # Cancel any existing pending action
        self._cancel_pending_actions()
        
        # In test mode, execute synchronously
        if self._test_mode:
            self._execute_ban_action(session, action, local_player_cell_id)
            self.action_completed.set()
        else:
            # Start delayed action in background thread
            self.action_completed.clear()
            self.pending_action_thread = threading.Thread(
                target=self._execute_ban_action_wrapper,
                args=(session, action, local_player_cell_id),
                daemon=True
            )
            self.pending_action_thread.start()
    
    def _execute_ban_action_wrapper(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Wrapper to signal completion."""
        try:
            self._execute_ban_action(session, action, local_player_cell_id)
        finally:
            self.action_completed.set()
    
    def _execute_ban_action(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Execute ban action after delay."""
        action_id = action['id']
        
        try:
            position = get_assigned_position(session, local_player_cell_id)
            role_to_use = position if position else 'default'
            
            preferences = self.role_preferences.get(role_to_use, {})
            ban_candidates = preferences.get('bans', [])
            
            # Fall back to default if role list is empty
            if not ban_candidates and role_to_use != 'default':
                logger.info(f"No bans for {role_to_use}, falling back to default")
                role_to_use = 'default'
                preferences = self.role_preferences.get('default', {})
                ban_candidates = preferences.get('bans', [])
            
            if not ban_candidates:
                logger.info(f"No ban preferences, skipping auto-ban")
                return
            
            logger.info(f"Champ select: assigned role = {position or 'none'}, using {role_to_use.capitalize()} list")
            
            # Get available bans
            bannable_ids = self._get_bannable_champions()
            banned = get_banned_champions(session)
            picked = get_picked_champions(session)
            teammate_intents = get_teammate_intents(session, local_player_cell_id)
            
            available = filter_available_champions(
                ban_candidates,
                set(),
                bannable_ids,
                'ban',
                banned,
                picked,
                teammate_intents
            )
            
            if not available:
                logger.info(f"No available bans from preferences, skipping")
                return
            
            # Get first candidate for logging
            champ_id = available[0]
            champ_name = self.champion_provider.get_display_name(champ_id)
            
            # Calculate safe delay
            delay = self._calculate_safe_delay(session, self.ban_delay_min, self.ban_delay_max)
            
            # In test mode, execute immediately without delay
            if self._test_mode:
                logger.debug(f"Auto-ban: test mode, banning {champ_name} immediately")
            elif delay <= 0:
                logger.info(f"Auto-ban: no time left for delay, banning {champ_name} immediately")
            else:
                logger.info(f"Auto-ban: waiting {delay:.1f}s before banning {champ_name}")
                
                # Wait with cancellation check
                if self.cancel_pending_action.wait(delay):
                    logger.debug("Ban action cancelled")
                    return
            
            # Re-fetch session and validate
            current_session = self._get_current_session()
            if not current_session:
                logger.debug("Ban: session ended during delay")
                return
            
            # Re-find our action
            my_action = find_my_action(current_session, local_player_cell_id)
            if not my_action or my_action.get('id') != action_id:
                logger.debug("Ban: action no longer ours or changed")
                return
            
            if my_action.get('completed'):
                logger.debug("Ban: user already acted manually")
                return
            
            # Re-select candidates (may have changed)
            bannable_ids = self._get_bannable_champions()
            banned = get_banned_champions(current_session)
            picked = get_picked_champions(current_session)
            teammate_intents = get_teammate_intents(current_session, local_player_cell_id)
            
            available = filter_available_champions(
                ban_candidates,
                set(),
                bannable_ids,
                'ban',
                banned,
                picked,
                teammate_intents
            )
            
            if not available:
                logger.info(f"No available bans after delay, skipping")
                return
            
            # Try each candidate
            for champ_id in available:
                champ_name = self.champion_provider.get_display_name(champ_id)
                logger.info(f"Auto-banning {champ_name}")
                
                if self._patch_action(action_id, champ_id, completed=True):
                    logger.info(f"[OK] Successfully banned {champ_name}")
                    return
                else:
                    logger.warning(f"Failed to ban {champ_id}, trying next candidate...")
            
            logger.warning("All ban candidates failed")
            
        except Exception as e:
            logger.error(f"Error in ban action: {e}", exc_info=True)
    
    def _handle_pick_action(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Handle pick action with delay."""
        action_id = action['id']
        
        # Check if already processed
        if action_id in self.processed_actions:
            return
        
        # Mark as processing
        self.processed_actions.add(action_id)
        
        # Cancel any existing pending action
        self._cancel_pending_actions()
        
        # In test mode, execute synchronously
        if self._test_mode:
            self._execute_pick_action(session, action, local_player_cell_id)
            self.action_completed.set()
        else:
            # Start delayed action in background thread
            self.action_completed.clear()
            self.pending_action_thread = threading.Thread(
                target=self._execute_pick_action_wrapper,
                args=(session, action, local_player_cell_id),
                daemon=True
            )
            self.pending_action_thread.start()
    
    def _execute_pick_action_wrapper(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Wrapper to signal completion."""
        try:
            self._execute_pick_action(session, action, local_player_cell_id)
        finally:
            self.action_completed.set()
    
    def _execute_pick_action(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Execute pick action after delay."""
        action_id = action['id']
        
        try:
            position = get_assigned_position(session, local_player_cell_id)
            role_to_use = position if position else 'default'
            
            preferences = self.role_preferences.get(role_to_use, {})
            pick_candidates = preferences.get('picks', [])
            
            # Fall back to default if role list is empty
            if not pick_candidates and role_to_use != 'default':
                logger.info(f"No picks for {role_to_use}, falling back to default")
                role_to_use = 'default'
                preferences = self.role_preferences.get('default', {})
                pick_candidates = preferences.get('picks', [])
            
            if not pick_candidates:
                logger.info(f"No pick preferences, skipping auto-pick")
                return
            
            logger.info(f"Champ select: assigned role = {position or 'none'}, using {role_to_use.capitalize()} list")
            
            # Get available picks
            pickable_ids = self._get_pickable_champions()
            banned = get_banned_champions(session)
            picked = get_picked_champions(session)
            teammate_intents = get_teammate_intents(session, local_player_cell_id)
            
            available = filter_available_champions(
                pick_candidates,
                pickable_ids,
                set(),
                'pick',
                banned,
                picked,
                teammate_intents
            )
            
            if not available:
                logger.info(f"No available picks from preferences, skipping")
                return
            
            # Get first candidate for logging
            champ_id = available[0]
            champ_name = self.champion_provider.get_display_name(champ_id)
            
            # Calculate safe delay
            delay = self._calculate_safe_delay(session, self.pick_delay_min, self.pick_delay_max)
            action_type = "lock" if self.pick_mode == 'lock' else "hover"
            
            # In test mode, execute immediately without delay
            if self._test_mode:
                logger.debug(f"Auto-pick: test mode, {action_type}ing {champ_name} immediately")
            elif delay <= 0:
                logger.info(f"Auto-pick: no time left for delay, {action_type}ing {champ_name} immediately")
            else:
                logger.info(f"Auto-pick: waiting {delay:.1f}s before {action_type}ing {champ_name}")
                
                # Wait with cancellation check
                if self.cancel_pending_action.wait(delay):
                    logger.debug("Pick action cancelled")
                    return
            
            # Re-fetch session and validate
            current_session = self._get_current_session()
            if not current_session:
                logger.debug("Pick: session ended during delay")
                return
            
            # Re-find our action
            my_action = find_my_action(current_session, local_player_cell_id)
            if not my_action or my_action.get('id') != action_id:
                logger.debug("Pick: action no longer ours or changed")
                return
            
            if my_action.get('completed'):
                logger.debug("Pick: user already acted manually")
                return
            
            # Re-select candidates (may have changed)
            pickable_ids = self._get_pickable_champions()
            banned = get_banned_champions(current_session)
            picked = get_picked_champions(current_session)
            teammate_intents = get_teammate_intents(current_session, local_player_cell_id)
            
            available = filter_available_champions(
                pick_candidates,
                pickable_ids,
                set(),
                'pick',
                banned,
                picked,
                teammate_intents
            )
            
            if not available:
                logger.info(f"No available picks after delay, skipping")
                return
            
            # Try each candidate
            for champ_id in available:
                champ_name = self.champion_provider.get_display_name(champ_id)
                
                if self.pick_mode == 'lock':
                    logger.info(f"Auto-picking and locking {champ_name}")
                    
                    if self._patch_action(action_id, champ_id, completed=True):
                        logger.info(f"[OK] Successfully picked and locked {champ_name}")
                        self.current_hover = None
                        return
                    else:
                        logger.warning(f"Failed to lock {champ_id}, trying next candidate...")
                else:
                    # Hover mode
                    logger.info(f"Auto-hovering {champ_name}")
                    
                    if self._patch_action(action_id, champ_id, completed=False):
                        logger.info(f"[OK] Successfully hovered {champ_name}")
                        self.current_hover = champ_id
                        return
                    else:
                        logger.warning(f"Failed to hover {champ_id}, trying next candidate...")
            
            logger.warning("All pick candidates failed")
            
        except Exception as e:
            logger.error(f"Error in pick action: {e}", exc_info=True)
    
    def _get_pickable_champions(self) -> Set[int]:
        """Get pickable champion IDs from API."""
        if not self.api_client:
            return set()
        
        try:
            response = self.api_client.get('/lol-champ-select/v1/pickable-champion-ids')
            if response and isinstance(response, list):
                return set(response)
        except Exception as e:
            logger.debug(f"Failed to get pickable champions: {e}")
        
        return set()
    
    def _get_bannable_champions(self) -> Set[int]:
        """Get bannable champion IDs from API."""
        if not self.api_client:
            return set()
        
        try:
            response = self.api_client.get('/lol-champ-select/v1/bannable-champion-ids')
            if response and isinstance(response, list):
                return set(response)
        except Exception as e:
            logger.debug(f"Failed to get bannable champions: {e}")
        
        return set()
    
    def _patch_action(self, action_id: int, champion_id: int, completed: bool) -> bool:
        """
        PATCH an action to hover or complete.
        
        Args:
            action_id: Action ID
            champion_id: Champion ID
            completed: True to lock/complete, False to hover
            
        Returns:
            True if successful
        """
        if not self.api_client:
            return False
        
        try:
            endpoint = f'/lol-champ-select/v1/session/actions/{action_id}'
            payload = {
                'championId': champion_id,
                'completed': completed
            }
            
            response = self.api_client.patch(endpoint, payload)
            return response is not None
        except Exception as e:
            logger.error(f"Failed to patch action {action_id}: {e}")
            return False
    
    def get_settings_schema(self) -> dict:
        """Get settings schema for UI."""
        return {
            'auto_ban_enabled': {
                'type': 'boolean',
                'label': 'Enable Auto-Ban',
                'description': 'Automatically ban champions',
                'default': False,
                'current': self.auto_ban_enabled
            },
            'auto_pick_enabled': {
                'type': 'boolean',
                'label': 'Enable Auto-Pick',
                'description': 'Automatically pick/hover champions',
                'default': False,
                'current': self.auto_pick_enabled
            },
            'pick_mode': {
                'type': 'select',
                'label': 'Pick Mode',
                'description': 'Hover or lock picks',
                'options': ['hover', 'lock'],
                'default': 'hover',
                'current': self.pick_mode
            }
        }
    
    def get_settings(self) -> dict:
        """Get current settings."""
        return {
            'auto_ban_enabled': self.auto_ban_enabled,
            'auto_pick_enabled': self.auto_pick_enabled,
            'pick_mode': self.pick_mode,
            'role_preferences': self.role_preferences,
            'ban_delay_min_seconds': self.ban_delay_min,
            'ban_delay_max_seconds': self.ban_delay_max,
            'pick_delay_min_seconds': self.pick_delay_min,
            'pick_delay_max_seconds': self.pick_delay_max
        }
    
    def update_setting(self, setting_name: str, value) -> bool:
        """Update a setting."""
        try:
            if setting_name == 'auto_ban_enabled':
                self.auto_ban_enabled = bool(value)
                logger.info(f"Updated auto_ban_enabled to {value}")
                return True
            elif setting_name == 'auto_pick_enabled':
                self.auto_pick_enabled = bool(value)
                logger.info(f"Updated auto_pick_enabled to {value}")
                return True
            elif setting_name == 'pick_mode':
                if value in ['hover', 'lock']:
                    self.pick_mode = value
                    logger.info(f"Updated pick_mode to {value}")
                    return True
            elif setting_name == 'role_preferences':
                if isinstance(value, dict):
                    self.role_preferences = value
                    logger.info("Updated role preferences")
                    return True
            elif setting_name == 'ban_delay_min_seconds':
                val = float(value)
                if val >= 0:
                    self.ban_delay_min = val
                    self._validate_delay_range('ban', self.ban_delay_min, self.ban_delay_max)
                    logger.info(f"Updated ban_delay_min_seconds to {val}")
                    return True
            elif setting_name == 'ban_delay_max_seconds':
                val = float(value)
                if val >= 0:
                    self.ban_delay_max = val
                    self._validate_delay_range('ban', self.ban_delay_min, self.ban_delay_max)
                    logger.info(f"Updated ban_delay_max_seconds to {val}")
                    return True
            elif setting_name == 'pick_delay_min_seconds':
                val = float(value)
                if val >= 0:
                    self.pick_delay_min = val
                    self._validate_delay_range('pick', self.pick_delay_min, self.pick_delay_max)
                    logger.info(f"Updated pick_delay_min_seconds to {val}")
                    return True
            elif setting_name == 'pick_delay_max_seconds':
                val = float(value)
                if val >= 0:
                    self.pick_delay_max = val
                    self._validate_delay_range('pick', self.pick_delay_min, self.pick_delay_max)
                    logger.info(f"Updated pick_delay_max_seconds to {val}")
                    return True
        except Exception as e:
            logger.error(f"Error updating setting {setting_name}: {e}")
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'enabled': self.enabled,
            'auto_ban_enabled': self.auto_ban_enabled,
            'auto_pick_enabled': self.auto_pick_enabled,
            'champions': self.get_champion_list()
        }
    
    def get_champion_list(self) -> List[Dict[str, Any]]:
        """Get champion list for UI with bilingual names."""
        champions = []
        champion_data = self.champion_provider.champion_data
        
        for champ_id in sorted(champion_data.keys(), key=lambda x: champion_data[x].get('name_en', '')):
            champions.append({
                'id': champ_id,
                'name': self.champion_provider.get_display_name(champ_id)
            })
        
        return champions
