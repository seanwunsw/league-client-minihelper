"""Champion data fetcher with multi-language support."""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class ChampionDataProvider:
    """Fetch and cache champion data with multi-language names."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize champion data provider.
        
        Args:
            cache_dir: Directory for cache files (defaults to app directory)
        """
        if cache_dir is None:
            # Use app directory for cache
            cache_dir = Path(os.getcwd())
        
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "champion_data_cache.json"
        self.fallback_file = self._get_fallback_path()
        self.champion_data = {}
        
    def _get_fallback_path(self) -> Path:
        """Get path to bundled fallback data."""
        try:
            # Try PyInstaller bundle
            import sys
            if getattr(sys, 'frozen', False):
                base_path = Path(sys._MEIPASS)
            else:
                base_path = Path(__file__).parent.parent
            return base_path / "data" / "champion_data_fallback.json"
        except Exception:
            return Path(__file__).parent.parent / "data" / "champion_data_fallback.json"
    
    def fetch_champion_data(self, client_champions: Optional[list] = None) -> Dict[int, Dict]:
        """
        Fetch champion data with multi-language names.
        
        Args:
            client_champions: Optional list from client's champion-summary
            
        Returns:
            Dict mapping champion ID to data with names in multiple languages
        """
        # Try to load from cache first
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # Normalize data: convert string keys to int, remove old fields
                    normalized_data = self._normalize_champion_data(cached_data)
                    logger.info(f"Loaded {len(normalized_data)} champions from cache")
                    self.champion_data = normalized_data
                    
                    # Merge with client data if provided
                    if client_champions:
                        self._merge_client_data(client_champions)
                    
                    return self.champion_data
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        
        # Try to fetch from Data Dragon
        try:
            self.champion_data = self._fetch_from_ddragon()
            
            # Merge with client data if provided
            if client_champions:
                self._merge_client_data(client_champions)
            
            # Save to cache
            self._save_cache()
            
            return self.champion_data
            
        except Exception as e:
            logger.warning(f"Failed to fetch from Data Dragon: {e}")
            
            # Fall back to bundled data
            return self._load_fallback()
    
    def _fetch_from_ddragon(self) -> Dict[int, Dict]:
        """Fetch champion data from Riot Data Dragon."""
        logger.info("Fetching champion data from Data Dragon...")
        
        # Get latest version
        version = self._get_latest_version()
        logger.info(f"Latest Data Dragon version: {version}")
        
        # Fetch champion data for each language
        en_data = self._fetch_champion_json(version, 'en_US')
        zh_tw_data = self._fetch_champion_json(version, 'zh_TW')
        
        # Build combined data (id derived from key, only store names)
        champion_data = {}
        
        for champ_id, champ_info in en_data.items():
            # Use numeric key as champion ID
            champ_key = int(champ_info['key'])
            
            champion_data[champ_key] = {
                'name_en': champ_info['name'],
                'name_zh_tw': zh_tw_data.get(champ_id, {}).get('name', champ_info['name'])
            }
        
        logger.info(f"Fetched {len(champion_data)} champions from Data Dragon")
        return champion_data
    
    def _get_latest_version(self) -> str:
        """Get latest Data Dragon version."""
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                versions = json.loads(response.read().decode('utf-8'))
                return versions[0]  # First version is latest
        except Exception as e:
            logger.error(f"Failed to get latest version: {e}")
            raise
    
    def _fetch_champion_json(self, version: str, locale: str) -> Dict:
        """Fetch champion.json for a specific locale."""
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{locale}/champion.json"
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('data', {})
        except Exception as e:
            logger.warning(f"Failed to fetch {locale} champion data: {e}")
            return {}
    
    def _merge_client_data(self, client_champions: list):
        """Merge client champion data to include new champions."""
        for champ in client_champions:
            champ_id = champ.get('id', 0)
            champ_name = champ.get('name', '')
            
            if champ_id > 0 and champ_id not in self.champion_data:
                # New champion not in Data Dragon yet
                self.champion_data[champ_id] = {
                    'name_en': champ_name,
                    'name_zh_tw': champ_name
                }
                logger.info(f"Added new champion from client: {champ_name} ({champ_id})")
    
    def _normalize_champion_data(self, data: Dict) -> Dict[int, Dict]:
        """
        Normalize champion data: convert string keys to int, keep only name_en and name_zh_tw.
        Handles old cache files that may have id, internal_name, or name_zh_cn fields.
        
        Args:
            data: Raw champion data dict (may have string keys or old fields)
            
        Returns:
            Normalized dict with int keys and only name_en/name_zh_tw
        """
        normalized = {}
        for key, value in data.items():
            # Convert key to int (handles both string and int keys)
            champ_id = int(key)
            
            # Keep only name fields we support
            normalized[champ_id] = {
                'name_en': value.get('name_en', f'Champion {champ_id}'),
                'name_zh_tw': value.get('name_zh_tw', value.get('name_en', f'Champion {champ_id}'))
            }
        
        return normalized
    
    def _save_cache(self):
        """Save champion data to cache file."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.champion_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved champion data cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def _load_fallback(self) -> Dict[int, Dict]:
        """Load bundled fallback data."""
        if not self.fallback_file.exists():
            logger.warning(f"Fallback file not found: {self.fallback_file}")
            return {}
        
        try:
            with open(self.fallback_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Normalize data: convert string keys to int, remove old fields
                normalized = self._normalize_champion_data(data)
                logger.info(f"Loaded {len(normalized)} champions from fallback")
                self.champion_data = normalized
                return normalized
        except Exception as e:
            logger.error(f"Failed to load fallback: {e}")
            return {}
    
    def get_display_name(self, champ_id: int) -> str:
        """
        Get display name for a champion (English + Traditional Chinese).
        
        Args:
            champ_id: Champion ID
            
        Returns:
            Display name like "Ahri 阿璃"
        """
        champ_data = self.champion_data.get(champ_id, {})
        name_en = champ_data.get('name_en', f'Champion {champ_id}')
        name_zh_tw = champ_data.get('name_zh_tw', '')
        
        if name_zh_tw and name_zh_tw != name_en:
            return f"{name_en} {name_zh_tw}"
        return name_en
    
    def search_champions(self, query: str) -> list:
        """
        Search champions by name (English or Traditional Chinese).
        
        Args:
            query: Search query (case-insensitive, partial match)
            
        Returns:
            List of (id, display_name) tuples matching the query
        """
        if not query:
            # Return all champions
            results = []
            for champ_id, champ_data in sorted(self.champion_data.items(), 
                                               key=lambda x: x[1].get('name_en', '')):
                results.append((champ_id, self.get_display_name(champ_id)))
            return results
        
        query_lower = query.lower()
        results = []
        
        for champ_id, champ_data in self.champion_data.items():
            name_en = champ_data.get('name_en', '').lower()
            name_zh_tw = champ_data.get('name_zh_tw', '').lower()
            
            # Check if query matches any name (partial, case-insensitive)
            if (query_lower in name_en or 
                query_lower in name_zh_tw):
                results.append((champ_id, self.get_display_name(champ_id)))
        
        # Sort by English name
        results.sort(key=lambda x: x[1])
        return results
