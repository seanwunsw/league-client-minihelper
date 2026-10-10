"""
LoL Auto-Accept Helper with pywebview UI
Threading model: pywebview on MAIN thread, pystray in background thread
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import threading
import time
import ctypes
import socket
from pathlib import Path
from queue import Queue, Empty
import yaml
import traceback

# Determine app directory first (before any file operations)
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Change to app directory so relative paths work
os.chdir(APP_DIR)

# Global state
controller = None
tray_icon = None
window = None
ui_log_handler = None
webview_ready = threading.Event()

# Check for WebView2
def check_webview2():
    """Check if WebView2 runtime is available."""
    try:
        import webview
        return True
    except Exception as e:
        return False

# Import dependencies
try:
    import webview
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    
    from core.app_controller import AppController
    from features.auto_accept import AutoAcceptFeature
    
    WEBVIEW_AVAILABLE = True
except ImportError as e:
    print(f"Import error: {e}")
    WEBVIEW_AVAILABLE = False

def show_error_box(title, message):
    """Show error message box on Windows."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except:
        print(f"{title}: {message}")

def load_config():
    """Load configuration from yaml file in app directory."""
    config_file = os.path.join(APP_DIR, 'config.yaml')
    default_config = {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4,
        'start_minimized': False,
        'log_level': 'INFO'
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    default_config.update(loaded)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
    
    return default_config

def setup_logging(config):
    """Setup logging with rotating file handler."""
    log_level_str = config.get('log_level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    log_file = os.path.join(APP_DIR, "LoLAutoAccept.log")
    
    # Clear any existing handlers
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(log_level)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Rotating file handler (5MB max, 3 backups)
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create log file: {e}")
    
    return logging.getLogger(__name__)

# Log handler for UI
class UILogHandler(logging.Handler):
    """Thread-safe log handler that queues messages for UI."""
    
    def __init__(self, max_logs=100):
        super().__init__()
        self.logs = []
        self.max_logs = max_logs
        self._buf_lock = threading.Lock()
        self.message_queue = Queue()
        self._window_ref = None
    
    def set_window(self, win):
        """Set window reference for JS calls."""
        with self._buf_lock:
            self._window_ref = win
    
    def clear_window(self):
        """Clear window reference when destroyed."""
        with self._buf_lock:
            self._window_ref = None
    
    def emit(self, record):
        """Emit a log record - queue it for processing."""
        try:
            msg = record.getMessage()
            level_map = {
                'DEBUG': 'info',
                'INFO': 'info',
                'WARNING': 'warning',
                'ERROR': 'error',
                'CRITICAL': 'error'
            }
            level = level_map.get(record.levelname, 'info')
            
            import datetime
            timestamp = datetime.datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            
            with self._buf_lock:
                # Add to buffer
                self.logs.append({'level': level, 'message': msg, 'timestamp': timestamp})
                if len(self.logs) > self.max_logs:
                    self.logs.pop(0)
            
            # Queue for UI update (non-blocking)
            self.message_queue.put_nowait({'level': level, 'message': msg, 'timestamp': timestamp})
        except:
            pass  # Never fail on logging
    
    def drain_messages(self):
        """Drain queued messages and send to UI (call from GUI thread)."""
        with self._buf_lock:
            win = self._window_ref
        
        if not win:
            return
        
        messages = []
        try:
            while True:
                messages.append(self.message_queue.get_nowait())
        except Empty:
            pass
        
        for msg in messages:
            try:
                safe_msg = msg['message'].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                win.evaluate_js(f'window.addLog("{msg["level"]}", "{safe_msg}")')
            except:
                pass  # Window may be closing
    
    def get_logs(self):
        """Get current log buffer."""
        with self._buf_lock:
            return list(self.logs)

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

# IPC for single instance
IPC_PORT = 57847

def check_single_instance():
    """Check if another instance is running and signal it. Returns socket if first instance."""
    # Try to connect to existing instance
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(0.5)
        client.connect(('127.0.0.1', IPC_PORT))
        client.send(b'SHOW_WINDOW')
        client.close()
        return None  # Another instance exists
    except:
        pass  # No existing instance
    
    # Create server socket to listen for future launches
    try:
        ipc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ipc_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ipc_socket.bind(('127.0.0.1', IPC_PORT))
        ipc_socket.listen(1)
        ipc_socket.settimeout(1.0)  # Non-blocking with timeout
        return ipc_socket
    except Exception as e:
        logging.getLogger(__name__).warning(f"Could not create IPC socket: {e}")
        return None

def ipc_server_thread(ipc_socket):
    """Listen for IPC commands from other instances."""
    logger = logging.getLogger(__name__)
    while True:
        try:
            client, _ = ipc_socket.accept()
            data = client.recv(1024)
            if data == b'SHOW_WINDOW':
                logger.info("IPC: Request to show window")
                # Trigger tray open action
                # Since we can't easily call tray menu items programmatically,
                # we'll just create the window directly
                global window
                if window is None and webview_ready.is_set():
                    try:
                        # Determine UI path
                        if getattr(sys, 'frozen', False):
                            ui_path = os.path.join(sys._MEIPASS, 'ui', 'index.html')
                        else:
                            ui_path = os.path.join(APP_DIR, 'ui', 'index.html')
                        
                        # Create window (same as tray on_open logic)
                        api = API(controller, ui_log_handler)
                        new_window = webview.create_window(
                            'LoL Auto-Accept Helper',
                            f'file://{ui_path}',
                            js_api=api,
                            width=750,
                            height=800,
                            resizable=True,
                            min_size=(600, 600)
                        )
                        
                        def on_loaded():
                            global window, ui_log_handler
                            logger.info("Window loaded (from IPC)")
                            window = new_window
                            if window and ui_log_handler:
                                ui_log_handler.set_window(window)
                        
                        def on_closed():
                            global window, ui_log_handler
                            logger.info("Window closed (from IPC)")
                            if ui_log_handler:
                                ui_log_handler.clear_window()
                            window = None
                        
                        new_window.events.loaded += on_loaded
                        new_window.events.closed += on_closed
                    except Exception as e:
                        logger.error(f"Error creating window from IPC: {e}")
            client.close()
        except socket.timeout:
            continue
        except:
            break

# Tray icon
def create_tray_icon():
    """Create the system tray icon."""
    image = Image.new('RGB', (64, 64), color='#0ac8b9')
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 16, 48, 48], fill='#0a0e1a')
    
    def on_open():
        """Open the UI window."""
        global window, controller, ui_log_handler, keeper_window
        logger = logging.getLogger(__name__)
        
        # Don't open if window already exists
        if window is not None:
            logger.info("Window already open")
            return
        
        # Wait for webview to be ready
        if not webview_ready.wait(timeout=5):
            logger.error("Webview not ready")
            return
        
        logger.info("Creating window from tray")
        
        # Determine UI path
        if getattr(sys, 'frozen', False):
            ui_path = os.path.join(sys._MEIPASS, 'ui', 'index.html')
        else:
            ui_path = os.path.join(APP_DIR, 'ui', 'index.html')
        
        # Create API
        api = API(controller, ui_log_handler)
        
        # Create window (thread-safe call after webview.start())
        new_window = webview.create_window(
            'LoL Auto-Accept Helper',
            f'file://{ui_path}',
            js_api=api,
            width=750,
            height=800,
            resizable=True,
            min_size=(600, 600)
        )
        
        def on_loaded():
            global window, ui_log_handler
            logger.info("Window loaded (from tray)")
            window = new_window
            if window and ui_log_handler:
                ui_log_handler.set_window(window)
                # Send initial logs
                for log in ui_log_handler.get_logs():
                    try:
                        safe_msg = log["message"].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                        window.evaluate_js(f'window.addLog("{log["level"]}", "{safe_msg}")')
                    except:
                        pass
        
        def on_closed():
            global window, ui_log_handler
            logger.info("Window closed (from tray)")
            if ui_log_handler:
                ui_log_handler.clear_window()
            window = None
        
        new_window.events.loaded += on_loaded
        new_window.events.closed += on_closed
    
    def on_toggle_auto_accept():
        """Toggle auto-accept from tray."""
        global controller
        if controller:
            controller.toggle_feature('Auto-Accept')
    
    def on_quit():
        """Quit the application."""
        global controller, tray_icon, keeper_window
        logger = logging.getLogger(__name__)
        logger.info("Quit requested from tray")
        
        # Destroy keeper window to exit webview loop
        if keeper_window:
            keeper_window.destroy()
        
        # Stop controller
        if controller:
            controller.stop()
        
        # Stop tray (will exit the tray thread)
        if tray_icon:
            tray_icon.stop()
    
    menu = Menu(
        MenuItem('Open', on_open),
        MenuItem('Toggle Auto-Accept', on_toggle_auto_accept),
        MenuItem('Quit', on_quit)
    )
    
    return Icon('LoL Auto-Accept', image, menu=menu)

