import json
import logging
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState
from twilio.base.exceptions import TwilioRestException

from app.services.config import get_settings
from app.services.realtime_bridge import OpenAIRealtimeBridge
from app.services.twilio_client import TwilioCallClient

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Twilio + OpenAI Realtime Caller")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="app/templates")

settings = get_settings()
twilio_client = TwilioCallClient(settings)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the landing page with the call configuration form."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_prompt": settings.default_prompt,
            "voices": settings.supported_voices,
            "public_base_url": settings.public_base_url,
        },
    )


@app.post("/call", response_class=HTMLResponse)
async def create_call(
    request: Request,
    to_number: str = Form(...),
    prompt: str = Form(...),
    voice: str = Form(...),
) -> HTMLResponse:
    """Trigger an outbound call through Twilio using the provided configuration."""
    prompt = prompt.strip()

    if not to_number:
        raise HTTPException(status_code=400, detail="A destination phone number is required.")

    if voice not in settings.supported_voices:
        raise HTTPException(status_code=400, detail="The selected voice is not supported.")

    try:
        call = twilio_client.start_call(
            to_number=to_number,
            prompt=prompt or settings.default_prompt,
            voice=voice,
        )
    except TwilioRestException as exc:  # pragma: no cover - network failure bubble up
        logger.exception("Unable to start call")
        raise HTTPException(status_code=502, detail=f"Twilio error: {exc.msg}") from exc

    return templates.TemplateResponse(
        "call_started.html",
        {
            "request": request,
            "call_sid": call.sid,
            "to_number": to_number,
            "voice": voice,
            "prompt": prompt or settings.default_prompt,
        },
    )


@app.api_route("/twiml", methods=["GET", "POST"], response_class=HTMLResponse)
async def twiml_endpoint(prompt: str, voice: str) -> HTMLResponse:
    """Generate the TwiML that connects the call audio stream to the realtime bridge."""
    twiml = twilio_client.generate_twiml(prompt=prompt, voice=voice)
    return HTMLResponse(content=twiml, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    """Handle media websocket connections coming from Twilio's <Stream> API."""
    requested_subprotocols = websocket.scope.get("subprotocols", [])
    target_subprotocol = "audio.twilio.com"
    negotiated_subprotocol: Optional[str] = None

    if target_subprotocol in requested_subprotocols:
        negotiated_subprotocol = target_subprotocol
    else:
        logger.warning("Unexpected websocket subprotocols: %s", requested_subprotocols)

    await websocket.accept(subprotocol=negotiated_subprotocol)
    logger.info(
        "Accepted Twilio websocket (requested=%s, negotiated=%s)",
        requested_subprotocols,
        negotiated_subprotocol or "none",
    )
    bridge: Optional[OpenAIRealtimeBridge] = None

    try:
        async for raw_message in websocket.iter_text():
            payload = json.loads(raw_message)
            event_type = payload.get("event")

            if event_type == "connected":
                logger.info("Twilio reports stream connection established")

            elif event_type == "start":
                stream_sid = payload.get("streamSid")
                params: Dict[str, Any] = payload.get("start", {}).get("customParameters", {})
                prompt = params.get("prompt", settings.default_prompt)
                voice = params.get("voice", settings.supported_voices[0])

                logger.info("Twilio stream %s starting with voice=%s", stream_sid, voice)
                bridge = OpenAIRealtimeBridge(
                    websocket=websocket,
                    stream_sid=stream_sid,
                    prompt=prompt,
                    voice=voice,
                    settings=settings,
                )

                try:
                    await bridge.connect()
                except Exception:  # pragma: no cover - network/runtime failure should log
                    logger.exception("Failed to connect realtime bridge to OpenAI")
                    break

                await websocket.send_json(
                    {
                        "event": "mark",
                        "streamSid": stream_sid,
                        "mark": {"name": "bridge-ready"},
                    }
                )

            elif event_type == "media" and bridge:
                media = payload.get("media", {})
                audio_chunk = media.get("payload")
                if audio_chunk:
                    await bridge.handle_audio_chunk(audio_chunk)

            elif event_type == "stop":
                logger.info("Twilio stream %s ended", payload.get("streamSid"))
                break

    except WebSocketDisconnect:
        logger.info("Twilio websocket disconnected")
    finally:
        if bridge:
            await bridge.close()
        if websocket.client_state not in (WebSocketState.DISCONNECTED, WebSocketState.CLOSING):
            await websocket.close()


@app.get("/health")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}
