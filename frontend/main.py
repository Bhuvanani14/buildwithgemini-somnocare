"""SomnoCare Unified FastAPI Application & A2A Proxy Server.

Supports:
1. Full REST & Multimodal Wellness API (`/api/*`) for the interactive SomnoCare Command Center UI.
2. Direct Gemini Agent tool-calling chat (`/chat` and `/api/agent-chat`) with automatic fallback
   to the deployed Vertex AI Agent Engine A2A endpoint when configured.
3. Static Single-Page Application hosting (`frontend/static/index.html`).
"""

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Ensure root repository path is importable when running `python frontend/main.py` or `uvicorn frontend.main:app`
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from app.api_routes import api_agent_chat, router as wellness_router  # noqa: E402

app = FastAPI(
    title="SomnoCare — Intelligent CPAP & OSA Wellness Platform",
    description="Clinical-guidance AI companion, OSA screening hub, acoustic snore analyzer, and MediaPipe Pose exercise coach.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wellness_router)


@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={
            "status": "error",
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}],
        },
    )


@app.post("/chat")
async def chat(req: Request):
    """Primary chat endpoint used by the web UI. Routes to the Gemini Agent with full SomnoCare tools,
    or optionally proxies to a remote Vertex AI A2A Reasoning Engine if USE_REMOTE_A2A=true."""
    if os.environ.get("USE_REMOTE_A2A", "").lower() not in ("1", "true", "yes"):
        return await api_agent_chat(req)

    # Optional remote A2A Reasoning Engine passthrough
    try:
        import google.auth
        import google.auth.transport.requests
        import httpx
        from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
        from a2a.types import Message, Part, Role, SendMessageRequest
        from google.protobuf.json_format import MessageToDict

        resource = os.environ.get(
            "AGENT_ENGINE_RESOURCE_NAME",
            "projects/132095283653/locations/us-east1/reasoningEngines/5291497565206872064",
        )
        agent_dir = os.environ.get("AGENT_DIRECTORY", "app")
        location = resource.split("/locations/")[1].split("/")[0]
        a2a_base = (
            f"https://{location}-aiplatform.googleapis.com/reasoningEngines/v1/"
            f"{resource}/api/a2a/{agent_dir}"
        )
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

        body = await req.json()
        message = body.get("message", "")
        parts: list[dict] = []

        async with httpx.AsyncClient(headers=headers, timeout=90) as client:
            resolver = A2ACardResolver(client, base_url=a2a_base)
            card = await resolver.get_agent_card()
            factory = ClientFactory(ClientConfig(httpx_client=client))
            a2a_client = factory.create(card)
            msg = Message(
                message_id=str(uuid.uuid4()),
                role=Role.ROLE_USER,
                parts=[Part(text=message)],
            )
            async for event in a2a_client.send_message(SendMessageRequest(message=msg)):
                event_dict = MessageToDict(event)
                if "artifactUpdate" in event_dict:
                    for p in event_dict["artifactUpdate"].get("artifact", {}).get("parts", []):
                        if "text" in p:
                            parts.append({"kind": "text", "text": p["text"]})
        if parts:
            return JSONResponse({"parts": parts})
    except Exception:
        pass

    return await api_agent_chat(req)


STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
