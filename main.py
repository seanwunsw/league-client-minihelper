"""League of Legends Auto-Accept Helper - Main Entry Point."""
import sys
import os
import time
import logging
from logging.handlers import RotatingFileHandler
import yaml
from pathlib import Path
import threading
from typing import Optional
import traceback

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

# Try to import Windows message box and mutex
try:
    import ctypes
    from ctypes import wintypes
    MESSAGEBOX_AVAILABLE = True
    WINDOWS = True
except ImportError:
    MESSAGEBOX_AVAILABLE = False
    WINDOWS = False


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
        """Setup logging configuration with file and console output."""
        log_level = getattr(logging, self.config.get('log_level', 'INFO').upper())
        
        # Get log file path (next to executable)
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        log_file = os.path.join(app_dir, "LoLAutoAccept.log")
        
        # Create formatters
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        
        # File handler with rotation (max 5MB, keep 3 backups)
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            handlers = [console_handler, file_handler]
            print(f"Logging to: {log_file}")
        except Exception as e:
            print(f"Warning: Could not create log file: {e}")
            handlers = [console_handler]
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 60)
        self.logger.info("LoL Auto-Accept Helper Started")
        self.logger.info(f"Version: 0.1.2")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info("=" * 60)
    
    def _initialize_features(self):
        """Initialize all features."""
        # Auto-accept feature
        auto_accept = AutoAcceptFeature(self.config)
        if not self.config.get('auto_accept_enabled', True):
            auto_accept.disable()
        self.features.append(auto_accept)
    
    def _is_connected(self) -> bool:
        """Check if currently connected to client (cheap health check)."""
        # Check if we have a client, API client, and WebSocket is connected
        return (self.current_client_info is not None and 
                self.api_client is not None and 
                self.ws_client is not None and 
                self.ws_client.connected)
    
    def _connect_to_client(self) -> bool:
        """Connect to League Client (only logs discovery on first call or when state changes)."""
        try:
            # If already connected and WebSocket is still alive, don't re-discover
            if self._is_connected():
                return True
            
            # If we had a connection that died, log that we're reconnecting
            if self.current_client_info and not self._is_connected():
                self.logger.info("Connection lost, attempting to reconnect...")
            
            client_info = get_client_info()
            
            if not client_info:
                # Only log "not detected" if state changed from connected to disconnected
                if self.current_client_info:
                    self.logger.warning("Client no longer detected")
                    self.current_client_info = None
                self.status = "Waiting for League Client...\n(Check log file for details)"
                return False
            
            # Check if client info changed (client restarted with different port/password)
            if (self.current_client_info and 
                (self.current_client_info.port != client_info.port or
                 self.current_client_info.password != client_info.password)):
                self.logger.info(f"Client info changed (port: {self.current_client_info.port} -> {client_info.port}), reconnecting...")
                self._disconnect()
            
            # Only log new connection if we didn't have one before
            if not self.current_client_info:
                self.logger.info(f"Client detected at port {client_info.port}")
            
            self.current_client_info = client_info
            
            # Create API client if needed
            if not self.api_client:
                self.api_client = LCUApiClient(client_info.port, client_info.password)
                
                # Initialize features with API client
                for feature in self.features:
                    feature.initialize(self.event_bus, self.api_client)
                
                self.logger.info(f"API client initialized on port {client_info.port}")
            
            # Connect WebSocket if not connected or not running
            if not self.ws_client or not self.ws_client.connected or not self.ws_client.running:
                self.logger.info(f"Connecting to League Client WebSocket (port {client_info.port})...")
                
                # If ws_client exists but is dead, clean it up first
                if self.ws_client:
                    self.ws_client.disconnect()
                
                self.ws_client = LCUWebSocketClient(
                    client_info.port,
                    client_info.password,
                    self._on_ws_event
                )
                
                if self.ws_client.connect():
                    # Wait a moment for connection to establish
                    time.sleep(0.5)
                    
                    if self.ws_client.connected:
                        enabled_features = [f.get_name() for f in self.features if f.enabled]
                        self.status = f"Connected!\nEnabled: {', '.join(enabled_features)}"
                        self.logger.info(f"Successfully connected to League Client")
                        return True
                    else:
                        self.logger.warning("WebSocket connection started but not yet connected")
                        return False
                else:
                    self.logger.warning("Failed to start WebSocket connection, will retry...")
                    self.status = "Connection failed, retrying..."
                    return False
            
            return True
        except Exception as e:
            self.logger.error(f"Error in _connect_to_client: {e}", exc_info=True)
            self.status = f"Error: {str(e)[:50]}"
            return False
    
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
    icon_ref = [None]  # Mutable container to hold icon reference
    
    def update_tooltip():
        """Update tray icon tooltip with current status."""
        if icon_ref[0]:
            icon_ref[0].title = f"LoL Helper\n{helper.status}"
    
    def on_quit(icon, item):
        helper.stop()
        icon.stop()
    
    def on_toggle(icon, item):
        enabled = helper.toggle_auto_accept()
        status = "enabled" if enabled else "disabled"
        helper.logger.info(f"Auto-accept {status}")
        print(f"Auto-accept {status}")
        update_tooltip()
    
    def on_show_status(icon, item):
        status_msg = f"Status: {helper.status}\n"
        enabled_features = [f.get_name() for f in helper.features if f.enabled]
        status_msg += f"Enabled features: {', '.join(enabled_features)}"
        print(status_msg)
        helper.logger.info(status_msg)
        # Show message box on Windows
        if MESSAGEBOX_AVAILABLE:
            try:
                ctypes.windll.user32.MessageBoxW(0, status_msg, "LoL Helper Status", 0x40)
            except:
                pass
    
    menu = pystray.Menu(
        pystray.MenuItem("Show Status", on_show_status),
        pystray.MenuItem("Toggle Auto-Accept", on_toggle),
        pystray.MenuItem("Quit", on_quit)
    )
    
    icon = pystray.Icon("lol_helper", icon_image, f"LoL Helper\n{helper.status}", menu)
    icon_ref[0] = icon
    
    # Update tooltip periodically
    def update_loop():
        while helper.running:
            update_tooltip()
            time.sleep(2)
    
    # Run helper in separate thread
    helper_thread = threading.Thread(target=helper.run, daemon=True)
    helper_thread.start()
    
    # Run tooltip updater in separate thread
    tooltip_thread = threading.Thread(target=update_loop, daemon=True)
    tooltip_thread.start()
    
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


