"""Tests for champion select decision logic."""
import pytest
from features.champ_select_logic import (
    get_assigned_position,
    flatten_actions,
    find_my_action,
    get_banned_champions,
    get_picked_champions,
    get_teammate_intents,
    filter_available_champions,
    should_hover_during_planning
)


def test_get_assigned_position_with_position():
    """Test getting assigned position when player has one."""
    session = {
        'myTeam': [
            {'cellId': 0, 'assignedPosition': 'TOP'},
            {'cellId': 1, 'assignedPosition': 'JUNGLE'},
            {'cellId': 2, 'assignedPosition': ''}
        ]
    }
    assert get_assigned_position(session, 0) == 'top'
    assert get_assigned_position(session, 1) == 'jungle'


def test_get_assigned_position_default():
    """Test default position when no assignment (blind pick)."""
    session = {
        'myTeam': [
            {'cellId': 0, 'assignedPosition': ''},
            {'cellId': 1, 'assignedPosition': ''}
        ]
    }
    assert get_assigned_position(session, 0) == 'default'
    assert get_assigned_position(session, 99) == 'default'


def test_get_assigned_position_null_session():
    """Test with null session."""
    assert get_assigned_position(None, 0) == 'default'
    assert get_assigned_position({}, 0) == 'default'


def test_flatten_actions():
    """Test flattening nested action lists."""
    session = {
        'actions': [
            [{'id': 1, 'type': 'ban'}, {'id': 2, 'type': 'ban'}],
            [{'id': 3, 'type': 'pick'}],
            [{'id': 4, 'type': 'pick'}, {'id': 5, 'type': 'pick'}]
        ]
    }
    flattened = flatten_actions(session)
    assert len(flattened) == 5
    assert flattened[0]['id'] == 1
    assert flattened[4]['id'] == 5


def test_flatten_actions_empty():
    """Test flattening with no actions."""
    assert flatten_actions(None) == []
    assert flatten_actions({}) == []
    assert flatten_actions({'actions': []}) == []


def test_find_my_action_ban_turn():
    """Test finding player's active ban action."""
    session = {
        'actions': [
            [
                {'id': 1, 'actorCellId': 0, 'type': 'ban', 'isInProgress': True, 'completed': False},
                {'id': 2, 'actorCellId': 1, 'type': 'ban', 'isInProgress': False, 'completed': False}
            ]
        ]
    }
    action = find_my_action(session, 0)
    assert action is not None
    assert action['id'] == 1
    assert action['type'] == 'ban'


def test_find_my_action_pick_turn():
    """Test finding player's active pick action."""
    session = {
        'actions': [
            [
                {'id': 10, 'actorCellId': 2, 'type': 'pick', 'isInProgress': True, 'completed': False},
                {'id': 11, 'actorCellId': 3, 'type': 'pick', 'isInProgress': False, 'completed': False}
            ]
        ]
    }
    action = find_my_action(session, 2)
    assert action is not None
    assert action['id'] == 10
    assert action['type'] == 'pick'


def test_find_my_action_no_action():
    """Test when player has no active action."""
    session = {
        'actions': [
            [
                {'id': 1, 'actorCellId': 0, 'type': 'ban', 'isInProgress': False, 'completed': True},
                {'id': 2, 'actorCellId': 1, 'type': 'ban', 'isInProgress': True, 'completed': False}
            ]
        ]
    }
    action = find_my_action(session, 0)
    assert action is None


def test_find_my_action_null_session():
    """Test with null session."""
    assert find_my_action(None, 0) is None
    assert find_my_action({}, 0) is None


def test_get_banned_champions():
    """Test getting all banned champions."""
    session = {
        'bans': {
            'myTeamBans': [1, 2, 3],
            'theirTeamBans': [4, 5, 6]
        },
        'actions': [
            [
                {'type': 'ban', 'completed': True, 'championId': 7},
                {'type': 'ban', 'completed': False, 'championId': 8}  # Not completed
            ]
        ]
    }
    banned = get_banned_champions(session)
    assert banned == {1, 2, 3, 4, 5, 6, 7}
    assert 8 not in banned


def test_get_banned_champions_empty():
    """Test with no bans."""
    session = {
        'bans': {
            'myTeamBans': [],
            'theirTeamBans': []
        },
        'actions': []
    }
    banned = get_banned_champions(session)
    assert banned == set()


def test_get_banned_champions_null():
    """Test with null data."""
    assert get_banned_champions(None) == set()
    assert get_banned_champions({}) == set()


def test_get_picked_champions():
    """Test getting all picked champions."""
    session = {
        'actions': [
            [
                {'type': 'pick', 'completed': True, 'championId': 10},
                {'type': 'pick', 'completed': True, 'championId': 20}
            ],
            [
                {'type': 'pick', 'completed': False, 'championId': 30},  # Not completed
                {'type': 'ban', 'completed': True, 'championId': 40}  # Ban, not pick
            ]
        ]
    }
    picked = get_picked_champions(session)
    assert picked == {10, 20}
    assert 30 not in picked
    assert 40 not in picked


