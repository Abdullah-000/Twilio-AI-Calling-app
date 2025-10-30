from dataclasses import dataclass
from urllib.parse import urlencode

from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from app.services.config import Settings


@dataclass
class TwilioCallClient:
    settings: Settings

    def __post_init__(self) -> None:
        self._client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)

    def start_call(self, to_number: str, prompt: str, voice: str):
        """Create an outbound call and instruct Twilio to fetch the streaming TwiML."""
        query = urlencode({"prompt": prompt, "voice": voice})
        twiml_url = self.settings.build_public_url("/twiml", query=query)
        return self._client.calls.create(
            to=to_number,
            from_=self.settings.twilio_caller_id,
            url=twiml_url,
        )

    def generate_twiml(self, prompt: str, voice: str) -> str:
        """Build the TwiML response that connects the call to our realtime bridge."""
        response = VoiceResponse()
        connect = Connect()
        stream = Stream(
            url=self.settings.build_public_url("/media-stream", scheme="wss"),
            track="both_tracks",
        )
        stream.parameter(name="prompt", value=prompt)
        stream.parameter(name="voice", value=voice)
        connect.append(stream)
        response.append(connect)
        return str(response)
