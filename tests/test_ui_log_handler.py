"""Tests for UILogHandler thread safety."""
import logging
import threading
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_ui import UILogHandler


def test_ui_log_handler_no_deadlock():
    """Test that UILogHandler doesn't deadlock when used from multiple threads."""
    handler = UILogHandler(max_logs=50)
    
    # Create a test logger
    test_logger = logging.Logger('test', level=logging.DEBUG)
    test_logger.addHandler(handler)
    
    success = threading.Event()
    errors = []
    
    def log_from_thread(thread_id, count):
        """Log messages from a thread."""
        try:
            for i in range(count):
                test_logger.info(f"Thread {thread_id} message {i}")
                time.sleep(0.001)  # Small delay to increase interleaving
            success.set()
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")
    
    # Start multiple threads logging concurrently
    threads = []
    for i in range(5):
        t = threading.Thread(target=log_from_thread, args=(i, 10))
        threads.append(t)
        t.start()
    
    # Wait for all threads with a timeout
    timeout = 5.0  # 5 seconds should be plenty
    start = time.time()
    for t in threads:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            break
        t.join(timeout=remaining)
    
    # Check if any threads are still alive (would indicate deadlock)
    alive_threads = [t for t in threads if t.is_alive()]
    
    assert not errors, f"Errors during logging: {errors}"
    assert not alive_threads, "Threads are still alive - possible deadlock"
    assert success.is_set(), "Success event was not set"
    
    # Verify logs were captured
    logs = handler.get_logs()
    assert len(logs) > 0, "No logs were captured"
    assert len(logs) <= 50, f"Log buffer exceeded max_logs: {len(logs)}"


def test_ui_log_handler_get_logs_thread_safe():
    """Test that get_logs() is thread-safe."""
    handler = UILogHandler(max_logs=20)
    
    test_logger = logging.Logger('test', level=logging.DEBUG)
    test_logger.addHandler(handler)
    
    errors = []
    results = []
    
    def log_and_read():
        """Log and read concurrently."""
        try:
            for i in range(10):
                test_logger.info(f"Message {i}")
                logs = handler.get_logs()
                results.append(len(logs))
                time.sleep(0.001)
        except Exception as e:
            errors.append(str(e))
    
    threads = [threading.Thread(target=log_and_read) for _ in range(3)]
    for t in threads:
        t.start()
    
    for t in threads:
        t.join(timeout=3.0)
    
    alive_threads = [t for t in threads if t.is_alive()]
    
    assert not errors, f"Errors: {errors}"
    assert not alive_threads, "Threads are still alive - possible deadlock"
    assert len(results) > 0, "No results captured"


if __name__ == '__main__':
    test_ui_log_handler_no_deadlock()
    test_ui_log_handler_get_logs_thread_safe()
    print("All tests passed!")
