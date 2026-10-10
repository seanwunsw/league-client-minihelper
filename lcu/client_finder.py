"""Find and authenticate with the League Client."""
import os
import json
import psutil
import logging
from pathlib import Path
from typing import Optional, List
import string

logger = logging.getLogger(__name__)


class ClientInfo:
    """League Client connection information."""
    
    def __init__(self, port: int, password: str, install_dir: Optional[str] = None):
        self.port = port
        self.password = password
        self.install_dir = install_dir
    
    def __repr__(self):
        return f"ClientInfo(port={self.port}, password='***', install_dir={self.install_dir})"


def parse_lockfile(lockfile_path: str) -> Optional[ClientInfo]:
    """
    Parse a lockfile and return ClientInfo.
    
    Args:
        lockfile_path: Path to the lockfile
        
    Returns:
        ClientInfo if valid, None otherwise
    """
    try:
        if not os.path.exists(lockfile_path):
            return None
        
        with open(lockfile_path, 'r') as f:
            content = f.read().strip()
        
        # Format: LeagueClient:<pid>:<port>:<password>:<protocol>
        parts = content.split(':')
        if len(parts) >= 4:
            port = int(parts[2])
            password = parts[3]
            install_dir = str(Path(lockfile_path).parent)
            
            logger.info(f"Found lockfile: port={port}, install_dir={install_dir}")
            return ClientInfo(port=port, password=password, install_dir=install_dir)
    except Exception as e:
        logger.debug(f"Error reading lockfile at {lockfile_path}: {e}")
    
    return None


