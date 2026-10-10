"""Find and authenticate with the League Client."""
import os
import re
import psutil
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ClientInfo:
    """League Client connection information."""
    
    def __init__(self, port: int, password: str, install_dir: Optional[str] = None):
        self.port = port
        self.password = password
        self.install_dir = install_dir
    
    def __repr__(self):
        return f"ClientInfo(port={self.port}, password='***', install_dir={self.install_dir})"


def find_lockfile(custom_path: Optional[str] = None) -> Optional[ClientInfo]:
    """
    Find and parse the League Client lockfile.
    
    Args:
        custom_path: Optional custom path to the lockfile
        
    Returns:
        ClientInfo if found, None otherwise
    """
    lockfile_path = custom_path or r"C:\Riot Games\League of Legends\lockfile"
    
    try:
        if not os.path.exists(lockfile_path):
            logger.debug(f"Lockfile not found at {lockfile_path}")
            return None
        
        with open(lockfile_path, 'r') as f:
            content = f.read()
        
        # Format: LeagueClient:<pid>:<port>:<password>:<protocol>
        parts = content.split(':')
        if len(parts) >= 4:
            port = int(parts[2])
            password = parts[3]
            install_dir = str(Path(lockfile_path).parent)
            
            logger.info(f"Found lockfile: port={port}, install_dir={install_dir}")
            return ClientInfo(port=port, password=password, install_dir=install_dir)
    except Exception as e:
        logger.debug(f"Error reading lockfile: {e}")
    
    return None


def find_client_process() -> Optional[ClientInfo]:
    """
    Find the League Client process and extract connection info from command line.
    
    Returns:
        ClientInfo if found, None otherwise
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
            try:
                if proc.info['name'] == 'LeagueClientUx.exe':
                    cmdline = proc.info['cmdline']
                    if not cmdline:
                        continue
                    
                    port = None
                    password = None
                    install_dir = None
                    
                    # Extract port from --app-port
                    for i, arg in enumerate(cmdline):
                        if arg == '--app-port' and i + 1 < len(cmdline):
                            port = int(cmdline[i + 1])
                        elif arg == '--remoting-auth-token' and i + 1 < len(cmdline):
                            password = cmdline[i + 1]
                    
                    # Get install directory from executable path
                    if proc.info['exe']:
                        install_dir = str(Path(proc.info['exe']).parent)
                    
                    if port and password:
                        logger.info(f"Found client process: port={port}, install_dir={install_dir}")
                        return ClientInfo(port=port, password=password, install_dir=install_dir)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.debug(f"Error finding client process: {e}")
    
    return None


def get_client_info() -> Optional[ClientInfo]:
    """
    Get League Client connection info using multiple methods.
    
    Tries lockfile first, then falls back to process detection.
    
    Returns:
        ClientInfo if found, None otherwise
    """
    # Try default lockfile location
    info = find_lockfile()
    if info:
        return info
    
    # Try finding process
    info = find_client_process()
    if info:
        # If we found via process, try to find lockfile in that install dir
        if info.install_dir:
            lockfile_path = os.path.join(info.install_dir, 'lockfile')
            lockfile_info = find_lockfile(lockfile_path)
            if lockfile_info:
                return lockfile_info
        return info
    
    return None
