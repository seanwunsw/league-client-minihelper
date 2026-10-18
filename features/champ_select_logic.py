"""
Champion select decision logic - pure functions for testing.
"""
from typing import Optional, List, Dict, Any, Set


def get_assigned_position(session: Dict[str, Any], local_player_cell_id: int) -> str:
    """
    Get assigned position for local player from session.
    
    Args:
        session: Champion select session data
        local_player_cell_id: Local player's cell ID
        
    Returns:
        Position string (e.g., 'top', 'jungle', 'middle', 'bottom', 'utility') or 'default'
    """
    if not session:
        return 'default'
    
    my_team = session.get('myTeam', [])
    for member in my_team:
        if member.get('cellId') == local_player_cell_id:
            position = member.get('assignedPosition', '')
            if position:
                return position.lower()
    
    return 'default'


def flatten_actions(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flatten session.actions (list of lists) to a single list.
    
    Args:
        session: Champion select session data
        
    Returns:
        Flattened list of actions
    """
    if not session:
        return []
    
    actions = session.get('actions', [])
    if not actions:
        return []
    
    flattened = []
    for action_group in actions:
        if isinstance(action_group, list):
            flattened.extend(action_group)
    
    return flattened


def find_my_action(
    session: Dict[str, Any],
    local_player_cell_id: int
) -> Optional[Dict[str, Any]]:
    """
    Find the current action for the local player.
    
    Args:
        session: Champion select session data
        local_player_cell_id: Local player's cell ID
        
    Returns:
        Action dict or None if no active action
    """
    if not session:
        return None
    
    actions = flatten_actions(session)
    
    for action in actions:
        if (action.get('actorCellId') == local_player_cell_id and
            action.get('isInProgress') and
            not action.get('completed')):
            return action
    
    return None


def get_banned_champions(session: Dict[str, Any]) -> Set[int]:
    """
    Get set of all banned champion IDs (including completed ban actions).
    
    Args:
        session: Champion select session data
        
    Returns:
        Set of banned champion IDs
    """
    if not session:
        return set()
    
    banned = set()
    
    # Get bans from bans arrays
    bans = session.get('bans', {})
    my_team_bans = bans.get('myTeamBans', [])
    their_team_bans = bans.get('theirTeamBans', [])
    
    for ban_id in my_team_bans:
        if ban_id and ban_id > 0:
            banned.add(ban_id)
    
    for ban_id in their_team_bans:
        if ban_id and ban_id > 0:
            banned.add(ban_id)
    
    # Get completed ban actions
    actions = flatten_actions(session)
    for action in actions:
        if action.get('type') == 'ban' and action.get('completed'):
            champ_id = action.get('championId', 0)
            if champ_id and champ_id > 0:
                banned.add(champ_id)
    
    return banned


def get_picked_champions(session: Dict[str, Any]) -> Set[int]:
    """
    Get set of all picked champion IDs (completed pick actions).
    
    Args:
        session: Champion select session data
        
    Returns:
        Set of picked champion IDs
    """
    if not session:
        return set()
    
    picked = set()
    actions = flatten_actions(session)
    
    for action in actions:
        if action.get('type') == 'pick' and action.get('completed'):
            champ_id = action.get('championId', 0)
            if champ_id and champ_id > 0:
                picked.add(champ_id)
    
    return picked


def get_teammate_intents(
    session: Dict[str, Any],
    local_player_cell_id: int
) -> Set[int]:
    """
    Get set of teammate champion intents/hovers (for ban filtering).
    
    Args:
        session: Champion select session data
        local_player_cell_id: Local player's cell ID
        
    Returns:
        Set of teammate intent champion IDs
    """
    if not session:
        return set()
    
    intents = set()
    
    # Get myTeam championPickIntent
    my_team = session.get('myTeam', [])
    for member in my_team:
        if member.get('cellId') != local_player_cell_id:
            intent = member.get('championPickIntent', 0)
            if intent and intent > 0:
                intents.add(intent)
    
    # Get teammates' pick action championIds (hovers)
    actions = flatten_actions(session)
    for action in actions:
        if (action.get('type') == 'pick' and
            action.get('actorCellId') != local_player_cell_id and
            not action.get('completed')):
            champ_id = action.get('championId', 0)
            if champ_id and champ_id > 0:
                intents.add(champ_id)
    
    return intents


def filter_available_champions(
    candidates: List[int],
    pickable_ids: Set[int],
    bannable_ids: Set[int],
    action_type: str,
    banned_champions: Set[int],
    picked_champions: Set[int],
    teammate_intents: Set[int]
) -> List[int]:
    """
    Filter candidate champions to only available ones.
    
    Args:
        candidates: List of candidate champion IDs in priority order
        pickable_ids: Set of pickable champion IDs from API
        bannable_ids: Set of bannable champion IDs from API
        action_type: 'ban' or 'pick'
        banned_champions: Set of already banned champion IDs
        picked_champions: Set of already picked champion IDs
        teammate_intents: Set of teammate intent champion IDs
        
    Returns:
        Filtered list of available champion IDs
    """
    available = []
    
    for champ_id in candidates:
        if not champ_id or champ_id <= 0:
            continue
        
        # Check if already banned or picked
        if champ_id in banned_champions or champ_id in picked_champions:
            continue
        
        # For bans, skip teammate intents
        if action_type == 'ban' and champ_id in teammate_intents:
            continue
        
        # Check if in allowed list
        if action_type == 'ban':
            if champ_id not in bannable_ids:
                continue
        elif action_type == 'pick':
            if champ_id not in pickable_ids:
                continue
        
        available.append(champ_id)
    
    return available


def should_hover_during_planning(session: Dict[str, Any]) -> bool:
    """
    Check if we should hover during PLANNING phase.
    
    Args:
        session: Champion select session data
        
    Returns:
        True if timer.phase is 'PLANNING'
    """
    if not session:
        return False
    
    timer = session.get('timer', {})
    phase = timer.get('phase', '')
    return phase == 'PLANNING'
