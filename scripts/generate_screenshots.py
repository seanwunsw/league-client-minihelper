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
        'features': [
            {
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
            },
            {
                'name': 'Champion Select',
                'enabled': True,
                'settings': {
                    'auto_ban_enabled': False,
                    'auto_pick_enabled': False,
                    'pick_mode': 'hover',
                    'role_preferences': {
                        'default': {'bans': [], 'picks': []},
                        'top': {'bans': [], 'picks': []},
                        'jungle': {'bans': [], 'picks': []},
                        'middle': {'bans': [], 'picks': []},
                        'bottom': {'bans': [], 'picks': []},
                        'utility': {'bans': [], 'picks': []}
                    }
                },
                'status': {
                    'enabled': True,
                    'auto_ban_enabled': False,
                    'auto_pick_enabled': False,
                    'champions': [
                        {'id': 1, 'name': 'Annie'},
                        {'id': 2, 'name': 'Olaf'},
                        {'id': 3, 'name': 'Galio'},
                        {'id': 266, 'name': 'Aatrox'},
                        {'id': 103, 'name': 'Ahri'}
                    ]
                }
            }
        ]
    },
    'connected': {
        'connection_state': 'connected',
        'gameflow_phase': 'Lobby',
        'client_info': {'port': 12345, 'install_dir': 'C:\\Riot Games\\League of Legends'},
        'features': [
            {
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
            },
            {
                'name': 'Champion Select',
                'enabled': True,
                'settings': {
                    'auto_ban_enabled': True,
                    'auto_pick_enabled': True,
                    'pick_mode': 'hover',
                    'role_preferences': {
                        'default': {'bans': [266, 64, 7], 'picks': [103, 84, 245]},
                        'top': {'bans': [266, 86, 24], 'picks': [86, 58, 24]},
                        'jungle': {'bans': [64, 104, 141], 'picks': [64, 104, 60]},
                        'middle': {'bans': [103, 238, 157], 'picks': [103, 238, 157]},
                        'bottom': {'bans': [523, 81, 22], 'picks': [523, 22, 81]},
                        'utility': {'bans': [555, 526, 412], 'picks': [555, 526, 497]}
                    }
                },
                'status': {
                    'enabled': True,
                    'auto_ban_enabled': True,
                    'auto_pick_enabled': True,
                    'champions': [
                        {'id': 1, 'name': 'Annie'},
                        {'id': 2, 'name': 'Olaf'},
                        {'id': 3, 'name': 'Galio'},
                        {'id': 7, 'name': 'LeBlanc'},
                        {'id': 22, 'name': 'Ashe'},
                        {'id': 24, 'name': 'Jax'},
                        {'id': 58, 'name': 'Renekton'},
                        {'id': 60, 'name': 'Elise'},
                        {'id': 64, 'name': 'Lee Sin'},
                        {'id': 81, 'name': 'Ezreal'},
                        {'id': 84, 'name': 'Akali'},
                        {'id': 86, 'name': 'Garen'},
                        {'id': 103, 'name': 'Ahri'},
                        {'id': 104, 'name': 'Graves'},
                        {'id': 141, 'name': 'Kayn'},
                        {'id': 157, 'name': 'Yasuo'},
                        {'id': 238, 'name': 'Zed'},
                        {'id': 245, 'name': 'Ekko'},
                        {'id': 266, 'name': 'Aatrox'},
                        {'id': 412, 'name': 'Thresh'},
                        {'id': 497, 'name': 'Rakan'},
                        {'id': 523, 'name': 'Aphelios'},
                        {'id': 526, 'name': 'Rell'},
                        {'id': 555, 'name': 'Pyke'}
                    ]
                }
            }
        ]
    },
    'champ_select': {
        'connection_state': 'connected',
        'gameflow_phase': 'ChampSelect',
        'client_info': {'port': 12345, 'install_dir': 'C:\\Riot Games\\League of Legends'},
        'features': [
            {
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
            },
            {
                'name': 'Champion Select',
                'enabled': True,
                'settings': {
                    'auto_ban_enabled': True,
                    'auto_pick_enabled': True,
                    'pick_mode': 'hover',
                    'role_preferences': {
                        'default': {'bans': [266, 64, 7], 'picks': [103, 84, 245]},
                        'top': {'bans': [266, 86, 24], 'picks': [86, 58, 24]},
                        'jungle': {'bans': [64, 104, 141], 'picks': [64, 104, 60]},
                        'middle': {'bans': [103, 238, 157], 'picks': [103, 238, 157]},
                        'bottom': {'bans': [523, 81, 22], 'picks': [523, 22, 81]},
                        'utility': {'bans': [555, 526, 412], 'picks': [555, 526, 497]}
                    }
                },
                'status': {
                    'enabled': True,
                    'auto_ban_enabled': True,
                    'auto_pick_enabled': True,
                    'champions': [
                        {'id': 1, 'name': 'Annie'},
                        {'id': 2, 'name': 'Olaf'},
                        {'id': 3, 'name': 'Galio'},
                        {'id': 7, 'name': 'LeBlanc'},
                        {'id': 22, 'name': 'Ashe'},
                        {'id': 24, 'name': 'Jax'},
                        {'id': 58, 'name': 'Renekton'},
                        {'id': 60, 'name': 'Elise'},
                        {'id': 64, 'name': 'Lee Sin'},
                        {'id': 81, 'name': 'Ezreal'},
                        {'id': 84, 'name': 'Akali'},
                        {'id': 86, 'name': 'Garen'},
                        {'id': 103, 'name': 'Ahri'},
                        {'id': 104, 'name': 'Graves'},
                        {'id': 141, 'name': 'Kayn'},
                        {'id': 157, 'name': 'Yasuo'},
                        {'id': 238, 'name': 'Zed'},
                        {'id': 245, 'name': 'Ekko'},
                        {'id': 266, 'name': 'Aatrox'},
                        {'id': 412, 'name': 'Thresh'},
                        {'id': 497, 'name': 'Rakan'},
                        {'id': 523, 'name': 'Aphelios'},
                        {'id': 526, 'name': 'Rell'},
                        {'id': 555, 'name': 'Pyke'}
                    ]
                }
            }
        ]
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
            
            page = browser.new_page(viewport={'width': 750, 'height': 900})
            
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
            
            # For connected and champ_select states, verify dropdowns are visible
            if state_name in ['connected', 'champ_select']:
                # Wait for champion select dropdowns to be present
                page.wait_for_selector('.champ-select', timeout=5000)
                
                # Check that ban/pick selects are visible in viewport
                ban_selects = page.locator('.champ-select[data-type="ban"]')
                pick_selects = page.locator('.champ-select[data-type="pick"]')
                
                # Verify at least one ban and one pick select is visible
                assert ban_selects.first.is_visible(), f"Ban selects not visible in {state_name}"
                assert pick_selects.first.is_visible(), f"Pick selects not visible in {state_name}"
                
                # Check that content fits without scrolling
                scroll_height = page.evaluate('document.documentElement.scrollHeight')
                window_height = page.evaluate('window.innerHeight')
                
                print(f"  Scroll height: {scroll_height}px, Window height: {window_height}px")
                
                if scroll_height > window_height:
                    print(f"  WARNING: Content overflows (scroll height {scroll_height}px > window {window_height}px)")
                    # Allow small overflow for rounding
                    assert scroll_height <= window_height + 5, f"Content does not fit in viewport for {state_name}"
                else:
                    print(f"  ✓ Content fits without scrolling")
            
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