def discover_riot_install_paths() -> List[str]:
    """
    Discover Riot Games install paths from metadata and common locations.
    
    Returns:
        List of potential League of Legends install directories
    """
    paths = []
    
    # Method 1: Check RiotClientInstalls.json
    try:
        riot_installs_path = r"C:\ProgramData\Riot Games\RiotClientInstalls.json"
        if os.path.exists(riot_installs_path):
            logger.debug(f"Reading {riot_installs_path}")
            with open(riot_installs_path, 'r') as f:
                data = json.load(f)
                if 'patchlines' in data:
                    for patchline_name, patchline_data in data['patchlines'].items():
                        if patchline_data and 'product_install_full_path' in patchline_data:
                            path = patchline_data['product_install_full_path']
                            if path and 'League of Legends' in path:
                                paths.append(path)
                                logger.debug(f"Found install path from RiotClientInstalls.json: {path}")
    except Exception as e:
        logger.debug(f"Error reading RiotClientInstalls.json: {e}")
    
    # Method 2: Check product_settings.yaml files in Metadata
    try:
        metadata_base = r"C:\ProgramData\Riot Games\Metadata"
        if os.path.exists(metadata_base):
            logger.debug(f"Scanning {metadata_base}")
            for item in os.listdir(metadata_base):
                item_path = os.path.join(metadata_base, item)
                if os.path.isdir(item_path) and 'league_of_legends' in item.lower():
                    # Look for .product_settings.yaml files
                    for file in os.listdir(item_path):
                        if file.endswith('.product_settings.yaml'):
                            yaml_path = os.path.join(item_path, file)
                            try:
                                with open(yaml_path, 'r', encoding='utf-8') as f:
                                    for line in f:
                                        if 'product_install_full_path' in line:
                                            # Extract path (simple parsing, not full YAML)
                                            if ':' in line:
                                                path = line.split(':', 1)[1].strip().strip('"\'')
                                                if path and os.path.exists(path):
                                                    paths.append(path)
                                                    logger.debug(f"Found install path from {file}: {path}")
                            except Exception as e:
                                logger.debug(f"Error reading {yaml_path}: {e}")
    except Exception as e:
        logger.debug(f"Error scanning Metadata folder: {e}")
    
    # Method 3: Scan common drives for Riot Games installations
    drives = []
    try:
        # Get available drives on Windows
        if os.name == 'nt':
            drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
            logger.debug(f"Scanning drives: {drives}")
    except Exception as e:
        logger.debug(f"Error getting drive list: {e}")
    
    # Check common paths on each drive
    common_paths = [
        "Riot Games\\League of Legends",
        "Riot Games\\League of Legends (PBE)",
        "game\\Riot Games\\League of Legends",
        "game\\Riot Games\\League of Legends (PBE)",
        "Games\\Riot Games\\League of Legends",
        "Games\\Riot Games\\League of Legends (PBE)",
        "Program Files\\Riot Games\\League of Legends",
        "Program Files (x86)\\Riot Games\\League of Legends",
    ]
    
    for drive in drives:
        for rel_path in common_paths:
            full_path = os.path.join(drive, rel_path)
            if os.path.exists(full_path):
                paths.append(full_path)
                logger.debug(f"Found install path by scanning: {full_path}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for path in paths:
        normalized = os.path.normpath(path).lower()
        if normalized not in seen:
            seen.add(normalized)
            unique_paths.append(path)
    
    logger.info(f"Discovered {len(unique_paths)} potential install paths")
    return unique_paths


def find_lockfile_in_install_dirs() -> Optional[ClientInfo]:
    """
    Search for lockfile in discovered install directories.
    
    Returns:
        ClientInfo if lockfile found, None otherwise
    """
    install_dirs = discover_riot_install_paths()
    
    for install_dir in install_dirs:
        lockfile_path = os.path.join(install_dir, 'lockfile')
        logger.debug(f"Checking for lockfile at: {lockfile_path}")
        info = parse_lockfile(lockfile_path)
        if info:
            return info
    
    return None


def find_client_process() -> Optional[ClientInfo]:
    """
    Find the League Client process and extract connection info.
    
    Looks for LeagueClientUx.exe and LeagueClient.exe processes.
    Tries to read command line args, falls back to finding lockfile via exe path.
    
    Returns:
        ClientInfo if found, None otherwise
    """
    target_processes = ['LeagueClientUx.exe', 'LeagueClient.exe']
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
            try:
                proc_name = proc.info.get('name', '')
                if proc_name not in target_processes:
                    continue
                
                logger.debug(f"Found {proc_name} process (PID: {proc.info.get('pid')})")
                
                # Try to get install directory from exe path
                install_dir = None
                exe_path = proc.info.get('exe')
                if exe_path:
                    install_dir = str(Path(exe_path).parent)
                    logger.debug(f"Process exe path: {exe_path}")
                    logger.debug(f"Install dir from exe: {install_dir}")
                else:
                    logger.debug(f"Could not read exe path for {proc_name} (may need elevation)")
                
                # Try to read command line (may fail without elevation)
                cmdline = proc.info.get('cmdline')
                if cmdline:
                    port = None
                    password = None
                    
                    # Extract port and token from command line
                    for i, arg in enumerate(cmdline):
                        if arg == '--app-port' and i + 1 < len(cmdline):
                            port = int(cmdline[i + 1])
                        elif arg == '--remoting-auth-token' and i + 1 < len(cmdline):
                            password = cmdline[i + 1]
                    
                    if port and password:
                        logger.info(f"Found client via process cmdline: port={port}, install_dir={install_dir}")
                        return ClientInfo(port=port, password=password, install_dir=install_dir)
                    else:
                        logger.debug(f"Command line did not contain port/token")
                else:
                    logger.debug(f"Could not read command line for {proc_name} (may need elevation)")
                
                # If we couldn't get cmdline but have install_dir, try lockfile
                if install_dir:
                    lockfile_path = os.path.join(install_dir, 'lockfile')
                    logger.debug(f"Trying lockfile at process install dir: {lockfile_path}")
                    info = parse_lockfile(lockfile_path)
                    if info:
                        return info
                
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"Process access error: {e}")
                continue
    except Exception as e:
        logger.debug(f"Error finding client process: {e}")
    
    return None


def get_client_info() -> Optional[ClientInfo]:
    """
    Get League Client connection info using multiple discovery methods.
    
    Tries (in order):
    1. Process detection (with cmdline or lockfile via exe path)
    2. Lockfile in discovered install directories
    3. Default lockfile location (C:\\Riot Games\\League of Legends\\lockfile)
    
    Returns:
        ClientInfo if found, None otherwise
    """
    logger.debug("=== Starting client detection ===")
    
    # Method 1: Try finding running process first (fastest if it works)
    logger.debug("Method 1: Detecting running League Client process...")
    info = find_client_process()
    if info:
        logger.info(f"Success: Found client via running process")
        return info
    
    # Method 2: Search for lockfile in discovered install directories
    logger.debug("Method 2: Searching for lockfile in discovered install directories...")
    info = find_lockfile_in_install_dirs()
    if info:
        logger.info(f"Success: Found client via install directory discovery")
        return info
    
    # Method 3: Try default location as last resort
    logger.debug("Method 3: Trying default lockfile location...")
    default_lockfile = r"C:\Riot Games\League of Legends\lockfile"
    info = parse_lockfile(default_lockfile)
    if info:
        logger.info(f"Success: Found client at default location")
        return info
    
    logger.warning("Failed to find League Client using all detection methods")
    return None
