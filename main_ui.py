"""
LoL Auto-Accept Helper with pywebview UI
"""
import os
import sys
import logging
import threading
import time
import ctypes
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

# API for pywebview
class API:
    """JavaScript API exposed to the UI."""
    
    def __init__(self, controller):
        self.controller = controller
    
    def get_state(self):
        """Get current application state."""
        return self.controller.get_state()
    
    def toggle_feature(self, feature_name):
        """Toggle a feature on/off."""
        return self.controller.toggle_feature(feature_name)
    
    def update_setting(self, feature_name, setting_name, value):
        """Update a feature setting."""
        return self.controller.update_feature_setting(feature_name, setting_name, value)

# Global state
window = None
tray_icon = None
controller = None
config = None

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
    global window, controller
    
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
        
        api = API(controller)
        window = webview.create_window(
            'LoL Auto-Accept Helper',
            f'file://{ui_path}',
            js_api=api,
            width=750,
            height=800,
            resizable=True,
            min_size=(600, 600)
        )
        
        # Window closed callback
        def on_closed():
            global window
            logger.info("Window closed, destroying")
            window = None
        
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
    global controller, tray_icon, config, window
    
    # Load config
    config = load_config()
    start_minimized = config.get('start_minimized', False)
    
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
