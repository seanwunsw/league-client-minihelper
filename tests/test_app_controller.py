"""Tests for AppController."""
import pytest
from unittest.mock import Mock, MagicMock
from core.app_controller import AppController
from features.auto_accept import AutoAcceptFeature


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


def test_toggle_feature():
    """Test toggling a feature."""
    config = {'auto_accept_enabled': True}
    controller = AppController(config)
    
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


def test_update_feature_setting():
    """Test updating a feature setting."""
    config = {
        'auto_accept_enabled': True,
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4
    }
    controller = AppController(config)
    
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
