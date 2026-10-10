"""League of Legends Auto-Accept Helper - Main Entry Point."""
import sys
import os
import time
import logging
import yaml
from pathlib import Path
import threading
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lcu.client_finder import get_client_info, ClientInfo
from lcu.api_client import LCUApiClient
from lcu.websocket_client import LCUWebSocketClient
from core.event_bus import EventBus
from features.auto_accept import AutoAcceptFeature

# Try to import GUI dependencies
try:
    import pystray
    from PIL import Image, ImageDraw
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


class LoLHelper:
    """Main application class."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self._setup_logging()
        
        self.event_bus = EventBus()
        self.api_client: Optional[LCUApiClient] = None
        self.ws_client: Optional[LCUWebSocketClient] = None
        self.current_client_info: Optional[ClientInfo] = None
        
        # Initialize features
        self.features = []
        self._initialize_features()
        
        self.running = False
        self.status = "Starting..."
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        default_config = {
            'auto_accept_enabled': True,
            'accept_delay_seconds': 0,
            'log_level': 'INFO'
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
                    if loaded_config:
                        default_config.update(loaded_config)
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")
        else:
            # Create default config file
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(default_config, f, default_flow_style=False)
                print(f"Created default config at {config_path}")
            except Exception as e:
                print(f"Warning: Failed to create config: {e}")
        
        return default_config
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = getattr(logging, self.config.get('log_level', 'INFO').upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _initialize_features(self):
        """Initialize all features."""
        # Auto-accept feature
        auto_accept = AutoAcceptFeature(self.config)
        if not self.config.get('auto_accept_enabled', True):
            auto_accept.disable()
        self.features.append(auto_accept)
    
    def _connect_to_client(self) -> bool:
        """Connect to League Client."""
        client_info = get_client_info()
        
        if not client_info:
            self.status = "Waiting for League Client..."
            return False
        
        # Check if client info changed (client restarted)
        if (self.current_client_info and 
            (self.current_client_info.port != client_info.port or
             self.current_client_info.password != client_info.password)):
            self.logger.info("Client info changed, reconnecting...")
            self._disconnect()
        
        self.current_client_info = client_info
        
        # Create API client
        if not self.api_client:
            self.api_client = LCUApiClient(client_info.port, client_info.password)
            
            # Initialize features with API client
            for feature in self.features:
                feature.initialize(self.event_bus, self.api_client)
        
        # Connect WebSocket if not connected
        if not self.ws_client or not self.ws_client.connected:
            self.logger.info("Connecting to League Client WebSocket...")
            self.ws_client = LCUWebSocketClient(
                client_info.port,
                client_info.password,
                self._on_ws_event
            )
            
            if self.ws_client.connect():
                self.status = "Connected to League Client"
                return True
            else:
                self.logger.warning("Failed to connect WebSocket, will retry...")
                self.status = "Connection failed, retrying..."
                return False
        
        return True
    
    def _on_ws_event(self, uri: str, event_data: dict):
        """Handle WebSocket events."""
        self.event_bus.publish(uri, event_data)
    
    def _disconnect(self):
        """Disconnect from client."""
        if self.ws_client:
            self.ws_client.disconnect()
            self.ws_client = None
        self.api_client = None
        self.current_client_info = None
    
    def run(self):
        """Main application loop."""
        self.running = True
        self.logger.info("LoL Helper started")
        
        retry_delay = 5  # seconds
        
        try:
            while self.running:
                if not self._connect_to_client():
                    time.sleep(retry_delay)
                    continue
                
                # Keep alive - check connection every 5 seconds
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the application."""
        self.running = False
        self._disconnect()
        self.logger.info("LoL Helper stopped")
    
    def toggle_auto_accept(self):
        """Toggle auto-accept feature."""
        for feature in self.features:
            if feature.get_name() == "Auto-Accept":
                if feature.enabled:
                    feature.disable()
                else:
                    feature.enable()
                return feature.enabled
        return False


def create_icon_image():
    """Create a simple icon for system tray."""
    # Create a simple colored circle
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (30, 30, 30))
    draw = ImageDraw.Draw(image)
    
    # Draw a circle
    draw.ellipse([8, 8, width-8, height-8], fill=(100, 200, 100), outline=(255, 255, 255))
    
    return image


def run_with_gui(helper: LoLHelper):
    """Run with system tray GUI."""
    icon_image = create_icon_image()
    
    def on_quit(icon, item):
        helper.stop()
        icon.stop()
    
    def on_toggle(icon, item):
        enabled = helper.toggle_auto_accept()
        status = "enabled" if enabled else "disabled"
        print(f"Auto-accept {status}")
    
    def on_show_status(icon, item):
        print(f"Status: {helper.status}")
        enabled_features = [f.get_name() for f in helper.features if f.enabled]
        print(f"Enabled features: {', '.join(enabled_features)}")
    
    menu = pystray.Menu(
        pystray.MenuItem("Status", on_show_status),
        pystray.MenuItem("Toggle Auto-Accept", on_toggle),
        pystray.MenuItem("Quit", on_quit)
    )
    
    icon = pystray.Icon("lol_helper", icon_image, "LoL Helper", menu)
    
    # Run helper in separate thread
    helper_thread = threading.Thread(target=helper.run, daemon=True)
    helper_thread.start()
    
    # Run tray icon (blocks until quit)
    icon.run()


def run_console(helper: LoLHelper):
    """Run in console mode."""
    print("="*50)
    print("League of Legends Auto-Accept Helper")
    print("="*50)
    print("Press Ctrl+C to quit")
    print()
    
    helper.run()


if __name__ == "__main__":
    # Get config path relative to executable
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        app_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    config_path = os.path.join(app_dir, "config.yaml")
    
    helper = LoLHelper(config_path)
    
    # Choose GUI or console mode
    if GUI_AVAILABLE and not sys.platform.startswith('linux'):
        run_with_gui(helper)
    else:
        run_console(helper)
