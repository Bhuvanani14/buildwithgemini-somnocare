"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.
"""

import json
import os
import uuid

import google.auth
import google.auth.transport.requests
from google.protobuf.json_format import MessageToDict
import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import AgentCard, Message, Part, Role, SendMessageRequest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ.get(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/132095283653/locations/us-east1/reasoningEngines/5291497565206872064",
)
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP passthrough.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request.
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation across turns.
_contexts: dict[str, str] = {}
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resolver = A2ACardResolver(client, base_url=A2A_BASE)
        card = await resolver.get_agent_card()
        _card = card
    return _card


def _extract_dict_parts(parts: list[dict]) -> list[dict]:
    out: list[dict] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        # Plain text
        if "text" in p and p["text"]:
            out.append({"kind": "text", "text": p["text"]})
        # Data / A2UI
        elif "data" in p and p["data"]:
            meta = p.get("metadata") or {}
            mime = meta.get("mimeType") or p.get("mediaType")
            data_payload = p["data"]
            # Unwrap data if nested
            if isinstance(data_payload, dict) and "data" in data_payload:
                nested = data_payload["data"]
                if isinstance(nested, dict) and (
                    "beginRendering" in nested or "surfaceUpdate" in nested
                ):
                    out.append({"kind": "a2ui", "data": nested})
                    continue
            if isinstance(data_payload, dict) and (
                "beginRendering" in data_payload or "surfaceUpdate" in data_payload
            ):
                out.append({"kind": "a2ui", "data": data_payload})
            elif mime == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": data_payload})
        elif "url" in p and p["url"]:
            out.append({"kind": "text", "text": p["url"]})
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        factory = ClientFactory(ClientConfig(httpx_client=client))
        a2a_client = factory.create(card)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.ROLE_USER,
            parts=[Part(text=message)],
        )
        if _contexts.get(user_id):
            msg.context_id = _contexts[user_id]

        send_req = SendMessageRequest(message=msg)

        async for event in a2a_client.send_message(send_req):
            event_dict = MessageToDict(event)
            # Track context ID
            ctx_id = event_dict.get("contextId")
            if not ctx_id:
                for k in ("task", "statusUpdate", "artifactUpdate"):
                    if k in event_dict and "contextId" in event_dict[k]:
                        ctx_id = event_dict[k]["contextId"]
                        break
            if ctx_id:
                _contexts[user_id] = ctx_id

            # Extract artifact updates
            if "artifactUpdate" in event_dict:
                art = event_dict["artifactUpdate"].get("artifact", {})
                parts.extend(_extract_dict_parts(art.get("parts", [])))
            elif "task" in event_dict:
                for art in event_dict["task"].get("artifacts", []):
                    parts.extend(_extract_dict_parts(art.get("parts", [])))

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
