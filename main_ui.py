"""
LoL Auto-Accept Helper with pywebview UI
"""
import os
import sys
import logging
import threading
import time
import ctypes
import socket
from pathlib import Path
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_accept_ui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Check for WebView2
def check_webview2():
    """Check if WebView2 runtime is available."""
    try:
        import webview
        return True
    except Exception as e:
        logger.error(f"WebView2 check failed: {e}")
        return False

# Fallback message if WebView2 missing
def show_webview2_missing():
    """Show message box if WebView2 is missing."""
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Microsoft Edge WebView2 Runtime is required but not found.\n\n"
            "Please download and install from:\n"
            "https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n\n"
            "App will continue running in tray mode.",
            "WebView2 Required",
            0x10  # MB_ICONERROR
        )
    except:
        logger.error("Could not show WebView2 missing message box")

# Import rest of app
try:
    import webview
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    
    from core.app_controller import AppController
    from features.auto_accept import AutoAcceptFeature
    
    WEBVIEW_AVAILABLE = True
except ImportError as e:
    logger.error(f"Import error: {e}")
    WEBVIEW_AVAILABLE = False

# Load config
def load_config():
    """Load configuration from yaml file."""
    config_file = Path('config.yaml')
    if config_file.exists():
        with open(config_file) as f:
            return yaml.safe_load(f)
    return {}

# Log handler for UI
class UILogHandler(logging.Handler):
    """Thread-safe log handler that forwards to UI."""
    
    def __init__(self, max_logs=100):
        super().__init__()
        self.logs = []
        self.max_logs = max_logs
        self.lock = threading.Lock()
        self._window_ref = None
    
    def set_window(self, win):
        """Set window reference for JS calls."""
        with self.lock:
            self._window_ref = win
    
    def clear_window(self):
        """Clear window reference when destroyed."""
        with self.lock:
            self._window_ref = None
    
    def emit(self, record):
        """Emit a log record."""
        try:
            # Simple format for UI: just message without timestamp/logger name
            msg = record.getMessage()
            level_map = {
                'DEBUG': 'info',
                'INFO': 'info',
                'WARNING': 'warning',
                'ERROR': 'error',
                'CRITICAL': 'error'
            }
            level = level_map.get(record.levelname, 'info')
            
            with self.lock:
                # Add to buffer with timestamp
                import datetime
                timestamp = datetime.datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
                self.logs.append({'level': level, 'message': msg, 'timestamp': timestamp})
                if len(self.logs) > self.max_logs:
                    self.logs.pop(0)
                
                # Forward to UI if window exists
                if self._window_ref:
                    try:
                        # Escape message for JS
                        safe_msg = msg.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                        self._window_ref.evaluate_js(f'window.addLog("{level}", "{safe_msg}")')
                    except:
                        pass  # Window may be closing
        except:
            pass  # Never fail on logging
    
    def get_logs(self):
        """Get current log buffer."""
        with self.lock:
            return list(self.logs)

# Global log handler
ui_log_handler = None

# API for pywebview
class API:
    """JavaScript API exposed to the UI."""
    
    def __init__(self, controller, log_handler):
        self.controller = controller
        self.log_handler = log_handler
    
    def get_state(self):
        """Get current application state."""
        return self.controller.get_state()
    
    def toggle_feature(self, feature_name):
        """Toggle a feature on/off."""
        return self.controller.toggle_feature(feature_name)
    
    def update_setting(self, feature_name, setting_name, value):
        """Update a feature setting."""
        return self.controller.update_feature_setting(feature_name, setting_name, value)
    
    def get_logs(self):
        """Get current log buffer."""
        return self.log_handler.get_logs()

# Global state
window = None
tray_icon = None
controller = None
config = None
ipc_socket = None

# IPC for single instance
IPC_PORT = 57847  # Random port for IPC

def check_single_instance():
    """Check if another instance is running and signal it."""
    global ipc_socket
    
    # Try to connect to existing instance
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(1)
        client.connect(('127.0.0.1', IPC_PORT))
        # If we connected, another instance exists
        client.send(b'SHOW_WINDOW')
        client.close()
        return False  # Another instance exists
    except:
        pass  # No existing instance
    
    # Create server socket to listen for future launches
    try:
        ipc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ipc_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ipc_socket.bind(('127.0.0.1', IPC_PORT))
        ipc_socket.listen(1)
        threading.Thread(target=ipc_server_thread, daemon=True).start()
        return True  # We are the first instance
    except:
        return False  # Port in use

