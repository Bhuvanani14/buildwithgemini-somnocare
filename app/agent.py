# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Any, Dict, List, Optional
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore
from google.genai import types

# Hardcoded GCP Project ID for reliable client initialization across local and Agent Platform
PROJECT_ID = "qwiklabs-gcp-03-fe29ebecbbcc"
MODEL = "gemini-3.8-flash"

_db: Optional[firestore.Client] = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT_ID)
    return _db


def search_cpap_supplies(category: str = "", query: str = "") -> List[Dict[str, Any]]:
    """Search the CPAP supplies catalog for masks, replacement cushions, filters, and heated tubing.

    Args:
        category: Optional category filter: 'mask', 'filter', or 'tubing'.
        query: Optional keyword search term to match against supply names and descriptions.

    Returns:
        A list of matching CPAP supplies with replacement intervals and details.
    """
    db = get_db()
    docs = db.collection("cpap_supplies").stream()
    results = []
    category_lower = category.lower().strip()
    query_lower = query.lower().strip()

    for doc in docs:
        data = doc.to_dict()
        if category_lower and data.get("category", "").lower() != category_lower:
            continue
        if query_lower:
            name = data.get("name", "").lower()
            desc = data.get("description", "").lower()
            best_for = data.get("best_for", "").lower()
            if query_lower not in name and query_lower not in desc and query_lower not in best_for:
                continue
        results.append(data)
    return results


def log_sleep_therapy_entry(
    date: str,
    usage_hours: float,
    ahi: float,
    mask_leak_rate: float,
    restedness_score: int,
    notes: str = "",
    user_id: str = "default_user",
) -> Dict[str, Any]:
    """Log a nightly CPAP sleep therapy entry into Firestore.

    Args:
        date: The date of the therapy session in YYYY-MM-DD format (e.g. '2026-10-13').
        usage_hours: Total CPAP run time in hours (e.g. 6.5).
        ahi: Apnea-Hypopnea Index events per hour (e.g. 2.1).
        mask_leak_rate: Mask leak rate in liters per minute (e.g. 5.4).
        restedness_score: Subjective restedness rating from 1 (exhausted) to 10 (fully refreshed).
        notes: Optional user notes or side effects (e.g. 'dry mouth, adjusted ramp').
        user_id: Identifier for the patient/user.

    Returns:
        A confirmation dict with the logged record ID and status.
    """
    db = get_db()
    doc_id = f"log-{user_id}-{date.replace('-', '')}"
    entry = {
        "id": doc_id,
        "user_id": user_id,
        "date": date,
        "usage_hours": float(usage_hours),
        "ahi": float(ahi),
        "mask_leak_rate": float(mask_leak_rate),
        "restedness_score": int(restedness_score),
        "notes": notes,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
    }
    db.collection("sleep_therapy_logs").document(doc_id).set(entry)
    return {
        "status": "success",
        "message": f"Successfully logged sleep therapy entry for {date}.",
        "entry_id": doc_id,
        "ahi": ahi,
        "usage_hours": usage_hours,
    }


def get_sleep_therapy_history(user_id: str = "default_user", limit: int = 7) -> List[Dict[str, Any]]:
    """Retrieve recent nightly CPAP sleep therapy logs for a patient from Firestore.

    Args:
        user_id: Patient/user identifier.
        limit: Maximum number of recent entries to return (default 7).

    Returns:
        List of historical sleep records sorted chronologically.
    """
    db = get_db()
    docs = (
        db.collection("sleep_therapy_logs")
        .where(filter=firestore.FieldFilter("user_id", "==", user_id))
        .stream()
    )
    records = [doc.to_dict() for doc in docs]
    records.sort(key=lambda r: r.get("date", ""), reverse=True)
    records = records[:limit]
    for log in records:
        if "timestamp" in log and isinstance(log["timestamp"], datetime.datetime):
            log["timestamp"] = log["timestamp"].isoformat()
    return records