def test_get_picked_champions_empty():
    """Test with no picks."""
    assert get_picked_champions(None) == set()
    assert get_picked_champions({'actions': []}) == set()


def test_get_teammate_intents():
    """Test getting teammate champion intents."""
    session = {
        'myTeam': [
            {'cellId': 0, 'championPickIntent': 100},  # Local player
            {'cellId': 1, 'championPickIntent': 101},
            {'cellId': 2, 'championPickIntent': 0},  # No intent
            {'cellId': 3, 'championPickIntent': 102}
        ],
        'actions': [
            [
                {'type': 'pick', 'actorCellId': 1, 'completed': False, 'championId': 103},
                {'type': 'pick', 'actorCellId': 0, 'completed': False, 'championId': 104}  # Local player
            ]
        ]
    }
    intents = get_teammate_intents(session, 0)
    assert intents == {101, 102, 103}
    assert 100 not in intents  # Local player's intent excluded
    assert 104 not in intents  # Local player's hover excluded


def test_get_teammate_intents_empty():
    """Test with no teammate intents."""
    session = {
        'myTeam': [
            {'cellId': 0, 'championPickIntent': 0}
        ],
        'actions': []
    }
    intents = get_teammate_intents(session, 0)
    assert intents == set()


def test_get_teammate_intents_null():
    """Test with null session."""
    assert get_teammate_intents(None, 0) == set()
    assert get_teammate_intents({}, 0) == set()


def test_filter_available_champions_ban():
    """Test filtering available ban champions."""
    candidates = [1, 2, 3, 4, 5]
    pickable_ids = set()
    bannable_ids = {1, 2, 3, 4, 5, 6, 7}
    banned = {2}  # 2 already banned
    picked = set()
    teammate_intents = {4}  # 4 is teammate intent
    
    available = filter_available_champions(
        candidates,
        pickable_ids,
        bannable_ids,
        'ban',
        banned,
        picked,
        teammate_intents
    )
    
    assert available == [1, 3, 5]
    assert 2 not in available  # Already banned
    assert 4 not in available  # Teammate intent


def test_filter_available_champions_pick():
    """Test filtering available pick champions."""
    candidates = [10, 20, 30, 40, 50]
    pickable_ids = {10, 20, 30, 40, 50, 60}
    bannable_ids = set()
    banned = {20}  # 20 banned
    picked = {30}  # 30 already picked
    teammate_intents = {40}  # Should not affect picks
    
    available = filter_available_champions(
        candidates,
        pickable_ids,
        bannable_ids,
        'pick',
        banned,
        picked,
        teammate_intents
    )
    
    assert available == [10, 40, 50]
    assert 20 not in available  # Banned
    assert 30 not in available  # Already picked
    assert 40 in available  # Teammate intents don't block picks


def test_filter_available_champions_fallback():
    """Test fallback when top candidates unavailable."""
    candidates = [1, 2, 3, 4, 5]
    pickable_ids = {1, 2, 3, 4, 5}
    bannable_ids = set()
    banned = {1, 2}
    picked = {3}
    teammate_intents = set()
    
    available = filter_available_champions(
        candidates,
        pickable_ids,
        bannable_ids,
        'pick',
        banned,
        picked,
        teammate_intents
    )
    
    # First 3 unavailable, should fallback to 4 and 5
    assert available == [4, 5]


def test_filter_available_champions_all_unavailable():
    """Test when all candidates are unavailable."""
    candidates = [1, 2, 3]
    pickable_ids = {1, 2, 3}
    bannable_ids = set()
    banned = {1, 2, 3}
    picked = set()
    teammate_intents = set()
    
    available = filter_available_champions(
        candidates,
        pickable_ids,
        bannable_ids,
        'pick',
        banned,
        picked,
        teammate_intents
    )
    
    assert available == []


def test_should_hover_during_planning():
    """Test PLANNING phase detection."""
    session_planning = {
        'timer': {
            'phase': 'PLANNING'
        }
    }
    assert should_hover_during_planning(session_planning) is True
    
    session_ban = {
        'timer': {
            'phase': 'BAN_PICK'
        }
    }
    assert should_hover_during_planning(session_ban) is False
    
    session_finalization = {
        'timer': {
            'phase': 'FINALIZATION'
        }
    }
    assert should_hover_during_planning(session_finalization) is False


def test_should_hover_during_planning_null():
    """Test PLANNING detection with null data."""
    assert should_hover_during_planning(None) is False
    assert should_hover_during_planning({}) is False
    assert should_hover_during_planning({'timer': {}}) is False
