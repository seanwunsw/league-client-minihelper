"""WebSocket client for League Client events."""
import websocket
import json
import threading
import logging
import time
import base64
from typing import Callable, Optional
import ssl

logger = logging.getLogger(__name__)


class LCUWebSocketClient:
    """WebSocket client for real-time LCU events."""
    
    def __init__(self, port: int, password: str, on_event: Callable[[str, dict], None]):
        self.port = port
        self.password = password
        self.on_event = on_event
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.connected = False
        self.subscriptions = set()
    
    def _create_auth_header(self) -> str:
        """Create Basic auth header."""
        credentials = f"riot:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def connect(self) -> bool:
        """
        Connect to LCU WebSocket.
        
        Returns:
            True if connection started, False otherwise
        """
        if self.running:
            return True
        
        try:
            url = f"wss://127.0.0.1:{self.port}/"
            
            def on_message(ws, message):
                try:
                    # Skip empty messages (subscribe acknowledgments)
                    if not message or not message.strip():
                        logger.debug("Received empty WebSocket message (likely subscribe ack)")
                        return
                    
                    # LCU WebSocket protocol: [opcode, eventName, eventData]
                    # eventData format: {uri: "...", eventType: "Create/Update/Delete", data: {...}}
                    data = json.loads(message)
                    
                    if isinstance(data, list) and len(data) >= 3:
                        opcode = data[0]
                        event_name = data[1]
                        event_data = data[2]
                        
                        if opcode == 8:  # Event message
                            uri = event_data.get('uri', '')
                            event_type = event_data.get('eventType', '')
                            
                            logger.debug(f"WS Event: opcode={opcode}, name={event_name}, uri={uri}, type={event_type}")
                            
                            # Call event handler with URI as key
                            if uri:
                                self.on_event(uri, event_data)
                        else:
                            logger.debug(f"WS Message: opcode={opcode}, data={data}")
                    else:
                        logger.debug(f"WS Message (unexpected format): {data}")
                        
                except json.JSONDecodeError as e:
                    logger.debug(f"Non-JSON WebSocket message (likely ack): {message[:100]}")
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
            
            def on_error(ws, error):
                logger.debug(f"WebSocket error: {error}")
                self.connected = False
            
            def on_close(ws, close_status_code, close_msg):
                logger.info("WebSocket connection closed")
                self.connected = False
            
            def on_open(ws):
                logger.info("WebSocket connection opened")
                self.connected = True
                
                # Subscribe to ready check events
                self._subscribe_to_event('OnJsonApiEvent_lol-matchmaking_v1_ready-check')
                
                # Subscribe to champion select events
                self._subscribe_to_event('OnJsonApiEvent_lol-champ-select_v1_session')
            
            self.ws = websocket.WebSocketApp(
                url,
                header=[f"Authorization: {self._create_auth_header()}"],
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            self.running = True
            self.thread = threading.Thread(
                target=self._run_websocket,
                daemon=True
            )
            self.thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            return False
    
    def _run_websocket(self):
        """Run WebSocket in thread."""
        try:
            self.ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE},
                ping_interval=30,
                ping_timeout=10
            )
        except Exception as e:
            logger.error(f"WebSocket run_forever error: {e}")
        finally:
            self.running = False
            self.connected = False
    
    def _subscribe_to_event(self, event_name: str):
        """Subscribe to a specific event."""
        if not self.ws or not self.connected:
            return
        
        try:
            # WAMP-style subscription: [5, event_name]
            subscribe_msg = json.dumps([5, event_name])
            self.ws.send(subscribe_msg)
            self.subscriptions.add(event_name)
            logger.info(f"Subscribed to {event_name}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {event_name}: {e}")
    
    def disconnect(self):
        """Disconnect WebSocket."""
        self.running = False
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=5)
        self.connected = False
        logger.info("WebSocket disconnected")
