"""Defaults, backward compatible config loading, and the --minimized flag."""
from pathlib import Path

import yaml

from core.app_settings import (
    apply_app_setting_defaults,
    load_config_file,
    normalize_close_action,
    should_start_minimized,
)
from core.windows_startup import REQUIRES_ADMIN_ELEVATION


def test_missing_shell_keys_get_defaults_without_dropping_old_keys():
    legacy = {
        'auto_accept_enabled': False,
        'accept_delay_min_seconds': 2,
        'accept_delay_max_seconds': 5,
        'accept_delay_seconds': 2,
        'log_level': 'WARNING',
        'champ_select_preferences': {'default': {'bans': [1], 'picks': [2]}},
    }
    merged = apply_app_setting_defaults(dict(legacy))

    assert merged['close_action'] == 'exit'
    assert merged['start_with_windows'] is False
    assert merged['auto_accept_enabled'] is False
    assert merged['accept_delay_min_seconds'] == 2
    assert merged['accept_delay_seconds'] == 2
    assert merged['log_level'] == 'WARNING'
    assert merged['champ_select_preferences']['default']['bans'] == [1]


def test_explicit_shell_settings_are_kept():
    config = apply_app_setting_defaults({
        'close_action': 'TRAY',
        'start_with_windows': True,
        'auto_accept_enabled': True,
    })
    assert config['close_action'] == 'tray'
    assert config['start_with_windows'] is True


def test_invalid_close_action_falls_back_to_exit():
    assert normalize_close_action('minimize') == 'exit'
    assert normalize_close_action(None) == 'exit'
    assert normalize_close_action('tray') == 'tray'
    config = apply_app_setting_defaults({'close_action': 'hide', 'start_with_windows': 'no'})
    assert config['close_action'] == 'exit'
    assert config['start_with_windows'] is False


def test_load_config_file_back_compat(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text(
        yaml.safe_dump({
            'auto_accept_enabled': True,
            'accept_delay_min_seconds': 3,
            'start_minimized': False,
        }),
        encoding='utf-8',
    )

    loaded = load_config_file(str(path))
    assert loaded['close_action'] == 'exit'
    assert loaded['start_with_windows'] is False
    assert loaded['accept_delay_min_seconds'] == 3
    assert loaded['start_minimized'] is False
    assert loaded['auto_accept_enabled'] is True


def test_load_config_file_reads_new_keys(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text(
        "close_action: tray\nstart_with_windows: true\nauto_accept_enabled: false\n",
        encoding='utf-8',
    )
    loaded = load_config_file(str(path))
    assert loaded['close_action'] == 'tray'
    assert loaded['start_with_windows'] is True
    assert loaded['auto_accept_enabled'] is False


def test_missing_config_file_uses_defaults(tmp_path):
    loaded = load_config_file(str(tmp_path / 'missing.yaml'))
    assert loaded['close_action'] == 'exit'
    assert loaded['start_with_windows'] is False
    assert loaded['start_minimized'] is False
    assert loaded['auto_accept_enabled'] is True


def test_minimized_flag_hides_window_without_changing_manual_launch():
    config = {'start_minimized': False, 'start_with_windows': True}
    assert should_start_minimized(config, ['LoLAutoAccept.exe']) is False
    assert should_start_minimized(config, ['LoLAutoAccept.exe', '--minimized']) is True
    assert should_start_minimized({'start_minimized': True}, ['app']) is True
    assert should_start_minimized(config, ['app', '--minimized-extra']) is False
    assert should_start_minimized(None, []) is False


def test_string_false_does_not_start_minimized():
    assert should_start_minimized({'start_minimized': 'false'}, ['app']) is False
    assert should_start_minimized({'start_minimized': 'true'}, ['app']) is True


def test_settings_markup_is_in_the_window():
    root = Path(__file__).resolve().parents[1]
    html = (root / 'ui' / 'index.html').read_text(encoding='utf-8')
    css = (root / 'ui' / 'style.css').read_text(encoding='utf-8')
    script = (root / 'ui' / 'app.js').read_text(encoding='utf-8')

    assert 'id="settings-button"' in html
    assert 'id="settings-panel"' in html
    assert 'When closing the window' in html
    assert 'value="exit"' in html
    assert 'value="tray"' in html
    assert 'Minimise to tray' in html
    assert 'id="start-with-windows"' in html
    assert 'Start with Windows (minimised to tray)' in html
    assert 'overflow: hidden' in css
    assert 'overflow-y: auto' in css
    assert '.settings-panel' in css
    assert 'position: fixed' in css
    assert 'set_close_action' in script
    assert 'set_start_with_windows' in script


def test_build_spec_elevation_matches_startup_policy():
    """uac_admin in build.spec and REQUIRES_ADMIN_ELEVATION must agree.

    This build does not request administrator rights, so login startup uses
    HKCU Run rather than a highest-privileges scheduled task.
    """
    spec = Path(__file__).resolve().parents[1].joinpath('build.spec').read_text(encoding='utf-8')
    compact = spec.replace(' ', '').replace('\n', '')
    spec_requires_admin = 'uac_admin=True' in compact
    assert spec_requires_admin is REQUIRES_ADMIN_ELEVATION
    assert REQUIRES_ADMIN_ELEVATION is False
