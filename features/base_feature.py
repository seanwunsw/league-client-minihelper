"""Base class for features."""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BaseFeature(ABC):
    """Base class for all features."""
    
    def __init__(self, config: dict):
        self.config = config
        self.enabled = True
    
    @abstractmethod
    def initialize(self, event_bus, api_client):
        """
        Initialize the feature.
        
        Args:
            event_bus: EventBus instance for subscribing to events
            api_client: LCUApiClient instance for API calls
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get feature name."""
        pass
    
    def get_settings_schema(self) -> Dict[str, Any]:
        """
        Get settings schema for UI rendering.
        
        Returns dict with schema for each setting:
        {
            'setting_name': {
                'type': 'boolean' | 'number' | 'string' | 'range',
                'label': 'Display Name',
                'description': 'Help text',
                'default': default_value,
                'min': min_value,  # for number/range
                'max': max_value,  # for number/range
                'current': current_value
            }
        }
        """
        return {}
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings values."""
        return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current feature status for display."""
        return {
            'enabled': self.enabled
        }
    
    def update_setting(self, setting_name: str, value: Any) -> bool:
        """
        Update a setting value.
        
        Args:
            setting_name: Name of the setting
            value: New value
            
        Returns:
            True if successful, False otherwise
        """
        return False
    
    def enable(self):
        """Enable the feature."""
        self.enabled = True
        logger.info(f"Feature '{self.get_name()}' enabled")
    
    def disable(self):
        """Disable the feature."""
        self.enabled = False
        logger.info(f"Feature '{self.get_name()}' disabled")
