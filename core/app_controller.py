"""Application controller - owns lifecycle, connection state, features, and config."""
import logging
import threading
import time
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path

from lcu.client_finder import get_client_info, ClientInfo
from lcu.api_client import LCUApiClient
from lcu.websocket_client import LCUWebSocketClient
from core.event_bus import EventBus

logger = logging.getLogger(__name__)


class AppController:
    """Main application controller that manages lifecycle and state."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.event_bus = EventBus()
        
        # Connection state
        self.api_client: Optional[LCUApiClient] = None
        self.ws_client: Optional[LCUWebSocketClient] = None
        self.current_client_info: Optional[ClientInfo] = None
        self.connection_state = "disconnected"  # disconnected, connecting, connected
        self.gameflow_phase = "None"  # None, Lobby, Matchmaking, ReadyCheck, ChampSelect, InGame, etc.
        
        # Features
        self.features: List[Any] = []
        
        # State change callbacks for UI
        self.state_callbacks: List[Callable] = []
        
        # Running state
        self.running = False
        self.connection_thread: Optional[threading.Thread] = None
    
    def register_feature(self, feature):
        """Register a feature with the controller."""
        self.features.append(feature)
        logger.info(f"Registered feature: {feature.get_name()}")
    
    def start(self):
        """Start the controller and connection management."""
        if self.running:
            return
        
        self.running = True
        self.connection_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self.connection_thread.start()
        logger.info("AppController started")
    
    def stop(self):
        """Stop the controller and cleanup."""
        self.running = False
        self._disconnect()
        
        # Stop all features
        for feature in self.features:
            if hasattr(feature, 'stop'):
                feature.stop()
        
        if self.connection_thread:
            self.connection_thread.join(timeout=5)
        
        logger.info("AppController stopped")
    
    def subscribe_state_change(self, callback: Callable):
        """Subscribe to state changes."""
        self.state_callbacks.append(callback)
    
    def _notify_state_change(self):
        """Notify all subscribers of state change."""
        for callback in self.state_callbacks:
            try:
                callback(self.get_state())
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current application state."""
        return {
            'connection_state': self.connection_state,
            'gameflow_phase': self.gameflow_phase,
            'client_info': {
                'port': self.current_client_info.port if self.current_client_info else None,
                'install_dir': self.current_client_info.install_dir if self.current_client_info else None
            } if self.current_client_info else None,
            'features': [
                {
                    'name': f.get_name(),
                    'enabled': f.enabled,
                    'settings': f.get_settings() if hasattr(f, 'get_settings') else {},
                    'status': f.get_status() if hasattr(f, 'get_status') else {}
                }
                for f in self.features
            ]
        }
    
    def update_feature_setting(self, feature_name: str, setting_name: str, value: Any) -> bool:
        """Update a feature setting and persist to config."""
        for feature in self.features:
            if feature.get_name() == feature_name:
                if hasattr(feature, 'update_setting'):
                    success = feature.update_setting(setting_name, value)
                    if success:
                        # Persist to config
                        self._save_config()
                        self._notify_state_change()
                        return True
        return False
    
    def toggle_feature(self, feature_name: str) -> bool:
        """Toggle a feature on/off."""
        for feature in self.features:
            if feature.get_name() == feature_name:
                if feature.enabled:
                    feature.disable()
                else:
                    feature.enable()
                
                # Persist to config
                self._save_config()
                self._notify_state_change()
                return feature.enabled
        return False
    
    def _save_config(self):
        """Save current config to file."""
        try:
            import yaml
            # Update config with current feature states
            for feature in self.features:
                name = feature.get_name()
                if name == 'Auto-Accept':
                    self.config['auto_accept_enabled'] = feature.enabled
                    if hasattr(feature, 'accept_delay_min'):
                        self.config['accept_delay_min_seconds'] = feature.accept_delay_min
                    if hasattr(feature, 'accept_delay_max'):
                        self.config['accept_delay_max_seconds'] = feature.accept_delay_max
                elif name == 'Champion Select':
                    self.config['auto_ban_enabled'] = feature.auto_ban_enabled
                    self.config['auto_pick_enabled'] = feature.auto_pick_enabled
                    self.config['pick_mode'] = feature.pick_mode
                    self.config['champ_select_preferences'] = feature.role_preferences
            
            # Write to file
            with open('config.yaml', 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            
            logger.debug("Config saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def _is_connected(self) -> bool:
        """Check if currently connected to client."""
        return (self.current_client_info is not None and 
                self.api_client is not None and 
                self.ws_client is not None and 
                self.ws_client.connected)
    
    def _connection_loop(self):
        """Main connection management loop."""
        retry_delay = 5
        
        while self.running:
            try:
                if self._is_connected():
                    # Already connected, just sleep
                    time.sleep(5)
                    continue
                
                # Update state
                old_state = self.connection_state
                self.connection_state = "connecting"
                if old_state != self.connection_state:
                    self._notify_state_change()
                
                # Try to connect
                if self._connect():
                    self.connection_state = "connected"
                    self._notify_state_change()
                else:
                    self.connection_state = "disconnected"
                    self._notify_state_change()
                    time.sleep(retry_delay)
            
            except Exception as e:
                logger.error(f"Error in connection loop: {e}", exc_info=True)
                time.sleep(retry_delay)
    
    def _connect(self) -> bool:
        """Attempt to connect to League Client."""
        client_info = get_client_info()
        
        if not client_info:
            return False
        
        # Check if client info changed (client restarted)
        if (self.current_client_info and 
            (self.current_client_info.port != client_info.port or
             self.current_client_info.password != client_info.password)):
            logger.info("Client info changed, reconnecting...")
            self._disconnect()
        
        # Only log on new connection
        if not self.current_client_info:
            logger.info(f"Client detected at port {client_info.port}")
        
        self.current_client_info = client_info
        
        # Create API client if needed
        if not self.api_client:
            self.api_client = LCUApiClient(client_info.port, client_info.password)
            
            # Initialize features
            for feature in self.features:
                feature.initialize(self.event_bus, self.api_client)
            
            logger.info(f"API client initialized on port {client_info.port}")
        
        # Connect WebSocket if not connected
        if not self.ws_client or not self.ws_client.connected or not self.ws_client.running:
            logger.info(f"Connecting to WebSocket (port {client_info.port})...")
            
            if self.ws_client:
                self.ws_client.disconnect()
            
            self.ws_client = LCUWebSocketClient(
                client_info.port,
                client_info.password,
                self._on_ws_event
            )
            
            if self.ws_client.connect():
                time.sleep(0.5)
                if self.ws_client.connected:
                    logger.info("Successfully connected to League Client")
                    
                    # Initialize gameflow phase on connect
                    self._fetch_gameflow_phase()
                    
                    return True
        
        return False
    
    def _fetch_gameflow_phase(self):
        """Fetch current gameflow phase via GET."""
        if not self.api_client:
            return
        
        try:
            response = self.api_client.get("/lol-gameflow/v1/gameflow-phase")
            if response and response.status_code == 200:
                phase = response.text.strip('"')
                if phase != self.gameflow_phase:
                    self.gameflow_phase = phase
                    logger.info(f"Gameflow phase: {phase}")
                    self._notify_state_change()
        except Exception as e:
            logger.debug(f"Error fetching gameflow phase: {e}")
    
    def _disconnect(self):
        """Disconnect from client."""
        if self.ws_client:
            self.ws_client.disconnect()
            self.ws_client = None
        self.api_client = None
        self.current_client_info = None
    
    def _on_ws_event(self, uri: str, event_data: dict):
        """Handle WebSocket events."""
        # Update gameflow phase if relevant
        if uri == '/lol-gameflow/v1/gameflow-phase':
            data = event_data.get('data')
            if data:
                self.gameflow_phase = data
                self._notify_state_change()
        
        # Forward to event bus
        self.event_bus.publish(uri, event_data)