def ipc_server_thread():
    """Listen for IPC commands from other instances."""
    global ipc_socket, window
    
    while True:
        try:
            client, _ = ipc_socket.accept()
            data = client.recv(1024)
            if data == b'SHOW_WINDOW':
                # Signal to open/show window
                if window is None:
                    threading.Thread(target=open_window, daemon=True).start()
                # TODO: bring window to front if already open (requires platform-specific code)
            client.close()
        except:
            break

# Tray icon
def create_tray_icon():
    """Create the system tray icon."""
    # Create a simple icon
    image = Image.new('RGB', (64, 64), color='#0ac8b9')
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 16, 48, 48], fill='#0a0e1a')
    
    def on_open():
        """Open the UI window."""
        global window
        if window is None:
            threading.Thread(target=open_window, daemon=True).start()
    
    def on_toggle_auto_accept():
        """Toggle auto-accept from tray."""
        global controller
        if controller:
            controller.toggle_feature('Auto-Accept')
    
    def on_quit():
        """Quit the application."""
        global controller, tray_icon
        logger.info("Quit requested from tray")
        if controller:
            controller.stop()
        if tray_icon:
            tray_icon.stop()
        sys.exit(0)
    
    menu = Menu(
        MenuItem('Open', on_open),
        MenuItem('Toggle Auto-Accept', on_toggle_auto_accept),
        MenuItem('Quit', on_quit)
    )
    
    return Icon('LoL Auto-Accept', image, menu=menu)

# Window management
def open_window():
    """Open the UI window."""
    global window, controller, ui_log_handler
    
    if not WEBVIEW_AVAILABLE:
        logger.error("Cannot open window: WebView not available")
        return
    
    if window is not None:
        logger.info("Window already exists")
        return
    
    try:
        # Determine UI path
        if getattr(sys, 'frozen', False):
            # PyInstaller bundle
            ui_path = os.path.join(sys._MEIPASS, 'ui', 'index.html')
        else:
            ui_path = os.path.join(os.path.dirname(__file__), 'ui', 'index.html')
        
        if not os.path.exists(ui_path):
            logger.error(f"UI file not found: {ui_path}")
            return
        
        logger.info(f"Opening window with UI from {ui_path}")
        
        api = API(controller, ui_log_handler)
        window = webview.create_window(
            'LoL Auto-Accept Helper',
            f'file://{ui_path}',
            js_api=api,
            width=750,
            height=800,
            resizable=True,
            min_size=(600, 600)
        )
        
        # Window loaded callback - set up log handler
        def on_loaded():
            global window, ui_log_handler
            if window and ui_log_handler:
                ui_log_handler.set_window(window)
                # Send initial log buffer
                for log in ui_log_handler.get_logs():
                    try:
                        safe_msg = log["message"].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                        window.evaluate_js(f'window.addLog("{log["level"]}", "{safe_msg}")')
                    except:
                        pass
        
        # Window closed callback
        def on_closed():
            global window, ui_log_handler
            logger.info("Window closed, destroying")
            if ui_log_handler:
                ui_log_handler.clear_window()
            window = None
        
        window.events.loaded += on_loaded
        window.events.closed += on_closed
        
        # Start webview (blocks until window closed)
        webview.start(debug=False)
        window = None
        logger.info("Window destroyed")
        
    except Exception as e:
        logger.error(f"Error opening window: {e}", exc_info=True)
        window = None

def main():
    """Main entry point."""
    global controller, tray_icon, config, window, ui_log_handler
    
    # Check for single instance
    if not check_single_instance():
        logger.info("Another instance is already running, signaling it to show window")
        sys.exit(0)
    
    # Load config
    config = load_config()
    start_minimized = config.get('start_minimized', False)
    
    # Set up UI log handler
    ui_log_handler = UILogHandler(max_logs=100)
    ui_log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(ui_log_handler)
    
    logger.info("=== LoL Auto-Accept Helper v0.2.0 (UI Mode) ===")
    
    # Check WebView2
    if not WEBVIEW_AVAILABLE:
        show_webview2_missing()
        logger.warning("Running in tray-only mode (no WebView2)")
    
    # Create controller
    controller = AppController(config)
    
    # Register features
    auto_accept = AutoAcceptFeature(config)
    auto_accept.enabled = config.get('auto_accept_enabled', True)
    controller.register_feature(auto_accept)
    
    # Start controller
    controller.start()
    logger.info("Controller started")
    
    # Create tray icon
    tray_icon = create_tray_icon()
    
    # Open window on start unless minimized
    if not start_minimized and WEBVIEW_AVAILABLE:
        threading.Thread(target=open_window, daemon=True).start()
        time.sleep(0.5)  # Give window thread time to start
    
    # Run tray icon (blocks)
    try:
        tray_icon.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        if controller:
            controller.stop()

if __name__ == '__main__':
    main()