def calculate_cms_adherence_compliance(user_id: str = "default_user", window_days: int = 30) -> Dict[str, Any]:
    """Calculate Medicare / CMS 30-day CPAP adherence compliance for insurance coverage.

    CMS criteria: CPAP usage must be at least 4.0 hours per night on at least 70% of days
    within a consecutive 30-day evaluation window.

    Args:
        user_id: Patient/user identifier.
        window_days: Days to evaluate (default 30).

    Returns:
        Compliance report with percentage, compliant days count, mean AHI, and adherence status.
    """
    db = get_db()
    docs = (
        db.collection("sleep_therapy_logs")
        .where(filter=firestore.FieldFilter("user_id", "==", user_id))
        .stream()
    )
    records = [doc.to_dict() for doc in docs]
    records.sort(key=lambda r: r.get("date", ""), reverse=True)
    records = records[:window_days]

    total_logged_days = len(records)
    if total_logged_days == 0:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "No sleep therapy logs found. Please log nightly sessions first.",
            "total_days_evaluated": 0,
            "compliance_percentage": 0.0,
            "is_compliant": False,
        }

    compliant_days = sum(1 for r in records if float(r.get("usage_hours", 0)) >= 4.0)
    compliance_percentage = round((compliant_days / total_logged_days) * 100, 1)
    avg_hours = round(sum(float(r.get("usage_hours", 0)) for r in records) / total_logged_days, 1)
    avg_ahi = round(sum(float(r.get("ahi", 0)) for r in records) / total_logged_days, 1)

    is_compliant = compliance_percentage >= 70.0
    status = "COMPLIANT" if is_compliant else "NON_COMPLIANT"

    return {
        "status": status,
        "is_compliant": is_compliant,
        "total_days_evaluated": total_logged_days,
        "compliant_days_count": compliant_days,
        "compliance_percentage": compliance_percentage,
        "average_usage_hours": avg_hours,
        "average_ahi": avg_ahi,
        "summary": (
            f"{compliant_days}/{total_logged_days} nights ({compliance_percentage}%) met the 4-hour threshold. "
            f"Average nightly usage: {avg_hours} hours. Average AHI: {avg_ahi}."
        ),
    }


def get_local_weather_and_humidity(city_or_location: str) -> Dict[str, Any]:
    """Fetch current ambient temperature and relative humidity for CPAP humidifier & rainout tuning.

    Calls the free Open-Meteo public API to fetch real-world ambient conditions.
    High or low humidity significantly impacts CPAP water chamber condensation ('rainout')
    and airway dryness.

    Args:
        city_or_location: Name of the city or locality (e.g., 'San Francisco', 'New York').

    Returns:
        Current ambient temperature (°C and °F), relative humidity (%), and CPAP climate tip.
    """
    import urllib.parse
    import urllib.request
    import json

    try:
        # Step 1: Geocode city name to coordinates
        encoded_query = urllib.parse.quote(city_or_location)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_query}&count=1"
        with urllib.request.urlopen(geo_url, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))

        if not geo_data.get("results"):
            return {
                "status": "error",
                "message": f"Could not find coordinates for location: {city_or_location}.",
            }

        result = geo_data["results"][0]
        lat, lon = result["latitude"], result["longitude"]
        resolved_name = f"{result.get('name')}, {result.get('country', '')}"

        # Step 2: Fetch current weather & relative humidity
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m&timezone=auto"
        )
        with urllib.request.urlopen(weather_url, timeout=5) as resp:
            weather_data = json.loads(resp.read().decode("utf-8"))

        current = weather_data.get("current", {})
        temp_c = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        temp_f = round((temp_c * 9 / 5) + 32, 1) if temp_c is not None else None

        # CPAP humidity guidance based on ambient levels
        if humidity is not None and humidity > 70:
            climate_tip = (
                f"Ambient humidity is high ({humidity}%). To prevent tube condensation ('rainout'), "
                "consider lowering your humidifier chamber level by 1 or enabling heated tubing."
            )
        elif humidity is not None and humidity < 35:
            climate_tip = (
                f"Ambient humidity is dry ({humidity}%). Increase your CPAP humidifier chamber level "
                "or use a heated tube to prevent dry nasal passages and morning throat irritation."
            )
        else:
            climate_tip = (
                f"Ambient humidity is moderate ({humidity}%). Standard auto-humidity settings should be comfortable."
            )

        return {
            "status": "success",
            "location": resolved_name,
            "temperature_celsius": temp_c,
            "temperature_fahrenheit": temp_f,
            "relative_humidity_percent": humidity,
            "cpap_climate_tip": climate_tip,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch weather data: {str(e)}",
        }


