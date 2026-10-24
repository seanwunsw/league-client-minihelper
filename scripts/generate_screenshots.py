"""Generate UI screenshots with mock states using Playwright."""
import json
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

# Mock champion list with bilingual names (English + Traditional Chinese)
MOCK_CHAMPIONS = [
    {'id': 1, 'name': 'Annie 安妮'},
    {'id': 2, 'name': 'Olaf 歐拉夫'},
    {'id': 3, 'name': 'Galio 加里歐'},
    {'id': 4, 'name': 'Twisted Fate 逆命'},
    {'id': 5, 'name': 'Xin Zhao 趙信'},
    {'id': 7, 'name': 'LeBlanc 勒布朗'},
    {'id': 22, 'name': 'Ashe 艾希'},
    {'id': 24, 'name': 'Jax 賈克斯'},
    {'id': 58, 'name': 'Renekton 雷尼克頓'},
    {'id': 60, 'name': 'Elise 伊莉絲'},
    {'id': 64, 'name': 'Lee Sin 李星'},
    {'id': 81, 'name': 'Ezreal 伊澤瑞爾'},
    {'id': 84, 'name': 'Akali 阿卡莉'},
    {'id': 86, 'name': 'Garen 蓋倫'},
    {'id': 103, 'name': 'Ahri 阿璃'},
    {'id': 104, 'name': 'Graves 葛雷夫'},
    {'id': 141, 'name': 'Kayn 慨影'},
    {'id': 157, 'name': 'Yasuo 犽宿'},
    {'id': 238, 'name': 'Zed 劫'},
    {'id': 245, 'name': 'Ekko 艾克'},
    {'id': 266, 'name': 'Aatrox 厄薩斯'},
    {'id': 412, 'name': 'Thresh 瑟雷西'},
    {'id': 497, 'name': 'Rakan 銳空'},
    {'id': 523, 'name': 'Aphelios 亞菲利歐'},
    {'id': 526, 'name': 'Rell 銳兒'},
    {'id': 555, 'name': 'Pyke 派克'}
]

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
                    'champions': MOCK_CHAMPIONS[:5]
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
                    'ban_delay_min_seconds': 1.0,
                    'ban_delay_max_seconds': 3.0,
                    'pick_delay_min_seconds': 1.0,
                    'pick_delay_max_seconds': 3.0,
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
                    'champions': MOCK_CHAMPIONS
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
                    'ban_delay_min_seconds': 1.0,
                    'ban_delay_max_seconds': 3.0,
                    'pick_delay_min_seconds': 1.0,
                    'pick_delay_max_seconds': 3.0,
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
                    'champions': MOCK_CHAMPIONS
                }
            }
        ]
    },
    'ready_check': {
        'connection_state': 'connected',
        'gameflow_phase': 'ReadyCheck',
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
                    'auto_ban_enabled': True,
                    'auto_pick_enabled': True,
                    'champions': MOCK_CHAMPIONS
                }
            }
        ]
    }
}

DEFAULT_APP_SETTINGS = {
    'close_action': 'exit',
    'start_with_windows': False,
    'start_with_windows_available': True,
    'start_with_windows_note': None,
    'startup_method': 'hkcu_run',
    'requires_admin_elevation': False,
}


def install_ui_mock(page, state_data, logs):
    """Install a stateful pywebview mock so settings changes stick."""
    payload = dict(state_data)
    payload.setdefault('app_settings', DEFAULT_APP_SETTINGS)
    script = """
window.__mockState = %s;
window.__mockLogs = %s;
window.pywebview = {
  api: {
    get_state: () => Promise.resolve(JSON.parse(JSON.stringify(window.__mockState))),
    toggle_feature: () => Promise.resolve(true),
    update_setting: () => Promise.resolve(true),
    get_logs: () => Promise.resolve(window.__mockLogs),
    set_close_action: (action) => {
      window.__mockState.app_settings.close_action = action;
      return Promise.resolve(true);
    },
    set_start_with_windows: (enabled) => {
      window.__mockState.app_settings.start_with_windows = !!enabled;
      return Promise.resolve({ok: true, available: true, enabled: !!enabled, message: null});
    }
  }
};
""" % (json.dumps(payload), json.dumps(logs))
    page.add_init_script(script)


