"""Tests for event bus."""
import pytest
from unittest.mock import Mock
from core.event_bus import EventBus


def test_event_bus_subscribe_and_publish():
    """Test basic subscribe and publish."""
    bus = EventBus()
    handler = Mock()
    
    bus.subscribe('/test/event', handler)
    bus.publish('/test/event', {'key': 'value'})
    
    handler.assert_called_once_with('/test/event', {'key': 'value'})


def test_event_bus_wildcard_handler():
    """Test wildcard handler receives all events."""
    bus = EventBus()
    handler = Mock()
    
    bus.subscribe('*', handler)
    
    bus.publish('/test/event1', {'data': 1})
    bus.publish('/test/event2', {'data': 2})
    
    assert handler.call_count == 2


def test_event_bus_multiple_handlers():
    """Test multiple handlers for same event."""
    bus = EventBus()
    handler1 = Mock()
    handler2 = Mock()
    
    bus.subscribe('/test/event', handler1)
    bus.subscribe('/test/event', handler2)
    
    bus.publish('/test/event', {'data': 'test'})
    
    handler1.assert_called_once()
    handler2.assert_called_once()


def test_event_bus_pattern_matching():
    """Test pattern matching with wildcard."""
    bus = EventBus()
    handler = Mock()
    
    bus.subscribe('/lol-matchmaking/*', handler)
    
    bus.publish('/lol-matchmaking/v1/ready-check', {'state': 'InProgress'})
    
    handler.assert_called_once()


def test_event_bus_no_match():
    """Test that handler is not called for non-matching events."""
    bus = EventBus()
    handler = Mock()
    
    bus.subscribe('/test/event1', handler)
    bus.publish('/test/event2', {'data': 'test'})
    
    handler.assert_not_called()


def test_event_bus_handler_exception():
    """Test that exceptions in handlers don't break event bus."""
    bus = EventBus()
    
    def bad_handler(uri, data):
        raise Exception("Handler error")
    
    good_handler = Mock()
    
    bus.subscribe('/test/event', bad_handler)
    bus.subscribe('/test/event', good_handler)
    
    # Should not raise exception
    bus.publish('/test/event', {'data': 'test'})
    
    # Good handler should still be called
    good_handler.assert_called_once()
