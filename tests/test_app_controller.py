"""Tests for AppController."""
import yaml
import pytest
from unittest.mock import Mock, MagicMock
from core.app_controller import AppController
from core.windows_startup import StartupResult
from features.auto_accept import AutoAcceptFeature


class FakeStartup:
    """In-memory login-startup registrar."""

    def __init__(self, available=True, requires_admin=False, ok=True, message=None):
        self.available = available
        self.requires_admin = requires_admin
        self.ok = ok
        self.message = message
        self.calls = []

    def status(self):
        if not self.available:
            return {
                'available': False,
                'method': None,
                'note': 'Start with Windows is only available in the packaged exe.',
                'requires_admin': self.requires_admin,
            }
        return {
            'available': True,
            'method': 'task_scheduler' if self.requires_admin else 'hkcu_run',
            'note': 'Scheduled task.' if self.requires_admin else None,
            'requires_admin': self.requires_admin,
        }

    def sync(self, enabled):
        self.calls.append(bool(enabled))
        if not self.available:
            return StartupResult(True, False, bool(enabled), None, False, self.status()['note'])
        if not self.ok:
            return StartupResult(False, True, False, self.status()['method'], False, self.message or 'failed')
        return StartupResult(True, True, bool(enabled), self.status()['method'], True, None)


def test_controller_init():
    """Test controller initialization."""
    config = {'auto_accept_enabled': True}
    controller = AppController(config)
    
    assert controller.config == config
    assert controller.connection_state == "disconnected"
    assert controller.gameflow_phase == "None"
    assert len(controller.features) == 0


def test_register_feature():
    """Test feature registration."""
    config = {'auto_accept_enabled': True}
    controller = AppController(config)
    
    feature = AutoAcceptFeature(config)
    controller.register_feature(feature)
    
    assert len(controller.features) == 1
    assert controller.features[0].get_name() == "Auto-Accept"


def test_get_state():
    """Test getting application state."""
    config = {'auto_accept_enabled': True}
    controller = AppController(config)
    
    feature = AutoAcceptFeature(config)
    controller.register_feature(feature)
    
    state = controller.get_state()
    
    assert 'connection_state' in state
    assert 'gameflow_phase' in state
    assert 'features' in state
    assert len(state['features']) == 1
    assert state['features'][0]['name'] == 'Auto-Accept'


def test_toggle_feature(tmp_path):
    """Test toggling a feature."""
    config = {'auto_accept_enabled': True}
    controller = AppController(config, config_path=str(tmp_path / 'config.yaml'))
    
    feature = AutoAcceptFeature(config)
    controller.register_feature(feature)
    
    # Initially enabled
    assert feature.enabled == True
    
    # Toggle off
    result = controller.toggle_feature('Auto-Accept')
    assert result == False
    assert feature.enabled == False
    
    # Toggle on
    result = controller.toggle_feature('Auto-Accept')
    assert result == True
    assert feature.enabled == True


def test_update_feature_setting(tmp_path):
    """Test updating a feature setting."""
    config = {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4
    }
    controller = AppController(config, config_path=str(tmp_path / 'config.yaml'))
    
    feature = AutoAcceptFeature(config)
    controller.register_feature(feature)
    
    # Update setting
    result = controller.update_feature_setting('Auto-Accept', 'accept_delay_min_seconds', 2)
    assert result == True
    assert feature.accept_delay_min == 2
    
    result = controller.update_feature_setting('Auto-Accept', 'accept_delay_max_seconds', 5)
    assert result == True
    assert feature.accept_delay_max == 5


def test_settings_schema():
    """Test that features expose settings schema."""
    config = {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4
    }
    
    feature = AutoAcceptFeature(config)
    schema = feature.get_settings_schema()
    
    assert 'accept_delay_min_seconds' in schema
    assert 'accept_delay_max_seconds' in schema
    assert schema['accept_delay_min_seconds']['type'] == 'number'
    assert schema['accept_delay_min_seconds']['current'] == 1
    assert schema['accept_delay_max_seconds']['current'] == 4


def test_feature_status():
    """Test that features expose status."""
    config = {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4
    }
    
    feature = AutoAcceptFeature(config)
    status = feature.get_status()
    
    assert 'enabled' in status
    assert 'accept_history' in status
    assert status['enabled'] == True
    assert isinstance(status['accept_history'], list)


