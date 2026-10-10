"""Auto-accept ready check feature."""
import logging
import time
import threading
import random
from typing import Optional
from features.base_feature import BaseFeature

logger = logging.getLogger(__name__)


class AutoAcceptFeature(BaseFeature):
    """Automatically accept matchmaking ready checks."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_client = None
        
        # Backward compatibility: check for old accept_delay_seconds config
        if 'accept_delay_seconds' in config:
            # Old config: use fixed delay
            self.accept_delay_min = config.get('accept_delay_seconds', 0)
            self.accept_delay_max = self.accept_delay_min
        else:
            # New config: use random delay range
            self.accept_delay_min = config.get('accept_delay_min_seconds', 1)
            self.accept_delay_max = config.get('accept_delay_max_seconds', 4)
        
        self.last_accept_time = 0
        self.cooldown = 2  # Prevent multiple accepts in quick succession
        self.polling_thread = None
        self.running = False
        self.last_state = None  # Track last state to avoid duplicate logs
        self.last_player_response = None
        self.accept_scheduled = False  # Prevent duplicate accept scheduling
        
        # Accept history (last 10)
        self.accept_history = []
    
    def initialize(self, event_bus, api_client):
        """Initialize the auto-accept feature."""
        self.api_client = api_client
        
        # Subscribe to ready check events (primary method)
        event_bus.subscribe('/lol-matchmaking/v1/ready-check', self._on_ready_check_event)
        
        # Start HTTP polling as fallback (belt-and-braces)
        self.running = True
        self.polling_thread = threading.Thread(target=self._poll_ready_check, daemon=True)
        self.polling_thread.start()
        
        if self.accept_delay_min == self.accept_delay_max:
            logger.info(f"Auto-accept feature initialized (delay: {self.accept_delay_min}s fixed, polling: enabled)")
        else:
            logger.info(f"Auto-accept feature initialized (delay: {self.accept_delay_min}-{self.accept_delay_max}s random, polling: enabled)")
    
    def get_name(self) -> str:
        return "Auto-Accept"
    
    def _on_ready_check_event(self, uri: str, event_data: dict):
        """Handle ready check events."""
        if not self.enabled:
            return
        
        try:
            event_type = event_data.get('eventType', '')
            
            # Handle null/missing data (Delete events, ended ready checks)
            data = event_data.get('data')
            if data is None:
                # Delete event or null data - ready check ended/removed
                logger.debug(f"Ready check event with null data: eventType={event_type}")
                # Reset state tracking
                if self.last_state != 'None':
                    logger.debug("Ready check ended (Delete event)")
                    self.last_state = 'None'
                    self.last_player_response = None
                    self.accept_scheduled = False  # Reset scheduled flag
                return
            
            # Extract state and response
            state = data.get('state', '')
            player_response = data.get('playerResponse', '')
            
            # Log at INFO only if state or response changed
            state_changed = (state != self.last_state or player_response != self.last_player_response)
            if state_changed:
                logger.info(f"Ready check state change: eventType={event_type}, state={state}, playerResponse={player_response}")
                self.last_state = state
                self.last_player_response = player_response
                
                # Reset scheduled flag if state changed away from InProgress
                if state != 'InProgress':
                    self.accept_scheduled = False
            else:
                logger.debug(f"Ready check event (no change): eventType={event_type}, state={state}, playerResponse={player_response}")
            
            # Check if ready check is active and we haven't responded
            if state == 'InProgress' and player_response == 'None':
                # Check if accept already scheduled for this ready check
                if self.accept_scheduled:
                    logger.debug("Accept already scheduled for this ready check, skipping")
                    return
                
                # Apply cooldown to prevent duplicate accepts
                current_time = time.time()
                if current_time - self.last_accept_time < self.cooldown:
                    logger.debug("Skipping accept due to cooldown")
                    return
                
                # Mark accept as scheduled
                self.accept_scheduled = True
                
                # Calculate delay (random if range specified, fixed otherwise)
                if self.accept_delay_min == self.accept_delay_max:
                    delay = self.accept_delay_min
                else:
                    delay = random.uniform(self.accept_delay_min, self.accept_delay_max)
                
                # Accept after delay
                if delay > 0:
                    logger.info(f"Ready check detected, accepting in {delay:.2f}s...")
                    threading.Thread(
                        target=self._delayed_accept,
                        args=(delay,),
                        daemon=True
                    ).start()
                else:
                    logger.info("Ready check detected, accepting NOW...")
                    self._accept_with_recheck()
        except Exception as e:
            logger.error(f"Error handling ready check event: {e}", exc_info=True)
    
    def _delayed_accept(self, delay: float):
        """Accept after specified delay with re-check."""
        self._last_delay = delay  # Store for history
        time.sleep(delay)
        self._accept_with_recheck()
    
    def _accept_with_recheck(self):
        """Accept the ready check after re-checking state."""
        try:
            # Re-check ready check state before accepting
            if self.api_client:
                state_data = self.api_client.get_ready_check_state()
                
                if state_data:
                    state = state_data.get('state', '')
                    player_response = state_data.get('playerResponse', '')
                    
                    if state != 'InProgress':
                        logger.info(f"Ready check no longer InProgress (state={state}), skipping accept")
                        return
                    
                    if player_response != 'None':
                        logger.info(f"Player already responded (response={player_response}), skipping accept")
                        return
                else:
                    logger.debug("Ready check state unavailable (404/null), skipping accept")
                    return
            
            # State is still valid, proceed with accept
            self._accept()
        finally:
            # Always reset scheduled flag
            self.accept_scheduled = False
    
    def _accept(self):
        """Accept the ready check."""
        if not self.api_client:
            logger.error("API client not initialized")
            return
        
        success = self.api_client.accept_ready_check()
        if not success:
            logger.warning("Failed to accept ready check")
        else:
            # Record successful accept in history
            self._record_accept()
        
        # Update last accept time
        self.last_accept_time = time.time()
    
    def _poll_ready_check(self):
        """Poll ready check state via HTTP as fallback (every 1 second)."""
        logger.info("HTTP polling fallback started (1s interval)")
        
        while self.running and self.enabled:
            try:
                time.sleep(1)
                
                if not self.api_client:
                    continue
                
                # Get current ready check state
                state_data = self.api_client.get_ready_check_state()
                
                # Handle null response (404, not in ready check)
                if state_data is None:
                    logger.debug("HTTP poll: no active ready check (404/null)")
                    continue
                
                state = state_data.get('state', '')
                player_response = state_data.get('playerResponse', '')
                
                logger.debug(f"HTTP poll: state={state}, playerResponse={player_response}")
                
                # Check if ready check is active and we haven't responded
                if state == 'InProgress' and player_response == 'None':
                    # Check if accept already scheduled (WS handler may have scheduled it)
                    if self.accept_scheduled:
                        logger.debug("Accept already scheduled by WS handler, skipping poll accept")
                        continue
                    
                    # Apply cooldown
                    current_time = time.time()
                    if current_time - self.last_accept_time < self.cooldown:
                        continue
                    
                    # Mark accept as scheduled
                    self.accept_scheduled = True
                    
                    # Calculate delay
                    if self.accept_delay_min == self.accept_delay_max:
                        delay = self.accept_delay_min
                    else:
                        delay = random.uniform(self.accept_delay_min, self.accept_delay_max)
                    
                    logger.info(f"Ready check detected via HTTP polling, accepting in {delay:.2f}s...")
                    
                    # Accept with delay in separate thread
                    if delay > 0:
                        threading.Thread(
                            target=self._delayed_accept,
                            args=(delay,),
                            daemon=True
                        ).start()
                    else:
                        self._accept_with_recheck()
                        
            except Exception as e:
                logger.debug(f"Error in HTTP polling: {e}")
        
        logger.info("HTTP polling fallback stopped")
    
    def stop(self):
        """Stop the feature and cleanup."""
        self.running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=2)
    
    def get_settings_schema(self) -> dict:
        """Get settings schema for UI."""
        return {
            'accept_delay_min_seconds': {
                'type': 'number',
                'label': 'Min Delay (seconds)',
                'description': 'Minimum random delay before accepting',
                'default': 1,
                'min': 0,
                'max': 10,
                'current': self.accept_delay_min
            },
            'accept_delay_max_seconds': {
                'type': 'number',
                'label': 'Max Delay (seconds)',
                'description': 'Maximum random delay before accepting',
                'default': 4,
                'min': 0,
                'max': 10,
                'current': self.accept_delay_max
            }
        }
    
    def get_settings(self) -> dict:
        """Get current settings."""
        return {
            'accept_delay_min_seconds': self.accept_delay_min,
            'accept_delay_max_seconds': self.accept_delay_max
        }
    
    def get_status(self) -> dict:
        """Get current status."""
        return {
            'enabled': self.enabled,
            'last_accept_time': self.last_accept_time,
            'accept_history': self.accept_history[-10:]  # Last 10
        }
    
    def update_setting(self, setting_name: str, value) -> bool:
        """Update a setting."""
        try:
            if setting_name == 'accept_delay_min_seconds':
                self.accept_delay_min = float(value)
                logger.info(f"Updated accept_delay_min to {value}s")
                return True
            elif setting_name == 'accept_delay_max_seconds':
                self.accept_delay_max = float(value)
                logger.info(f"Updated accept_delay_max to {value}s")
                return True
        except Exception as e:
            logger.error(f"Error updating setting {setting_name}: {e}")
        return False
    
    def _record_accept(self):
        """Record an accept in history."""
        import datetime
        self.accept_history.append({
            'timestamp': datetime.datetime.now().isoformat(),
            'delay': getattr(self, '_last_delay', 0)
        })
        if len(self.accept_history) > 10:
            self.accept_history.pop(0)