def assert_main_window_does_not_scroll(page, label):
    """The window itself must not scroll. Only the log view may."""
    metrics = page.evaluate('''() => {
        const scrolling = [];
        for (const el of document.querySelectorAll('*')) {
            const style = getComputedStyle(el);
            const oy = style.overflowY;
            if ((oy === 'auto' || oy === 'scroll') && el.scrollHeight > el.clientHeight + 1) {
                scrolling.push(el.id || el.className || el.tagName);
            }
        }
        return {
            scrollHeight: document.documentElement.scrollHeight,
            innerHeight: window.innerHeight,
            scrolling
        };
    }''')
    print(f"  Scroll height: {metrics['scrollHeight']}px, window: {metrics['innerHeight']}px, scrolling: {metrics['scrolling']}")
    assert metrics['scrollHeight'] <= metrics['innerHeight'] + 5, f"{label} page scrolls: {metrics}"
    unexpected = [name for name in metrics['scrolling'] if 'log-view' not in str(name)]
    assert not unexpected, f"{label} has extra scroll regions: {unexpected}"


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
            
            install_ui_mock(page, state_data, [
                {"level": "info", "message": "Application started", "timestamp": "14:20:00"},
                {"level": "info", "message": "Client detected at port 12345", "timestamp": "14:20:01"},
                {"level": "info", "message": "Successfully connected to League Client", "timestamp": "14:20:02"},
                {"level": "info", "message": f"Gameflow phase: {state_data['gameflow_phase']}", "timestamp": "14:20:03"},
            ])
            
            # Load page
            page.goto(f'file://{ui_path.absolute()}')
            
            # Wait for content to load
            page.wait_for_timeout(1500)
            
            # For connected and champ_select states, verify comboboxes are visible
            if state_name in ['connected', 'champ_select']:
                # Wait for comboboxes to be present
                page.wait_for_selector('.combobox-container', timeout=5000)
                
                # Check that ban/pick comboboxes are visible in viewport
                ban_comboboxes = page.locator('.combobox-container[data-type="ban"]')
                pick_comboboxes = page.locator('.combobox-container[data-type="pick"]')
                
                # Verify at least one ban and one pick combobox is visible
                assert ban_comboboxes.first.is_visible(), f"Ban comboboxes not visible in {state_name}"
                assert pick_comboboxes.first.is_visible(), f"Pick comboboxes not visible in {state_name}"
                
                assert_main_window_does_not_scroll(page, state_name)
                print("  [OK] Content fits without scrolling")
            
            # Take screenshot
            screenshot_path = screenshots_dir / f'{state_name}.png'
            page.screenshot(path=str(screenshot_path))
            print(f"  Saved to {screenshot_path}")
            
            page.close()
        
        # Generate special screenshot with combobox open showing Chinese search
        print("Generating screenshot with combobox open (Chinese search)...")
        page = browser.new_page(viewport={'width': 750, 'height': 900})
        
        state_data = STATES['champ_select']
        install_ui_mock(page, state_data, [
            {"level": "info", "message": "Champ select: assigned role = middle, using Middle list", "timestamp": "14:20:05"},
            {"level": "info", "message": "Auto-ban: waiting 2.3s before banning Aatrox 厄薩斯", "timestamp": "14:20:06"},
            {"level": "info", "message": "[OK] Successfully banned Aatrox 厄薩斯", "timestamp": "14:20:09"},
            {"level": "info", "message": "Auto-pick: waiting 1.7s before hovering Ahri 阿璃", "timestamp": "14:20:15"},
            {"level": "info", "message": "[OK] Successfully hovered Ahri 阿璃", "timestamp": "14:20:17"},
        ])
        
        page.goto(f'file://{ui_path.absolute()}')
        page.wait_for_timeout(1500)
        
        # Click on first pick combobox to open it
        first_pick_input = page.locator('.combobox-container[data-type="pick"][data-priority="1"] .combobox-input').first
        first_pick_input.click()
        page.wait_for_timeout(500)
        
        # Type Chinese character to filter
        first_pick_input.fill('阿')
        page.wait_for_timeout(500)
        
        # Take screenshot
        screenshot_path = screenshots_dir / 'champ_select_search.png'
        page.screenshot(path=str(screenshot_path))
        print(f"  Saved to {screenshot_path}")
        
        page.close()

        print("Generating screenshot with settings panel open...")
        page = browser.new_page(viewport={'width': 750, 'height': 900})
        install_ui_mock(page, STATES['connected'], [
            {"level": "info", "message": "Application started", "timestamp": "14:20:00"},
            {"level": "info", "message": "Close action: exit (window X quits the app)", "timestamp": "14:20:01"},
            {"level": "info", "message": "Start with Windows is off", "timestamp": "14:20:02"},
        ])
        page.goto(f'file://{ui_path.absolute()}')
        page.wait_for_timeout(800)
        page.click('#settings-button')
        page.wait_for_selector('#settings-panel', state='visible')
        page.wait_for_timeout(200)
        assert page.locator('#close-action-exit').is_checked()
        assert page.locator('#start-with-windows').is_checked() is False
        default_path = screenshots_dir / 'settings.png'
        page.screenshot(path=str(default_path))
        print(f"  Saved to {default_path}")

        page.click('#close-action-tray')
        page.click('#start-with-windows')
        page.wait_for_timeout(400)

        assert page.locator('#close-action-tray').is_checked()
        assert page.locator('#start-with-windows').is_checked()
        assert page.locator('#settings-panel').is_visible()
        assert_main_window_does_not_scroll(page, 'settings')

        # Log is the only region allowed to scroll; give it enough lines to prove that.
        page.evaluate('''() => {
            for (let i = 0; i < 30; i++) window.addLog('info', 'Log line ' + i);
        }''')
        page.wait_for_timeout(200)
        log_overflow = page.evaluate('''() => {
            const log = document.getElementById('log-view');
            const body = getComputedStyle(document.body).overflowY;
            return {
                logScrolls: log.scrollHeight > log.clientHeight,
                bodyOverflow: body,
                pageScrolls: document.documentElement.scrollHeight > window.innerHeight + 5
            };
        }''')
        assert log_overflow['logScrolls'], log_overflow
        assert log_overflow['bodyOverflow'] == 'hidden', log_overflow
        assert log_overflow['pageScrolls'] is False, log_overflow

        screenshot_path = screenshots_dir / 'settings-updated.png'
        page.screenshot(path=str(screenshot_path))
        print(f"  Saved to {screenshot_path}")
        page.close()
        browser.close()
    
    print(f"\nGenerated {len(STATES) + 3} screenshots in {screenshots_dir}")
    return True

if __name__ == '__main__':
    success = generate_screenshots()
    sys.exit(0 if success else 1)
