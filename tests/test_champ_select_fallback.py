"""Tests for champion select feature role fallback logic."""
import pytest
import logging
from unittest.mock import Mock, MagicMock, patch
from features.champ_select import ChampSelectFeature


@pytest.fixture
def feature():
    """Create a champion select feature with test config."""
    # Set logging level for the feature
    logging.getLogger('features.champ_select').setLevel(logging.INFO)
    
    config = {
        'auto_ban_enabled': True,
        'auto_pick_enabled': True,
        'pick_mode': 'hover',
        '_test_mode': True,  # Enable test mode for deterministic execution
        'champ_select_preferences': {
            'default': {
                'bans': [1, 2, 3],
                'picks': [10, 11, 12]
            },
            'top': {
                'bans': [],  # Empty - should fall back to default
                'picks': []
            },
            'jungle': {
                'bans': [20, 21],
                'picks': [30, 31]
            },
            'middle': {
                'bans': [],
                'picks': []
            },
            'bottom': {
                'bans': [40],
                'picks': []
            },
            'utility': {
                'bans': [],
                'picks': [50, 51]
            }
        }
    }
    
    feature = ChampSelectFeature(config)
    feature.api_client = Mock()
    
    # Mock champion provider
    feature.champion_provider.champion_data = {
        1: {'name_en': 'Champ1', 'name_zh_tw': '冠軍1'},
        2: {'name_en': 'Champ2', 'name_zh_tw': '冠軍2'},
        3: {'name_en': 'Champ3', 'name_zh_tw': '冠軍3'},
        10: {'name_en': 'Champ10', 'name_zh_tw': '冠軍10'},
        11: {'name_en': 'Champ11', 'name_zh_tw': '冠軍11'},
        12: {'name_en': 'Champ12', 'name_zh_tw': '冠軍12'},
        20: {'name_en': 'Champ20', 'name_zh_tw': '冠軍20'},
        21: {'name_en': 'Champ21', 'name_zh_tw': '冠軍21'},
        30: {'name_en': 'Champ30', 'name_zh_tw': '冠軍30'},
        31: {'name_en': 'Champ31', 'name_zh_tw': '冠軍31'},
        40: {'name_en': 'Champ40', 'name_zh_tw': '冠軍40'},
        50: {'name_en': 'Champ50', 'name_zh_tw': '冠軍50'},
        51: {'name_en': 'Champ51', 'name_zh_tw': '冠軍51'},
    }
    
    return feature


