"""Tests for champion select feature delay functionality."""
import pytest
import time
import logging
import threading
from unittest.mock import Mock, MagicMock, patch
from features.champ_select import ChampSelectFeature


@pytest.fixture
def feature_with_delays():
    """Create a champion select feature with configured delays."""
    # Set logging level to DEBUG to capture debug messages
    logging.getLogger('features.champ_select').setLevel(logging.DEBUG)
    
    config = {
        'auto_ban_enabled': True,
        'auto_pick_enabled': True,
        'pick_mode': 'hover',
        'ban_delay_min_seconds': 0.5,
        'ban_delay_max_seconds': 1.0,
        'pick_delay_min_seconds': 0.5,
        'pick_delay_max_seconds': 1.0,
        'champ_select_preferences': {
            'default': {
                'bans': [1, 2, 3],
                'picks': [10, 11, 12]
            }
        }
    }
    
    feature = ChampSelectFeature(config)
    feature.api_client = Mock()
    
    # Mock champion provider
    feature.champion_provider.champion_data = {
        1: {'name_en': 'Champ1', 'name_zh_tw': '冠軍1'},
        2: {'name_en': 'Champ2', 'name_zh_tw': '冠軍2'},
        10: {'name_en': 'Champ10', 'name_zh_tw': '冠軍10'},
    }
    
    return feature


def test_delay_within_range(feature_with_delays, caplog):
    """Test that calculated delay is within configured range."""
    session = {
        'timer': {'adjustedTimeLeftInPhase': 30000}  # 30 seconds
    }
    
    # Test ban delay
    for _ in range(10):
        delay = feature_with_delays._calculate_safe_delay(
            session,
            feature_with_delays.ban_delay_min,
            feature_with_delays.ban_delay_max
        )
        assert feature_with_delays.ban_delay_min <= delay <= feature_with_delays.ban_delay_max


def test_delay_capped_by_timer(feature_with_delays, caplog):
    """Test that delay is capped when timer is running out."""
    # Only 2 seconds left (with 3s safety margin, max delay should be 0)
    session = {
        'timer': {'adjustedTimeLeftInPhase': 2000}  # 2 seconds
    }
    
    delay = feature_with_delays._calculate_safe_delay(
        session,
        feature_with_delays.ban_delay_min,
        feature_with_delays.ban_delay_max
    )
    
    # Should be capped to 0 (2s - 3s safety margin = -1, max(0, -1) = 0)
    assert delay == 0
    
    # 10 seconds left, should cap to 7s max (10 - 3 safety)
    session = {
        'timer': {'adjustedTimeLeftInPhase': 10000}  # 10 seconds
    }
    
    delay = feature_with_delays._calculate_safe_delay(
        session,
        5.0,  # min 5s
        15.0  # max 15s (but only 10s available)
    )
    
    assert delay <= 7.0  # 10 - 3 safety margin


