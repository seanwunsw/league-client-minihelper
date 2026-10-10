"""Tests for client finder module."""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from lcu.client_finder import (
    ClientInfo,
    find_lockfile,
    find_client_process,
    get_client_info
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


def test_find_lockfile_success():
    """Test successful lockfile parsing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        # Format: LeagueClient:<pid>:<port>:<password>:<protocol>
        f.write("LeagueClient:12345:54321:mypassword:https")
        lockfile_path = f.name
    
    try:
        info = find_lockfile(lockfile_path)
        assert info is not None
        assert info.port == 54321
        assert info.password == "mypassword"
        assert info.install_dir is not None
    finally:
        os.unlink(lockfile_path)


def test_find_lockfile_not_found():
    """Test lockfile not found."""
    info = find_lockfile("/nonexistent/path/lockfile")
    assert info is None


def test_find_lockfile_invalid_format():
    """Test invalid lockfile format."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("invalid content")
        lockfile_path = f.name
    
    try:
        info = find_lockfile(lockfile_path)
        assert info is None
    finally:
        os.unlink(lockfile_path)


@patch('psutil.process_iter')
def test_find_client_process_success(mock_process_iter):
    """Test finding client via process."""
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
    assert info.install_dir is not None  # Just verify it's set


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


@patch('lcu.client_finder.find_lockfile')
@patch('lcu.client_finder.find_client_process')
def test_get_client_info_lockfile_first(mock_find_process, mock_find_lockfile):
    """Test that lockfile is tried first."""
    expected_info = ClientInfo(port=12345, password="test", install_dir="/path")
    mock_find_lockfile.return_value = expected_info
    
    info = get_client_info()
    assert info == expected_info
    mock_find_lockfile.assert_called_once()
    mock_find_process.assert_not_called()


@patch('lcu.client_finder.find_lockfile')
@patch('lcu.client_finder.find_client_process')
def test_get_client_info_fallback_to_process(mock_find_process, mock_find_lockfile):
    """Test fallback to process detection."""
    expected_info = ClientInfo(port=12345, password="test", install_dir="/path")
    mock_find_lockfile.return_value = None
    mock_find_process.return_value = expected_info
    
    info = get_client_info()
    assert info == expected_info
    mock_find_lockfile.assert_called()
    mock_find_process.assert_called_once()