def show_error_message(title: str, message: str):
    """Show error message box on Windows."""
    print(f"\n{'='*60}\nERROR: {title}\n{message}\n{'='*60}\n")
    
    if MESSAGEBOX_AVAILABLE:
        try:
            # MB_ICONERROR | MB_OK = 0x10
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except:
            pass


def show_info_message(title: str, message: str):
    """Show info message box on Windows."""
    print(f"\n{title}\n{message}\n")
    
    if MESSAGEBOX_AVAILABLE:
        try:
            # MB_ICONINFORMATION | MB_OK = 0x40
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        except:
            pass


def check_single_instance():
    """Check if another instance is already running (Windows only)."""
    if not WINDOWS:
        return None
    
    try:
        # Create a named mutex
        mutex_name = "Global\\LoLAutoAcceptHelper_SingleInstance"
        
        # Windows API constants
        ERROR_ALREADY_EXISTS = 183
        
        # Try to create mutex
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, True, mutex_name)
        
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            # Another instance is already running
            return None
        
        # Return mutex handle to keep it alive
        return mutex
    except Exception as e:
        print(f"Warning: Could not check for single instance: {e}")
        return None


if __name__ == "__main__":
    # Check for single instance (Windows only)
    mutex = check_single_instance()
    if mutex is None and WINDOWS:
        show_info_message(
            "LoL Helper Already Running",
            "Another instance of LoL Auto-Accept Helper is already running.\n\n"
            "Check the system tray (bottom-right corner) for the icon."
        )
        sys.exit(0)
    
    try:
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
    
    except Exception as e:
        error_msg = f"Fatal error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        
        # Try to log to file if possible
        try:
            log_file = os.path.join(app_dir if 'app_dir' in locals() else '.', "LoLAutoAccept.log")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\nFATAL ERROR\n{'='*60}\n")
                f.write(error_msg)
                f.write(f"\n{'='*60}\n")
        except:
            pass
        
        show_error_message("LoL Helper - Fatal Error", error_msg)
        sys.exit(1)
