"""Base class for features."""
import logging
from abc import ABC, abstractmethod

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
    
    def enable(self):
        """Enable the feature."""
        self.enabled = True
        logger.info(f"Feature '{self.get_name()}' enabled")
    
    def disable(self):
        """Disable the feature."""
        self.enabled = False
        logger.info(f"Feature '{self.get_name()}' disabled")
