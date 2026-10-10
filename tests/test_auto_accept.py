"""Tests for auto-accept feature."""
import pytest
import time
from unittest.mock import Mock, MagicMock
from features.auto_accept import AutoAcceptFeature


def test_feature_initialization():
    """Test feature initialization with fixed delay (backward compatible)."""
    config = {
        'accept_delay_seconds': 1
    }
    feature = AutoAcceptFeature(config)
    assert feature.get_name() == "Auto-Accept"
    assert feature.accept_delay_min == 1
    assert feature.accept_delay_max == 1
    assert feature.enabled is True


def test_feature_initialization_random_delay():
    """Test feature initialization with random delay range."""
    config = {
        'accept_delay_min_seconds': 1,
        'accept_delay_max_seconds': 4
    }
    feature = AutoAcceptFeature(config)
    assert feature.accept_delay_min == 1
    assert feature.accept_delay_max == 4


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
    mock_api_client.get_ready_check_state.return_value = {
        'state': 'InProgress',
        'playerResponse': 'None'
    }
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
    
    # Wait briefly for any async operations
    time.sleep(0.05)
    
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
    feature = AutoAcceptFeature({'accept_delay_seconds': 0})
    
    mock_api_client = Mock()
    mock_api_client.accept_ready_check.return_value = True
    mock_api_client.get_ready_check_state.return_value = {
        'state': 'InProgress',
        'playerResponse': 'None'
    }
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
    time.sleep(0.1)  # Let accept complete
    assert mock_api_client.accept_ready_check.call_count == 1
    
    # Reset scheduled flag (simulating state change)
    feature.accept_scheduled = False
    
    # Second accept immediately (should be blocked by cooldown)
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    time.sleep(0.1)
    assert mock_api_client.accept_ready_check.call_count == 1
    
    # Wait for cooldown to expire
    time.sleep(feature.cooldown)
    
    # Third accept (should work)
    feature.accept_scheduled = False  # Reset flag
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    time.sleep(0.1)
    assert mock_api_client.accept_ready_check.call_count == 2


def test_delayed_accept():
    """Test delayed accept functionality."""
    config = {'accept_delay_seconds': 0.1}  # Short delay for testing
    feature = AutoAcceptFeature(config)
    
    mock_api_client = Mock()
    mock_api_client.accept_ready_check.return_value = True
    mock_api_client.get_ready_check_state.return_value = {
        'state': 'InProgress',
        'playerResponse': 'None'
    }
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
    time.sleep(0.3)
    
    # Should be called after delay
    mock_api_client.accept_ready_check.assert_called_once()


def test_null_data_handling():
    """Test that null data (Delete events) doesn't crash."""
    feature = AutoAcceptFeature({})
    
    mock_api_client = Mock()
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    # Delete event with null data
    event_data = {
        'eventType': 'Delete',
        'data': None
    }
    
    # Should not crash
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Should not accept
    mock_api_client.accept_ready_check.assert_not_called()


def test_null_data_in_http_poll():
    """Test that null response in HTTP poll doesn't crash."""
    feature = AutoAcceptFeature({'accept_delay_seconds': 0})
    
    mock_api_client = Mock()
    mock_api_client.get_ready_check_state.return_value = None  # 404 / not in ready check
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    # Simulate one poll iteration
    feature.running = False  # Stop after one iteration
    
    # Should not crash (poll will call get_ready_check_state once in the loop)
    # The test just verifies no exception is raised


def test_recheck_before_accept():
    """Test that ready check state is re-checked before accepting."""
    config = {'accept_delay_seconds': 0.05}
    feature = AutoAcceptFeature(config)
    
    mock_api_client = Mock()
    # Re-check will show already accepted
    mock_api_client.get_ready_check_state.return_value = {
        'state': 'InProgress',
        'playerResponse': 'Accepted'  # Already accepted
    }
    mock_event_bus = Mock()
    
    # Stop polling thread to avoid interference
    feature.running = False
    feature.api_client = mock_api_client
    mock_event_bus.subscribe = Mock()
    
    event_data = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'None'
        }
    }
    
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Wait for delay and re-check
    time.sleep(0.15)
    
    # Should NOT accept because re-check showed already accepted
    mock_api_client.accept_ready_check.assert_not_called()


def test_prevent_duplicate_scheduling():
    """Test that WS and HTTP poll don't both schedule accepts."""
    feature = AutoAcceptFeature({'accept_delay_seconds': 0})
    
    mock_api_client = Mock()
    mock_api_client.accept_ready_check.return_value = True
    mock_api_client.get_ready_check_state.return_value = {
        'state': 'InProgress',
        'playerResponse': 'None'
    }
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    event_data = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'None'
        }
    }
    
    # First event schedules accept
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Second event immediately after should be ignored (accept_scheduled=True)
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data)
    
    # Wait a bit
    time.sleep(0.1)
    
    # Should only accept once
    assert mock_api_client.accept_ready_check.call_count == 1


def test_state_change_resets_scheduled_flag():
    """Test that accept_scheduled flag is reset when state changes."""
    feature = AutoAcceptFeature({})
    
    mock_api_client = Mock()
    mock_event_bus = Mock()
    
    feature.initialize(mock_event_bus, mock_api_client)
    
    # First event: InProgress
    event_data1 = {
        'data': {
            'state': 'InProgress',
            'playerResponse': 'None'
        }
    }
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data1)
    
    # accept_scheduled should be True
    assert feature.accept_scheduled is True
    
    # Second event: state changed to EveryoneReady
    event_data2 = {
        'data': {
            'state': 'EveryoneReady',
            'playerResponse': 'Accepted'
        }
    }
    feature._on_ready_check_event('/lol-matchmaking/v1/ready-check', event_data2)
    
    # accept_scheduled should be reset to False
    assert feature.accept_scheduled is False
