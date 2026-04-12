"""WebSocket manager and logging handler for live log streaming."""

import asyncio
import json
import logging
from typing import Optional


class WebSocketManager:
    def __init__(self):
        self._connections: list = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._buffer: list[str] = []  # Log history for late joiners
        self._max_buffer = 500

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket):
        await websocket.accept()
        self._connections.append(websocket)
        # Send buffered history to new client
        for msg in self._buffer:
            try:
                await websocket.send_text(msg)
            except Exception:
                break

    def disconnect(self, websocket):
        self._connections = [c for c in self._connections if c is not websocket]

    async def broadcast(self, text: str):
        msg = json.dumps({"type": "log", "text": text})
        self._buffer.append(msg)
        if len(self._buffer) > self._max_buffer:
            self._buffer = self._buffer[-self._max_buffer:]
        dead = []
        for ws in list(self._connections):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_json(self, data: dict):
        msg = json.dumps(data)
        dead = []
        for ws in list(self._connections):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_from_thread(self, text: str):
        """Thread-safe: called from worker threads."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(text), self._loop)

    def broadcast_json_from_thread(self, data: dict):
        """Thread-safe: called from worker threads."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast_json(data), self._loop)

    def clear_buffer(self):
        self._buffer.clear()


class WebSocketLogHandler(logging.Handler):
    """Logging handler that forwards records to the WebSocket manager."""

    def __init__(self, manager: WebSocketManager):
        super().__init__()
        self.manager = manager

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.manager.broadcast_from_thread(msg)
        except Exception:
            self.handleError(record)


# Module-level singleton
manager = WebSocketManager()