def generate_cpap_item_illustration(
    prompt: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Generate a clean illustration for a CPAP mask, accessory, or fit guide and save it.

    Uses the gemini-3.1-flash-lite-image model in the global region to generate an image.
    The generated image is:
    1. Saved as an ADK session artifact via tool_context.save_artifact (shown in Playground Artifacts panel).
    2. Uploaded directly to the public Cloud Storage bucket: somnocare-media-qwiklabs-gcp-03-fe29ebecbbcc.
    3. Returned with its public https URL.

    Args:
        prompt: Description of the CPAP equipment, mask, or fit diagram to illustrate.
        tool_context: Injected ADK ToolContext for saving session artifacts.

    Returns:
        Dict with public_url, artifact_filename, and status.
    """
    import uuid
    from google import genai
    from google.cloud import storage

    gcs_bucket_name = "somnocare-media-qwiklabs-gcp-03-fe29ebecbbcc"

    # Initialize genai client for Vertex AI in global region
    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

    # Generate image content
    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=f"Medical educational illustration of CPAP therapy equipment, clean studio product rendering, neutral background: {prompt}",
    )

    image_bytes = None
    mime_type = "image/jpeg"
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            image_bytes = part.inline_data.data
            mime_type = part.inline_data.mime_type or "image/jpeg"
            break

    if not image_bytes:
        return {
            "status": "error",
            "message": "Failed to extract generated image bytes from model response.",
        }

    # 1. Save artifact to ADK session context
    file_id = uuid.uuid4().hex[:8]
    ext = "jpg" if "jpeg" in mime_type or "jpg" in mime_type else "png"
    artifact_filename = f"cpap_{file_id}.{ext}"

    artifact_part = types.Part(
        inline_data=types.Blob(
            mime_type=mime_type,
            data=image_bytes,
        )
    )
    tool_context.save_artifact(
        filename=artifact_filename,
        artifact=artifact_part,
    )

    # 2. Upload to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(gcs_bucket_name)
    blob = bucket.blob(artifact_filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{gcs_bucket_name}/{artifact_filename}"

    return {
        "status": "success",
        "prompt": prompt,
        "artifact_filename": artifact_filename,
        "public_url": public_url,
        "message": f"Illustration generated, saved to session artifacts as {artifact_filename}, and uploaded to public Cloud Storage.",
    }


from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback

AGENT_ENGINE_RESOURCE_NAME = (
    "projects/132095283653/locations/us-east1/reasoningEngines/3470354465888927744"
)
SANDBOX_RESOURCE_NAME = (
    "projects/132095283653/locations/us-east1/reasoningEngines/3470354465888927744/sandboxEnvironments/4286485663303335936"
)


# WRITE: after each turn, send the session to Memory Bank for extraction
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description="""You are SomnoCare, an empathetic, clinically guided AI companion for sleep apnea patients and CPAP users.
You remember the user's stated clinical facts, equipment preferences, pressure tolerances, and lifestyle details across conversations and use them to personalize your care.

Your responsibilities:
1. Help patients track CPAP therapy adherence and log nightly metrics (usage hours, AHI, mask leak rates).
2. Calculate Medicare / CMS adherence compliance (4+ hours/night on 70% of nights) using the adherence calculation tool.
3. Check ambient weather and relative humidity via the weather tool to guide CPAP humidifier settings and prevent tube condensation ('rainout').
4. Answer questions about CPAP equipment, masks, replacement intervals, and maintenance using the CPAP supplies catalog tool.
5. Generate visual illustrations of CPAP equipment, mask fittings, or setup diagrams using the image generation tool when helpful.
6. When complex numerical calculations, statistical analysis of sleep trends, or custom sleep metric modeling are requested, safely write and run Python code in your secure Agent Engine Sandbox code executor.
7. Review therapy history using the sleep history lookup tool to provide encouraging, actionable sleep hygiene tips.
8. Adhere strictly to clinical safety guardrails:
   - Clarify you are an educational and therapy adherence assistant, not a diagnosing physician.
   - Do NOT modify or advise altering prescribed clinical pressure settings without physician consent.
   - For acute emergencies (severe chest pain, sudden breathlessness, nocturnal choking with respiratory distress), immediately direct the user to emergency services (911).
""",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        search_cpap_supplies,
        log_sleep_therapy_entry,
        get_sleep_therapy_history,
        calculate_cms_adherence_compliance,
        get_local_weather_and_humidity,
        generate_cpap_item_illustration,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
    code_executor=AgentEngineSandboxCodeExecutor(
        sandbox_resource_name=SANDBOX_RESOURCE_NAME,
        agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME,
    ),
)


app = App(
    root_agent=root_agent,
    name="app",
)