keeper_window = None  # Hidden window to keep GUI loop alive

def webview_thread_main(config, logger):
    """Main thread function: runs pywebview event loop."""
    global window, controller, ui_log_handler, keeper_window
    
    try:
        # Determine UI path
        if getattr(sys, 'frozen', False):
            ui_path = os.path.join(sys._MEIPASS, 'ui', 'index.html')
        else:
            ui_path = os.path.join(APP_DIR, 'ui', 'index.html')
        
        if not os.path.exists(ui_path):
            logger.error(f"UI file not found at {ui_path}")
            show_error_box("Error", f"UI file not found: {ui_path}")
            return
        
        logger.info(f"UI path: {ui_path}")
        
        # Create API
        api = API(controller, ui_log_handler)
        
        start_minimized = config.get('start_minimized', False)
        
        # Create a hidden keeper window to keep the GUI loop alive
        # This ensures webview.start() doesn't exit when user closes the visible window
        keeper_window = webview.create_window(
            'LoL Auto-Accept Keeper',
            'about:blank',
            width=1,
            height=1,
            x=-1000,
            y=-1000,
            resizable=False,
            minimized=True,
            hidden=True
        )
        logger.info("Created keeper window")
        
        # Create visible window if not start_minimized
        if not start_minimized:
            logger.info("Creating main window (start_minimized=False)")
            window = webview.create_window(
                'LoL Auto-Accept Helper',
                f'file://{ui_path}',
                js_api=api,
                width=750,
                height=800,
                resizable=True,
                min_size=(600, 700)
            )
            
            def on_shown():
                logger.info("Main window shown (visible)")
            
            def on_loaded():
                global window, ui_log_handler
                logger.info("Main window loaded (DOM ready)")
                if window and ui_log_handler:
                    ui_log_handler.set_window(window)
                    # Send initial logs
                    for log in ui_log_handler.get_logs():
                        try:
                            safe_msg = log["message"].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                            window.evaluate_js(f'window.addLog("{log["level"]}", "{safe_msg}")')
                        except:
                            pass
            
            def on_closed():
                global window, ui_log_handler
                logger.info("Main window closed by user (X button)")
                if ui_log_handler:
                    ui_log_handler.clear_window()
                window = None
            
            window.events.shown += on_shown
            window.events.loaded += on_loaded
            window.events.closed += on_closed
        else:
            logger.info("Skipping main window creation (start_minimized=True)")
        
        webview_ready.set()
        logger.info("Webview ready, starting GUI loop")
        
        # Start webview (blocks on main thread)
        # The keeper window ensures this doesn't exit until we explicitly destroy it
        webview.start(debug=False)
        
        logger.info("Webview GUI loop exited")
        
    except Exception as e:
        logger.error(f"Error in webview thread: {e}", exc_info=True)
        show_error_box("Webview Error", f"Failed to start UI:\n{e}\n\nCheck LoLAutoAccept.log for details.")


