"""Event bus for dispatching LCU events."""
import logging
from typing import Callable, Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventBus:
    """Central event dispatcher for LCU events."""
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.wildcard_handlers: List[Callable] = []
    
    def subscribe(self, uri_pattern: str, handler: Callable):
        """
        Subscribe to events matching a URI pattern.
        
        Args:
            uri_pattern: URI pattern to match (use '*' for wildcard)
            handler: Callback function(uri, event_data)
        """
        if uri_pattern == '*':
            self.wildcard_handlers.append(handler)
            logger.debug(f"Subscribed handler to all events")
        else:
            self.handlers[uri_pattern].append(handler)
            logger.debug(f"Subscribed handler to {uri_pattern}")
    
    def publish(self, uri: str, event_data: dict):
        """
        Publish an event to all matching subscribers.
        
        Args:
            uri: Event URI
            event_data: Event data
        """
        # Call wildcard handlers
        for handler in self.wildcard_handlers:
            try:
                handler(uri, event_data)
            except Exception as e:
                logger.error(f"Error in wildcard event handler: {e}")
        
        # Call specific URI handlers
        if uri in self.handlers:
            for handler in self.handlers[uri]:
                try:
                    handler(uri, event_data)
                except Exception as e:
                    logger.error(f"Error in event handler for {uri}: {e}")
        
        # Check for partial matches (e.g., /lol-matchmaking/v1/* matches /lol-matchmaking/v1/ready-check)
        for pattern, pattern_handlers in self.handlers.items():
            if pattern.endswith('*') and uri.startswith(pattern[:-1]):
                for handler in pattern_handlers:
                    try:
                        handler(uri, event_data)
                    except Exception as e:
                        logger.error(f"Error in pattern event handler for {pattern}: {e}")
