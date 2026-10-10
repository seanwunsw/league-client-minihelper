"""Auto-accept ready check feature."""
import logging
import time
import threading
from typing import Optional
from features.base_feature import BaseFeature

logger = logging.getLogger(__name__)


class AutoAcceptFeature(BaseFeature):
    """Automatically accept matchmaking ready checks."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_client = None
        self.accept_delay = config.get('accept_delay_seconds', 0)
        self.last_accept_time = 0
        self.cooldown = 2  # Prevent multiple accepts in quick succession
        self.polling_thread = None
        self.running = False
    
    def initialize(self, event_bus, api_client):
        """Initialize the auto-accept feature."""
        self.api_client = api_client
        
        # Subscribe to ready check events (primary method)
        event_bus.subscribe('/lol-matchmaking/v1/ready-check', self._on_ready_check_event)
        
        # Start HTTP polling as fallback (belt-and-braces)
        self.running = True
        self.polling_thread = threading.Thread(target=self._poll_ready_check, daemon=True)
        self.polling_thread.start()
        
        logger.info(f"Auto-accept feature initialized (delay: {self.accept_delay}s, polling: enabled)")
    
    def get_name(self) -> str:
        return "Auto-Accept"
    
    def _on_ready_check_event(self, uri: str, event_data: dict):
        """Handle ready check events."""
        if not self.enabled:
            return
        
        try:
            data = event_data.get('data', {})
            state = data.get('state', '')
            player_response = data.get('playerResponse', '')
            event_type = event_data.get('eventType', '')
            
            # Log every ready check event at INFO level
            logger.info(f"Ready check event received: uri={uri}, eventType={event_type}, state={state}, playerResponse={player_response}")
            
            # Check if ready check is active and we haven't responded
            if state == 'InProgress' and player_response == 'None':
                # Apply cooldown to prevent duplicate accepts
                current_time = time.time()
                if current_time - self.last_accept_time < self.cooldown:
                    logger.debug("Skipping accept due to cooldown")
                    return
                
                self.last_accept_time = current_time
                
                # Accept after delay (if configured)
                if self.accept_delay > 0:
                    logger.info(f"Ready check detected, accepting in {self.accept_delay}s...")
                    threading.Thread(
                        target=self._delayed_accept,
                        daemon=True
                    ).start()
                else:
                    logger.info("Ready check detected, accepting NOW...")
                    self._accept()
        except Exception as e:
            logger.error(f"Error handling ready check event: {e}", exc_info=True)
    
    def _delayed_accept(self):
        """Accept after configured delay."""
        time.sleep(self.accept_delay)
        self._accept()
    
    def _accept(self):
        """Accept the ready check."""
        if not self.api_client:
            logger.error("API client not initialized")
            return
        
        success = self.api_client.accept_ready_check()
        if not success:
            logger.warning("Failed to accept ready check")
    
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
                
                if state_data:
                    state = state_data.get('state', '')
                    player_response = state_data.get('playerResponse', '')
                    
                    logger.debug(f"HTTP poll: state={state}, playerResponse={player_response}")
                    
                    # Check if ready check is active and we haven't responded
                    if state == 'InProgress' and player_response == 'None':
                        # Apply cooldown
                        current_time = time.time()
                        if current_time - self.last_accept_time < self.cooldown:
                            continue
                        
                        self.last_accept_time = current_time
                        logger.info("Ready check detected via HTTP polling, accepting...")
                        self._accept()
                        
            except Exception as e:
                logger.debug(f"Error in HTTP polling: {e}")
        
        logger.info("HTTP polling fallback stopped")
    
    def stop(self):
        """Stop the feature and cleanup."""
        self.running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=2)
