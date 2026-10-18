"""Champion select auto-ban/auto-pick feature."""
import logging
import time
import threading
from typing import Optional, Dict, Any, List, Set
from features.base_feature import BaseFeature
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
        
        # Delays
        self.ban_delay = config.get('auto_ban_delay_seconds', 0.5)
        self.pick_delay = config.get('auto_pick_delay_seconds', 0.5)
        self.lock_delay = config.get('auto_lock_delay_seconds', 1.0)
        
        # State tracking
        self.processed_actions = set()  # Track action IDs we've already processed
        self.champion_map = {}  # name -> id mapping
        self.champion_reverse_map = {}  # id -> name mapping
        self.last_session_state = None
        self.current_hover = None  # Track current hover to avoid duplicate hover calls
    
    def initialize(self, event_bus, api_client):
        """Initialize the champion select feature."""
        self.api_client = api_client
        
        # Subscribe to champ select session events
        event_bus.subscribe('/lol-champ-select/v1/session', self._on_champ_select_event)
        
        # Load champion data
        self._load_champion_data()
        
        logger.info(
            f"Champion select feature initialized (auto_ban: {self.auto_ban_enabled}, "
            f"auto_pick: {self.auto_pick_enabled}, pick_mode: {self.pick_mode})"
        )
    
    def get_name(self) -> str:
        return "Champion Select"
    
    def _load_champion_data(self):
        """Load champion name<->ID mapping from client."""
        if not self.api_client:
            return
        
        try:
            # Try champion-summary.json first (more comprehensive)
            response = self.api_client.get('/lol-game-data/assets/v1/champion-summary.json')
            if response and isinstance(response, list):
                for champ in response:
                    champ_id = champ.get('id', 0)
                    name = champ.get('name', '')
                    if champ_id > 0 and name:
                        self.champion_map[name.lower()] = champ_id
                        self.champion_reverse_map[champ_id] = name
                
                logger.info(f"Loaded {len(self.champion_map)} champions from champion-summary.json")
                return
        except Exception as e:
            logger.debug(f"Failed to load champion-summary.json: {e}")
        
        # Fallback to owned-champions-minimal
        try:
            response = self.api_client.get('/lol-champions/v1/owned-champions-minimal')
            if response and isinstance(response, list):
                for champ in response:
                    champ_id = champ.get('id', 0)
                    name = champ.get('name', '')
                    if champ_id > 0 and name:
                        self.champion_map[name.lower()] = champ_id
                        self.champion_reverse_map[champ_id] = name
                
                logger.info(f"Loaded {len(self.champion_map)} champions from owned-champions-minimal")
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
                self.processed_actions.clear()
                self.current_hover = None
                return
            
            # Process the session
            self._process_session(data)
            
        except Exception as e:
            logger.error(f"Error handling champ select event: {e}", exc_info=True)
    
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
        """Hover top pick during PLANNING phase."""
        position = get_assigned_position(session, local_player_cell_id)
        preferences = self.role_preferences.get(position, {})
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
            set(),
            'pick',
            banned,
            picked,
            teammate_intents
        )
        
        if available and available[0] != self.current_hover:
            champ_id = available[0]
            champ_name = self.champion_reverse_map.get(champ_id, f'Champion {champ_id}')
            logger.info(f"PLANNING phase: hovering {champ_name} (position: {position})")
            
            # Hover via any pick action (doesn't have to be ours)
            actions = flatten_actions(session)
            for action in actions:
                if action.get('type') == 'pick':
                    self._patch_action(action['id'], champ_id, completed=False)
                    self.current_hover = champ_id
                    break
    
    def _handle_ban_action(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Handle ban action."""
        action_id = action['id']
        position = get_assigned_position(session, local_player_cell_id)
        
        preferences = self.role_preferences.get(position, {})
        ban_candidates = preferences.get('bans', [])
        
        if not ban_candidates:
            logger.info(f"No ban preferences for position '{position}', skipping auto-ban")
            self.processed_actions.add(action_id)
            return
        
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
            logger.info(f"No available bans from preferences (position: {position}), skipping")
            self.processed_actions.add(action_id)
            return
        
        # Try each candidate
        for champ_id in available:
            champ_name = self.champion_reverse_map.get(champ_id, f'Champion {champ_id}')
            logger.info(f"Auto-banning {champ_name} (position: {position})")
            
            time.sleep(self.ban_delay)
            
            if self._patch_action(action_id, champ_id, completed=True):
                logger.info(f"✓ Successfully banned {champ_name}")
                self.processed_actions.add(action_id)
                return
            else:
                logger.warning(f"Failed to ban {champ_id}, trying next candidate...")
        
        logger.warning("All ban candidates failed")
        self.processed_actions.add(action_id)
    
    def _handle_pick_action(
        self,
        session: Dict[str, Any],
        action: Dict[str, Any],
        local_player_cell_id: int
    ):
        """Handle pick action."""
        action_id = action['id']
        position = get_assigned_position(session, local_player_cell_id)
        
        preferences = self.role_preferences.get(position, {})
        pick_candidates = preferences.get('picks', [])
        
        if not pick_candidates:
            logger.info(f"No pick preferences for position '{position}', skipping auto-pick")
            self.processed_actions.add(action_id)
            return
        
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
            logger.info(f"No available picks from preferences (position: {position}), skipping")
            self.processed_actions.add(action_id)
            return
        
        # Try each candidate
        for champ_id in available:
            champ_name = self.champion_reverse_map.get(champ_id, f'Champion {champ_id}')
            
            if self.pick_mode == 'lock':
                logger.info(f"Auto-picking and locking {champ_name} (position: {position})")
                time.sleep(self.pick_delay)
                
                if self._patch_action(action_id, champ_id, completed=True):
                    logger.info(f"✓ Successfully picked and locked {champ_name}")
                    self.processed_actions.add(action_id)
                    self.current_hover = None
                    return
                else:
                    logger.warning(f"Failed to lock {champ_id}, trying next candidate...")
            else:
                # Hover mode
                logger.info(f"Auto-hovering {champ_name} (position: {position})")
                time.sleep(self.pick_delay)
                
                if self._patch_action(action_id, champ_id, completed=False):
                    logger.info(f"✓ Successfully hovered {champ_name}")
                    self.processed_actions.add(action_id)
                    self.current_hover = champ_id
                    return
                else:
                    logger.warning(f"Failed to hover {champ_id}, trying next candidate...")
        
        logger.warning("All pick candidates failed")
        self.processed_actions.add(action_id)
    
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
            'role_preferences': self.role_preferences
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
        """Get champion list for UI."""
        champions = []
        for champ_id, name in sorted(self.champion_reverse_map.items(), key=lambda x: x[1]):
            champions.append({
                'id': champ_id,
                'name': name
            })
        return champions
