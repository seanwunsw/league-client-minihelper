"""Tests for auto-accept feature."""
import pytest
import time
from unittest.mock import Mock, MagicMock
from features.auto_accept import AutoAcceptFeature


def test_feature_initialization():
    """Test feature initialization."""
    config = {
        'accept_delay_seconds': 1
    }
    feature = AutoAcceptFeature(config)
    assert feature.get_name() == "Auto-Accept"
    assert feature.accept_delay == 1
    assert feature.enabled is True


def test_feature_enable_disable():
    """Test enabling and disabling feature."""
    feature = AutoAcceptFeature({})
    
    assert feature.enabled is True
    feature.disable()
    assert feature.enabled is False
    feature.enable()
    assert feature.enabled is True


def test_ready_check_accept_immediate():
    """Test immediate accept without delay."""
    config = {'accept_delay_seconds': 0}
    feature = AutoAcceptFeature(config)
    
    mock_api_client = Mock()
    mock_api_client.accept_ready_check.return_value = True
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    # Simulate ready check event
    event_data = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'None'
        }
    }
    
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Should accept immediately
    mock_api_client.accept_ready_check.assert_called_once()


def test_ready_check_ignore_when_disabled():
    """Test that ready check is ignored when feature is disabled."""
    feature = AutoAcceptFeature({})
    
    mock_api_client = Mock()
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    feature.disable()
    
    event_data = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'None'
        }
    }
    
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Should not accept when disabled
    mock_api_client.accept_ready_check.assert_not_called()


def test_ready_check_ignore_already_responded():
    """Test that ready check is ignored if already responded."""
    feature = AutoAcceptFeature({})
    
    mock_api_client = Mock()
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    # Player already accepted
    event_data = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'Accepted'
        }
    }
    
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Should not accept again
    mock_api_client.accept_ready_check.assert_not_called()


def test_ready_check_ignore_wrong_state():
    """Test that ready check is ignored if not in progress."""
    feature = AutoAcceptFeature({})
    
    mock_api_client = Mock()
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    # State is not InProgress
    event_data = {
        'data': {
            'state': 'Complete',
            'playerResponse': 'None'
        }
    }
    
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Should not accept
    mock_api_client.accept_ready_check.assert_not_called()


def test_ready_check_cooldown():
    """Test that cooldown prevents duplicate accepts."""
    feature = AutoAcceptFeature({})
    
    mock_api_client = Mock()
    mock_api_client.accept_ready_check.return_value = True
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    event_data = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'None'
        }
    }
    
    # First accept
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    assert mock_api_client.accept_ready_check.call_count == 1
    
    # Second accept immediately (should be blocked by cooldown)
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    assert mock_api_client.accept_ready_check.call_count == 1
    
    # Wait for cooldown to expire
    time.sleep(feature.cooldown + 0.1)
    
    # Third accept (should work)
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    assert mock_api_client.accept_ready_check.call_count == 2


def test_delayed_accept():
    """Test delayed accept functionality."""
    config = {'accept_delay_seconds': 0.1}  # Short delay for testing
    feature = AutoAcceptFeature(config)
    
    mock_api_client = Mock()
    mock_api_client.accept_ready_check.return_value = True
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    event_data = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'None'
        }
    }
    
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Should not be called immediately
    mock_api_client.accept_ready_check.assert_not_called()
    
    # Wait for delay
    time.sleep(0.2)
    
    # Should be called after delay
    mock_api_client.accept_ready_check.assert_called_once()
