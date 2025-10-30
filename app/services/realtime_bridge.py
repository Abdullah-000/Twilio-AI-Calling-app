import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import websockets
from fastapi import WebSocket

from app.services.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class OpenAIRealtimeBridge:
    websocket: WebSocket
    stream_sid: str
    prompt: str
    voice: str
    settings: Settings

    _openai_ws: Optional[websockets.WebSocketClientProtocol] = field(init=False, default=None)
    _buffer: List[str] = field(init=False, default_factory=list)
    _waiting_for_response: bool = field(init=False, default=False)
    _bridge_task: Optional[asyncio.Task] = field(init=False, default=None)

    async def connect(self) -> None:
        """Connect to the OpenAI Realtime websocket and configure the session."""
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        realtime_url = (
            f"wss://api.openai.com/v1/realtime?model={self.settings.openai_realtime_model}&voice={self.voice}"
        )
        self._openai_ws = await websockets.connect(realtime_url, extra_headers=headers)

        session_update = {
            "type": "session.update",
            "session": {
                "instructions": self.prompt,
                "modalities": ["audio", "text"],
                "voice": self.voice,
            },
        }
        await self._openai_ws.send(json.dumps(session_update))
        self._bridge_task = asyncio.create_task(self._forward_openai_events())
        logger.info("Connected OpenAI session for stream %s", self.stream_sid)

        await self._openai_ws.send(
            json.dumps(
                {
                    "type": "response.create",
                    "response": {"modalities": ["audio"], "instructions": self.prompt},
                }
            )
        )
        self._waiting_for_response = True

    async def handle_audio_chunk(self, base64_payload: str) -> None:
        """Buffer audio from Twilio and periodically forward it to OpenAI."""
        if not self._openai_ws:
            return

        self._buffer.append(base64_payload)

        if len(self._buffer) >= 20 and not self._waiting_for_response:
            await self._flush_audio_buffer()

    async def _flush_audio_buffer(self) -> None:
        if not self._buffer or not self._openai_ws:
            return

        for chunk in self._buffer:
            await self._openai_ws.send(
                json.dumps({"type": "input_audio_buffer.append", "audio": chunk})
            )

        await self._openai_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await self._openai_ws.send(
            json.dumps(
                {
                    "type": "response.create",
                    "response": {"modalities": ["audio"]},
                }
            )
        )
        self._waiting_for_response = True
        self._buffer.clear()

    async def _forward_openai_events(self) -> None:
        assert self._openai_ws is not None
        async for message in self._openai_ws:
            payload = json.loads(message)
            event_type = payload.get("type")

            if event_type == "response.audio.delta":
                await self._send_audio_to_twilio(payload.get("delta"))

            elif event_type == "response.completed":
                self._waiting_for_response = False
                if len(self._buffer) >= 20:
                    await self._flush_audio_buffer()

            elif event_type == "error":
                logger.error("OpenAI realtime error: %s", payload)

    async def _send_audio_to_twilio(self, base64_audio: Optional[str]) -> None:
        if not base64_audio:
            return

        message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": base64_audio},
        }
        await self.websocket.send_json(message)

    async def close(self) -> None:
        if self._buffer and self._openai_ws and not self._waiting_for_response:
            await self._flush_audio_buffer()

        if self._bridge_task:
            self._bridge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._bridge_task

        if self._openai_ws:
            await self._openai_ws.close()
            self._openai_ws = None