def main():
    """Main entry point."""
    global controller, tray_icon, ui_log_handler
    
    try:
        # Load config first
        config = load_config()
        
        # Setup logging
        logger = setup_logging(config)
        
        logger.info("=== LoL Auto-Accept Helper v0.2.0 (UI Mode) ===")
        logger.info(f"App directory: {APP_DIR}")
        
        # Check for single instance
        ipc_socket = check_single_instance()
        if ipc_socket is None:
            logger.info("Another instance is already running, signaling it to show window")
            # Socket creation failed or another instance responded - exit
            time.sleep(1)  # Give other instance time to show window
            return 0
        
        logger.info("First instance, continuing startup")
        
        # Start IPC server in background
        logger.info("Starting IPC server")
        if ipc_socket:
            threading.Thread(target=ipc_server_thread, args=(ipc_socket,), daemon=True).start()
            logger.info("IPC server thread started")
        
        # Check WebView2
        logger.info(f"WebView available: {WEBVIEW_AVAILABLE}")
        if not WEBVIEW_AVAILABLE:
            logger.warning("WebView2 not available, running in tray-only mode")
            show_error_box(
                "WebView2 Required",
                "Microsoft Edge WebView2 Runtime is required but not found.\n\n"
                "Please download and install from:\n"
                "https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n\n"
                "App will continue running in tray mode."
            )
        
        # Set up UI log handler
        logger.info("Setting up UI log handler")
        ui_log_handler = UILogHandler(max_logs=100)
        logging.getLogger().addHandler(ui_log_handler)
        logger.info("UI log handler added")
        
        # Create controller
        logger.info("Creating controller")
        controller = AppController(config)
        logger.info("Controller created")
        
        # Register features
        auto_accept = AutoAcceptFeature(config)
        auto_accept.enabled = config.get('auto_accept_enabled', True)
        controller.register_feature(auto_accept)
        logger.info("Features registered")
        
        # Start controller (non-blocking - runs connection loop in background thread)
        controller.start()
        logger.info("Controller started")
        
        # Create tray icon and run in background thread
        tray_icon = create_tray_icon()
        logger.info("Tray icon created")
        
        # Start tray in background thread
        tray_thread = threading.Thread(target=tray_icon.run, daemon=False)
        tray_thread.start()
        logger.info("Tray thread started")
        
        # Run webview on main thread if available
        if WEBVIEW_AVAILABLE:
            logger.info("Starting webview on main thread")
            webview_thread_main(config, logger)
            logger.info("Webview exited")
        else:
            # No webview, just wait
            logger.info("No webview available, waiting for tray")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Interrupted")
        
        # Cleanup (will only reach here when keeper window destroyed or webview unavailable)
        logger.info("Shutting down")
        if controller:
            controller.stop()
        if tray_icon:
            tray_icon.stop()
        
        return 0
        
    except Exception as e:
        error_msg = f"Fatal error: {e}\n\n{traceback.format_exc()}"
        print(error_msg)
        try:
            with open(os.path.join(APP_DIR, "crash.log"), "w") as f:
                f.write(error_msg)
        except:
            pass
        show_error_box("Fatal Error", f"Application crashed:\n\n{e}\n\nSee crash.log for details.")
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        # If main() fails before logging setup, write to emergency log
        try:
            emergency_log = os.path.join(APP_DIR, "emergency.log")
            with open(emergency_log, "w") as f:
                f.write(f"Emergency: Failed to start\n")
                f.write(f"Error: {e}\n")
                f.write(traceback.format_exc())
        except:
            pass
        # Try to show error box
        try:
            ctypes.windll.user32.MessageBoxW(0, f"Failed to start:\n{e}", "Error", 0x10)
        except:
            pass
        sys.exit(1)