def test_close_action_defaults_to_exit_for_old_config(tmp_path):
    """Configs written before close_action existed exit when the window is closed."""
    config = {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 2,
        'log_level': 'DEBUG',
    }
    controller = AppController(config, config_path=str(tmp_path / 'config.yaml'))

    assert controller.get_close_action() == 'exit'
    assert controller.handle_main_window_close() == 'exit'
    assert controller.get_start_with_windows() is False
    assert config['accept_delay_min_seconds'] == 2
    assert config['log_level'] == 'DEBUG'
    assert config['auto_accept_enabled'] is True


def test_close_action_tray_is_persisted_and_reported(tmp_path):
    path = tmp_path / 'config.yaml'
    config = {'auto_accept_enabled': False, 'accept_delay_max_seconds': 4}
    controller = AppController(config, config_path=str(path))

    assert controller.set_close_action('tray') is True
    assert controller.handle_main_window_close() == 'tray'
    assert controller.set_close_action('EXIT') is True
    assert controller.get_close_action() == 'exit'
    assert controller.set_close_action('minimize') is False
    assert controller.get_close_action() == 'exit'

    controller.set_close_action('tray')
    saved = yaml.safe_load(path.read_text(encoding='utf-8'))
    assert saved['close_action'] == 'tray'
    assert saved['start_with_windows'] is False
    assert saved['auto_accept_enabled'] is False
    assert saved['accept_delay_max_seconds'] == 4


def test_invalid_stored_close_action_falls_back_to_exit(tmp_path):
    config = {'close_action': 'bogus', 'auto_accept_enabled': True}
    controller = AppController(config, config_path=str(tmp_path / 'config.yaml'))
    assert controller.handle_main_window_close() == 'exit'


def test_close_action_survives_feature_setting_save(tmp_path):
    path = tmp_path / 'config.yaml'
    config = {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4,
    }
    controller = AppController(config, config_path=str(path))
    controller.register_feature(AutoAcceptFeature(config))
    assert controller.set_close_action('tray') is True

    assert controller.update_feature_setting('Auto-Accept', 'accept_delay_min_seconds', 2) is True
    saved = yaml.safe_load(path.read_text(encoding='utf-8'))
    assert saved['close_action'] == 'tray'
    assert saved['accept_delay_min_seconds'] == 2
    assert saved['auto_accept_enabled'] is True


def test_start_with_windows_persists_and_syncs(tmp_path):
    path = tmp_path / 'config.yaml'
    fake = FakeStartup()
    controller = AppController(
        {'auto_accept_enabled': True},
        config_path=str(path),
        startup_registrar=fake,
    )

    result = controller.set_start_with_windows(True)
    assert result['ok'] is True
    assert result['method'] == 'hkcu_run'
    assert fake.calls == [True]
    assert controller.get_start_with_windows() is True

    saved = yaml.safe_load(path.read_text(encoding='utf-8'))
    assert saved['start_with_windows'] is True
    assert saved['close_action'] == 'exit'

    controller.apply_startup_registration()
    assert fake.calls == [True, True]


def test_start_with_windows_from_source_does_not_enable(tmp_path):
    fake = FakeStartup(available=False)
    controller = AppController(
        {'start_with_windows': False},
        config_path=str(tmp_path / 'config.yaml'),
        startup_registrar=fake,
    )

    result = controller.set_start_with_windows(True)
    assert result['available'] is False
    assert result['message']
    assert controller.get_start_with_windows() is False
    assert fake.calls == [True]


def test_start_with_windows_does_not_persist_when_registration_fails(tmp_path):
    fake = FakeStartup(ok=False, message='Access is denied.')
    controller = AppController(
        {},
        config_path=str(tmp_path / 'config.yaml'),
        startup_registrar=fake,
    )

    result = controller.set_start_with_windows(True)
    assert result['ok'] is False
    assert controller.get_start_with_windows() is False
    assert not (tmp_path / 'config.yaml').exists()


def test_app_settings_included_in_state(tmp_path):
    fake = FakeStartup(requires_admin=True)
    controller = AppController(
        {},
        config_path=str(tmp_path / 'config.yaml'),
        startup_registrar=fake,
    )
    settings = controller.get_app_settings()
    assert settings['close_action'] == 'exit'
    assert settings['start_with_windows'] is False
    assert settings['start_with_windows_available'] is True
    assert settings['startup_method'] == 'task_scheduler'
    assert settings['requires_admin_elevation'] is True
    assert controller.get_state()['app_settings'] == settings


def test_real_registrar_is_unavailable_when_not_frozen(tmp_path):
    controller = AppController({}, config_path=str(tmp_path / 'config.yaml'))
    settings = controller.get_app_settings()
    assert settings['start_with_windows_available'] is False
    assert settings['requires_admin_elevation'] is False
    assert 'source' in settings['start_with_windows_note'].lower()