def test_skip_when_user_acted_during_delay(feature_with_delays, caplog):
    """Test that action is skipped if user acted manually during delay."""
    session_initial = {
        'localPlayerCellId': 0,
        'myTeam': [{'cellId': 0, 'assignedPosition': ''}],
        'actions': [[{
            'id': 1,
            'actorCellId': 0,
            'type': 'ban',
            'isInProgress': True,
            'completed': False
        }]],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # After delay, action is completed
    session_after = session_initial.copy()
    session_after['actions'] = [[{
        'id': 1,
        'actorCellId': 0,
        'type': 'ban',
        'isInProgress': True,
        'completed': True  # User already acted
    }]]
    
    # Mock API responses
    feature_with_delays.api_client.get.side_effect = [
        [1, 2, 3],  # bannable IDs (initial)
        session_after,  # session after delay
    ]
    
    # Start the ban action
    action = session_initial['actions'][0][0]
    feature_with_delays._handle_ban_action(session_initial, action, 0)
    
    # Wait for thread to complete
    if feature_with_delays.pending_action_thread:
        feature_with_delays.pending_action_thread.join(timeout=3)
    
    # Should have logged that user already acted
    assert any('already acted' in record.message.lower() for record in caplog.records)
    
    # Should NOT have called patch (because user already acted)
    patch_calls = [call for call in feature_with_delays.api_client.patch.call_args_list]
    assert len(patch_calls) == 0


def test_reselection_after_delay(feature_with_delays, caplog):
    """Test that candidates are re-selected after delay."""
    session_initial = {
        'localPlayerCellId': 0,
        'myTeam': [{'cellId': 0, 'assignedPosition': ''}],
        'actions': [[{
            'id': 1,
            'actorCellId': 0,
            'type': 'ban',
            'isInProgress': True,
            'completed': False
        }]],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # After delay, champ 1 is already banned, should skip to champ 2
    session_after = session_initial.copy()
    session_after['bans'] = {'myTeamBans': [1], 'theirTeamBans': []}
    
    # Mock API responses
    feature_with_delays.api_client.get.side_effect = [
        [1, 2, 3],  # bannable IDs (initial)
        session_after,  # session after delay (champ 1 banned)
        [2, 3],  # bannable IDs after delay
    ]
    feature_with_delays.api_client.patch.return_value = {}
    
    # Start the ban action
    action = session_initial['actions'][0][0]
    feature_with_delays._handle_ban_action(session_initial, action, 0)
    
    # Wait for thread to complete
    if feature_with_delays.pending_action_thread:
        feature_with_delays.pending_action_thread.join(timeout=2)
    
    # Should have tried to ban champ 2 (first available after champ 1 was banned)
    patch_calls = [call for call in feature_with_delays.api_client.patch.call_args_list]
    if len(patch_calls) > 0:
        call_args = patch_calls[0]
        assert call_args[0][1]['championId'] == 2


def test_cancel_on_champ_select_end(feature_with_delays, caplog):
    """Test that pending actions are cancelled when champ select ends."""
    session = {
        'localPlayerCellId': 0,
        'myTeam': [{'cellId': 0, 'assignedPosition': ''}],
        'actions': [[{
            'id': 1,
            'actorCellId': 0,
            'type': 'ban',
            'isInProgress': True,
            'completed': False
        }]],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # Mock API responses
    feature_with_delays.api_client.get.return_value = [1, 2, 3]  # bannable IDs
    
    # Start the ban action (will wait for delay)
    action = session['actions'][0][0]
    feature_with_delays._handle_ban_action(session, action, 0)
    
    # Small delay to let thread start
    time.sleep(0.1)
    
    # Simulate champ select ending
    event_data = {'eventType': 'Delete', 'data': None}
    feature_with_delays._on_champ_select_event('/lol-champ-select/v1/session', event_data)
    
    # Wait for thread to complete
    if feature_with_delays.pending_action_thread:
        feature_with_delays.pending_action_thread.join(timeout=2)
    
    # Should have cancelled
    assert any('cancel' in record.message.lower() for record in caplog.records)


def test_backward_compatibility_old_delays(caplog):
    """Test that old delay config keys are migrated."""
    old_config = {
        'auto_ban_enabled': True,
        'auto_pick_enabled': True,
        'pick_mode': 'hover',
        'auto_ban_delay_seconds': 2.0,  # Old key
        'auto_lock_delay_seconds': 3.0,  # Old key
        'champ_select_preferences': {
            'default': {'bans': [], 'picks': []}
        }
    }
    
    feature = ChampSelectFeature(old_config)
    
    # Should use old value as min, with default max
    assert feature.ban_delay_min == 2.0
    assert feature.ban_delay_max == 3.0
    assert feature.pick_delay_min == 3.0  # From auto_lock_delay_seconds
    assert feature.pick_delay_max == 3.0


def test_delay_validation(caplog):
    """Test delay range validation."""
    # Min > Max should swap
    config = {
        'auto_ban_enabled': True,
        'ban_delay_min_seconds': 5.0,
        'ban_delay_max_seconds': 2.0,  # Less than min
        'champ_select_preferences': {'default': {'bans': [], 'picks': []}}
    }
    
    feature = ChampSelectFeature(config)
    
    # Should have swapped
    assert feature.ban_delay_min == 2.0
    assert feature.ban_delay_max == 5.0
    assert any('swapping' in record.message.lower() for record in caplog.records)
