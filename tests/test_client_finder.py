"""Tests for client finder module."""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, mock_open
from lcu.client_finder import (
    ClientInfo,
    parse_lockfile,
    find_client_process,
    get_client_info,
    discover_riot_install_paths
)


def test_client_info_creation():
    """Test ClientInfo object creation."""
    info = ClientInfo(port=12345, password="test123", install_dir="C:\\Riot Games\\League of Legends")
    assert info.port == 12345
    assert info.password == "test123"
    assert info.install_dir == "C:\\Riot Games\\League of Legends"


def test_client_info_repr():
    """Test ClientInfo string representation hides password."""
    info = ClientInfo(port=12345, password="secret", install_dir="/path")
    repr_str = repr(info)
    assert "12345" in repr_str
    assert "secret" not in repr_str
    assert "***" in repr_str


def test_parse_lockfile_success():
    """Test successful lockfile parsing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        # Format: LeagueClient:<pid>:<port>:<password>:<protocol>
        f.write("LeagueClient:12345:54321:mypassword:https")
        lockfile_path = f.name
    
    try:
        info = parse_lockfile(lockfile_path)
        assert info is not None
        assert info.port == 54321
        assert info.password == "mypassword"
        assert info.install_dir is not None
    finally:
        os.unlink(lockfile_path)


def test_parse_lockfile_not_found():
    """Test lockfile not found."""
    info = parse_lockfile("/nonexistent/path/lockfile")
    assert info is None


def test_parse_lockfile_invalid_format():
    """Test invalid lockfile format."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("invalid content")
        lockfile_path = f.name
    
    try:
        info = parse_lockfile(lockfile_path)
        assert info is None
    finally:
        os.unlink(lockfile_path)


@patch('psutil.process_iter')
def test_find_client_process_success_with_cmdline(mock_process_iter):
    """Test finding client via process with command line."""
    mock_proc = Mock()
    mock_proc.info = {
        'pid': 12345,
        'name': 'LeagueClientUx.exe',
        'cmdline': ['LeagueClientUx.exe', '--app-port', '54321', '--remoting-auth-token', 'mytoken'],
        'exe': 'C:\\Riot Games\\League of Legends\\LeagueClientUx.exe'
    }
    mock_process_iter.return_value = [mock_proc]
    
    info = find_client_process()
    assert info is not None
    assert info.port == 54321
    assert info.password == "mytoken"
    assert info.install_dir is not None


@patch('lcu.client_finder.parse_lockfile')
@patch('psutil.process_iter')
def test_find_client_process_fallback_to_lockfile(mock_process_iter, mock_parse_lockfile):
    """Test finding client via process exe path when cmdline is unavailable."""
    expected_info = ClientInfo(port=12345, password="test", install_dir="C:\\Riot Games\\League of Legends")
    
    mock_proc = Mock()
    mock_proc.info = {
        'pid': 12345,
        'name': 'LeagueClient.exe',
        'cmdline': None,  # Simulates no access to cmdline
        'exe': 'C:\\Riot Games\\League of Legends\\LeagueClient.exe'
    }
    mock_process_iter.return_value = [mock_proc]
    mock_parse_lockfile.return_value = expected_info
    
    info = find_client_process()
    assert info is not None
    assert info == expected_info
    mock_parse_lockfile.assert_called_once()


@patch('psutil.process_iter')
def test_find_client_process_not_found(mock_process_iter):
    """Test client process not found."""
    mock_proc = Mock()
    mock_proc.info = {
        'pid': 12345,
        'name': 'some_other_process.exe',
        'cmdline': [],
        'exe': '/path/to/other.exe'
    }
    mock_process_iter.return_value = [mock_proc]
    
    info = find_client_process()
    assert info is None


@patch('lcu.client_finder.find_client_process')
def test_get_client_info_via_process(mock_find_process):
    """Test finding client via process (tried first)."""
    expected_info = ClientInfo(port=12345, password="test", install_dir="/path")
    mock_find_process.return_value = expected_info
    
    info = get_client_info()
    assert info == expected_info
    mock_find_process.assert_called_once()


@patch('lcu.client_finder.parse_lockfile')
@patch('lcu.client_finder.find_lockfile_in_install_dirs')
@patch('lcu.client_finder.find_client_process')
def test_get_client_info_fallback_chain(mock_find_process, mock_find_install_dirs, mock_parse_lockfile):
    """Test fallback chain: process -> install dirs -> default."""
    expected_info = ClientInfo(port=12345, password="test", install_dir="/path")
    
    # Process detection fails
    mock_find_process.return_value = None
    # Install dir discovery fails
    mock_find_install_dirs.return_value = None
    # Default location succeeds
    mock_parse_lockfile.return_value = expected_info
    
    info = get_client_info()
    assert info == expected_info
    mock_find_process.assert_called_once()
    mock_find_install_dirs.assert_called_once()
    mock_parse_lockfile.assert_called_once()


def test_discover_riot_install_paths_returns_list():
    """Test that discover_riot_install_paths returns a list."""
    # Just verify it returns a list without errors
    # (actual discovery depends on system state, hard to test in unit tests)
    paths = discover_riot_install_paths()
    assert isinstance(paths, list)
