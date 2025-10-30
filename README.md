# Twilio AI Calling Demo

A lightweight FastAPI application that lets you launch AI-assisted phone calls using Twilio's Programmable Voice and OpenAI's Realtime API. Configure calls from a friendly web UI, customize the assistant prompt and voice, and expose the service using ngrok so Twilio can deliver audio streams back to the app.

## Features

- 📞 Start outbound calls with your Twilio number and stream audio back to the app.
- 🧠 Bridge between Twilio media streams and OpenAI Realtime to produce AI voice responses.
- 🗣️ Choose from multiple OpenAI voices and provide custom prompts per call.
- 🌐 Single-page UI for launching calls, built with Jinja templates and a modern glassmorphism style.

## Prerequisites

- Python 3.10+
- A Twilio account with a verified phone number that can place outbound calls
- An OpenAI API key with access to the Realtime API
- ngrok (or a similar tunneling tool) to expose your local server

## Installation

1. Clone the repository and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the example environment file and fill in your credentials:

   ```bash
   cp .env.example .env
   ```

   | Variable | Description |
   | --- | --- |
   | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Twilio REST credentials |
   | `TWILIO_CALLER_ID` | The Twilio phone number (E.164 format) used for outbound calls |
   | `PUBLIC_BASE_URL` | **HTTPS** URL exposed by ngrok, e.g. `https://abcd1234.ngrok.app` |
   | `OPENAI_API_KEY` | Token with access to OpenAI Realtime |
   | `OPENAI_REALTIME_MODEL` | Realtime model name (defaults to `gpt-4o-realtime-preview-2024-12-17`) |

## Running the app

1. Start the FastAPI server (the default port is 8000):

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. In another terminal, expose the server using ngrok:

   ```bash
   ngrok http 8000
   ```

   Copy the HTTPS forwarding URL and update `PUBLIC_BASE_URL` in your `.env` file. Restart the server if the URL changes. Twilio requires TLS to establish the media websocket, so non-HTTPS URLs will cause calls to hang up immediately.

3. Visit `http://localhost:8000` to open the UI. Enter a destination number, adjust the prompt/voice, and click **Start call**. Twilio will dial the callee and stream media back to the `/media-stream` websocket, which forwards audio to OpenAI Realtime.

## Project structure

```
app/
├── main.py                 # FastAPI routes, templates, and websocket endpoint
├── static/styles.css       # Minimal styling for the UI
├── templates/              # Jinja templates for the UI
└── services/
    ├── config.py           # Pydantic settings management
    ├── realtime_bridge.py  # Websocket bridge between Twilio and OpenAI
    └── twilio_client.py    # Twilio helper for calls and TwiML generation
```

## Notes & limitations

- The realtime bridge provided here is designed for experimentation. Depending on your use case you may want to add persistence, authentication, better error handling, or advanced audio buffering logic.
- Twilio webhooks require a publicly accessible **HTTPS** URL so the <Stream> endpoint is reachable via `wss://`. ngrok is convenient for local development but consider deploying the app to a public host for production usage.
- Ensure that outbound calling complies with local regulations and that you have consent from recipients before placing calls.

## License

This project is provided as-is under the MIT License.
