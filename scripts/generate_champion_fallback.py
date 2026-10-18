"""Generate fallback champion data for offline use."""
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from features.champion_data import ChampionDataProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Generate fallback champion data."""
    output_file = Path(__file__).parent.parent / "data" / "champion_data_fallback.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info("Fetching champion data from Data Dragon...")
    
    provider = ChampionDataProvider()
    
    try:
        # Fetch fresh data
        champion_data = provider._fetch_from_ddragon()
        
        # Save as fallback
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(champion_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Generated fallback data with {len(champion_data)} champions")
        logger.info(f"Saved to {output_file}")
        logger.info(f"File size: {output_file.stat().st_size / 1024:.1f} KB")
        
        # Show a few examples
        logger.info("\nExample champions:")
        for champ_id in sorted(champion_data.keys())[:5]:
            champ = champion_data[champ_id]
            logger.info(f"  {champ['name_en']} {champ['name_zh_tw']} (ID: {champ_id})")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to generate fallback: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