def test_fallback_to_default_when_role_list_empty_ban(feature, caplog):
    """Test that ban action falls back to default when role list is empty."""
    # Session with TOP role assigned but empty ban list
    session = {
        'localPlayerCellId': 0,
        'myTeam': [
            {'cellId': 0, 'assignedPosition': 'TOP'}
        ],
        'actions': [
            [{
                'id': 1,
                'actorCellId': 0,
                'type': 'ban',
                'isInProgress': True,
                'completed': False
            }]
        ],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # Mock API responses
    feature.api_client.get.side_effect = [
        [1, 2, 3, 10, 11, 12],  # All champions available (initial)
        session,  # Re-fetch after delay (in test mode, no actual delay)
        [1, 2, 3, 10, 11, 12],  # All champions available (after delay)
    ]
    feature.api_client.patch.return_value = {}
    
    # Process the session (in test mode, this executes synchronously)
    feature._process_session(session)
    
    # In test mode, action completes immediately, no need to wait for thread
    
    # Check that it logged the fallback
    assert any('falling back to default' in record.message.lower() for record in caplog.records)
    assert any('assigned role = top' in record.message.lower() for record in caplog.records)
    
    # Check that it tried to ban from default list
    patch_calls = [call for call in feature.api_client.patch.call_args_list]
    assert len(patch_calls) > 0
    # Should have tried to ban champion 1 (first in default list)
    call_args = patch_calls[0]
    assert call_args[0][0] == '/lol-champ-select/v1/session/actions/1'
    assert call_args[0][1]['championId'] == 1


def test_fallback_to_default_when_role_list_empty_pick(feature, caplog):
    """Test that pick action falls back to default when role list is empty."""
    # Session with MIDDLE role assigned but empty pick list
    session = {
        'localPlayerCellId': 0,
        'myTeam': [
            {'cellId': 0, 'assignedPosition': 'MIDDLE'}
        ],
        'actions': [
            [{
                'id': 10,
                'actorCellId': 0,
                'type': 'pick',
                'isInProgress': True,
                'completed': False
            }]
        ],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # Mock API responses
    feature.api_client.get.side_effect = [
        [1, 2, 3, 10, 11, 12],  # pickable (initial)
        session,  # Re-fetch after delay
        [1, 2, 3, 10, 11, 12],  # pickable (after delay)
    ]
    feature.api_client.patch.return_value = {}
    
    # Process the session (in test mode, this executes synchronously)
    feature._process_session(session)
    
    # Check that it logged the fallback
    assert any('falling back to default' in record.message.lower() for record in caplog.records)
    assert any('assigned role = middle' in record.message.lower() for record in caplog.records)
    
    # Check that it tried to pick from default list
    patch_calls = [call for call in feature.api_client.patch.call_args_list]
    assert len(patch_calls) > 0
    # Should have tried to hover champion 10 (first in default picks)
    call_args = patch_calls[0]
    assert call_args[0][0] == '/lol-champ-select/v1/session/actions/10'
    assert call_args[0][1]['championId'] == 10
    assert call_args[0][1]['completed'] is False  # Hover mode


def test_no_fallback_when_role_has_list(feature, caplog):
    """Test that it uses role list when available (no fallback)."""
    # Session with JUNGLE role assigned, which has its own ban list
    session = {
        'localPlayerCellId': 0,
        'myTeam': [
            {'cellId': 0, 'assignedPosition': 'JUNGLE'}
        ],
        'actions': [
            [{
                'id': 2,
                'actorCellId': 0,
                'type': 'ban',
                'isInProgress': True,
                'completed': False
            }]
        ],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # Mock API responses
    feature.api_client.get.side_effect = [
        [20, 21, 30, 31],  # bannable (initial)
        session,  # Re-fetch after delay
        [20, 21, 30, 31],  # bannable (after delay)
    ]
    feature.api_client.patch.return_value = {}
    
    # Process the session
    feature._process_session(session)
    
    # Should NOT fall back to default
    assert not any('falling back to default' in record.message.lower() for record in caplog.records)
    assert any('assigned role = jungle' in record.message.lower() for record in caplog.records)
    assert any('using jungle list' in record.message.lower() for record in caplog.records)
    
    # Should have tried to ban champion 20 (first in jungle list)
    patch_calls = [call for call in feature.api_client.patch.call_args_list]
    assert len(patch_calls) > 0
    call_args = patch_calls[0]
    assert call_args[0][1]['championId'] == 20


def test_fallback_when_no_assigned_position(feature, caplog):
    """Test that it uses default when assignedPosition is empty (blind pick)."""
    # Session with no role assigned (blind pick)
    session = {
        'localPlayerCellId': 0,
        'myTeam': [
            {'cellId': 0, 'assignedPosition': ''}
        ],
        'actions': [
            [{
                'id': 3,
                'actorCellId': 0,
                'type': 'ban',
                'isInProgress': True,
                'completed': False
            }]
        ],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # Mock API responses
    feature.api_client.get.side_effect = [
        [1, 2, 3],  # bannable (initial)
        session,  # Re-fetch after delay
        [1, 2, 3],  # bannable (after delay)
    ]
    feature.api_client.patch.return_value = {}
    
    # Process the session
    feature._process_session(session)
    
    # Should use default directly (logged as "assigned role = default")
    assert any('assigned role = default' in record.message.lower() for record in caplog.records)
    assert any('using default list' in record.message.lower() for record in caplog.records)
    
    # Should have tried to ban champion 1 (first in default list)
    patch_calls = [call for call in feature.api_client.patch.call_args_list]
    assert len(patch_calls) > 0
    call_args = patch_calls[0]
    assert call_args[0][1]['championId'] == 1


def test_planning_hover_fallback(feature, caplog):
    """Test that PLANNING phase hover also falls back to default when needed."""
    # Session in PLANNING phase with BOTTOM role (has bans but no picks)
    session = {
        'localPlayerCellId': 0,
        'myTeam': [
            {'cellId': 0, 'assignedPosition': 'BOTTOM'}
        ],
        'actions': [
            [{
                'id': 20,
                'actorCellId': 0,
                'type': 'pick',
                'isInProgress': False,
                'completed': False
            }]
        ],
        'bans': {'myTeamBans': [], 'theirTeamBans': []},
        'timer': {'phase': 'PLANNING', 'adjustedTimeLeftInPhase': 30000}
    }
    
    # Mock API responses
    feature.api_client.get.side_effect = [
        [10, 11, 12, 40],  # pickable (initial)
        session,  # Re-fetch after delay
        [10, 11, 12, 40],  # pickable (after delay)
    ]
    feature.api_client.patch.return_value = {}
    
    # Process the session
    feature._process_session(session)
    
    # Should fall back to default for picks
    assert any('falling back to default' in record.message.lower() for record in caplog.records)
    
    # Should have hovered champion 10 (first in default picks)
    patch_calls = [call for call in feature.api_client.patch.call_args_list]
    assert len(patch_calls) > 0
    call_args = patch_calls[0]
    assert call_args[0][1]['championId'] == 10
