"""Generate UI screenshots with mock states using Playwright."""
import os
import sys
from pathlib import Path

# Install playwright if needed
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Installing playwright...")
    os.system("pip install playwright")
    os.system("playwright install chromium")
    from playwright.sync_api import sync_playwright

# Mock states
STATES = {
    'disconnected': {
        'connection_state': 'disconnected',
        'gameflow_phase': 'None',
        'client_info': None,
        'features': [{
            'name': 'Auto-Accept',
            'enabled': True,
            'settings': {
                'accept_delay_min_seconds': 1,
                'accept_delay_max_seconds': 4
            },
            'status': {
                'enabled': True,
                'accept_history': []
            }
        }]
    },
    'connected': {
        'connection_state': 'connected',
        'gameflow_phase': 'Lobby',
        'client_info': {'port': 12345, 'install_dir': 'C:\\Riot Games\\League of Legends'},
        'features': [{
            'name': 'Auto-Accept',
            'enabled': True,
            'settings': {
                'accept_delay_min_seconds': 1,
                'accept_delay_max_seconds': 4
            },
            'status': {
                'enabled': True,
                'accept_history': [
                    {'timestamp': '2026-10-10T14:23:45', 'delay': 2.34},
                    {'timestamp': '2026-10-10T14:20:12', 'delay': 3.67},
                    {'timestamp': '2026-10-10T14:18:03', 'delay': 1.89}
                ]
            }
        }]
    },
    'ready_check': {
        'connection_state': 'connected',
        'gameflow_phase': 'ReadyCheck',
        'client_info': {'port': 12345, 'install_dir': 'C:\\Riot Games\\League of Legends'},
        'features': [{
            'name': 'Auto-Accept',
            'enabled': True,
            'settings': {
                'accept_delay_min_seconds': 1,
                'accept_delay_max_seconds': 4
            },
            'status': {
                'enabled': True,
                'accept_history': [
                    {'timestamp': '2026-10-10T14:23:45', 'delay': 2.34},
                    {'timestamp': '2026-10-10T14:20:12', 'delay': 3.67},
                    {'timestamp': '2026-10-10T14:18:03', 'delay': 1.89},
                    {'timestamp': '2026-10-10T14:15:22', 'delay': 2.91}
                ]
            }
        }]
    }
}

def generate_screenshots():
    """Generate screenshots for different states."""
    # Get UI path
    ui_path = Path(__file__).parent.parent / 'ui' / 'index.html'
    if not ui_path.exists():
        print(f"Error: UI file not found at {ui_path}")
        return False
    
    # Create screenshots directory
    screenshots_dir = Path(__file__).parent.parent / 'screenshots'
    screenshots_dir.mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        for state_name, state_data in STATES.items():
            print(f"Generating screenshot for {state_name}...")
            
            page = browser.new_page(viewport={'width': 750, 'height': 800})
            
            # Mock window.pywebview.api
            page.add_init_script(f"""
                window.pywebview = {{
                    api: {{
                        get_state: () => Promise.resolve({str(state_data).replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null')}),
                        toggle_feature: () => Promise.resolve(true),
                        update_setting: () => Promise.resolve(true),
                        get_logs: () => Promise.resolve([
                            {{"level": "info", "message": "Application started", "timestamp": "14:20:00"}},
                            {{"level": "info", "message": "Client detected at port 12345", "timestamp": "14:20:01"}},
                            {{"level": "info", "message": "Successfully connected to League Client", "timestamp": "14:20:02"}},
                            {{"level": "info", "message": "Gameflow phase: {state_data['gameflow_phase']}", "timestamp": "14:20:03"}}
                        ])
                    }}
                }};
            """)
            
            # Load page
            page.goto(f'file://{ui_path.absolute()}')
            
            # Wait for content to load
            page.wait_for_timeout(1000)
            
            # Take screenshot
            screenshot_path = screenshots_dir / f'{state_name}.png'
            page.screenshot(path=str(screenshot_path))
            print(f"  Saved to {screenshot_path}")
            
            page.close()
        
        browser.close()
    
    print(f"\nGenerated {len(STATES)} screenshots in {screenshots_dir}")
    return True

if __name__ == '__main__':
    success = generate_screenshots()
    sys.exit(0 if success else 1)
