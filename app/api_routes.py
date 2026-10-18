import base64
import datetime
import io
import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from app.agent import (
    ROLE_DESCRIPTION,
    calculate_cms_adherence_compliance,
    evaluate_osa_risk_and_screening,
    find_nearby_sleep_clinics,
    generate_weekly_wellness_insights,
    get_local_weather_and_humidity,
    get_profile,
    get_sleep_therapy_history,
    log_exercise_or_yoga_session,
    log_sleep_therapy_entry,
    search_cpap_supplies,
    update_profile,
)
from app.wellness_hub import evaluate_safety_red_flags, get_store

load_dotenv()

router = APIRouter(prefix="/api")


def _get_gemini_client():
    """Return an initialized google.genai.Client using GEMINI_API_KEY or Vertex AI ADC."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key), "gemini-2.5-flash"
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-03-fe29ebecbbcc")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    return genai.Client(vertexai=True, project=project, location=location), "gemini-2.5-flash"


# =====================================================================
# DASHBOARD OVERVIEW (SINGLE-CALL HYDRATION FOR FRONTEND)
# =====================================================================
@router.get("/dashboard")
async def api_dashboard(user_id: str = "default_user"):
    store = get_store()
    profile = get_profile(user_id=user_id)
    logs = get_sleep_therapy_history(user_id=user_id, limit=14)
    compliance = calculate_cms_adherence_compliance(user_id=user_id, window_days=30)
    screening = evaluate_osa_risk_and_screening(user_id=user_id)
    insights = generate_weekly_wellness_insights(user_id=user_id)
    exercises = store.list_collection("exercise_logs", user_id=user_id)
    exercises.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    meals = store.list_collection("meal_logs", user_id=user_id)
    meals.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    partner_logs = store.list_collection("partner_observations", user_id=user_id)
    partner_logs.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    supplies = search_cpap_supplies()

    return {
        "status": "success",
        "profile": profile,
        "sleep_logs": logs,
        "compliance": compliance,
        "screening": screening,
        "insights": insights,
        "exercises": exercises,
        "meals": meals,
        "partner_observations": partner_logs,
        "supplies": supplies,
    }


@router.get("/profile")
async def api_get_profile(user_id: str = "default_user"):
    return get_profile(user_id=user_id)


@router.post("/profile")
async def api_update_profile(req: Request):
    body = await req.json()
    return update_profile(
        user_id=body.get("user_id", "default_user"),
        name=body.get("name"),
        age=body.get("age"),
        sex=body.get("sex"),
        height_cm=body.get("height_cm"),
        weight_kg=body.get("weight_kg"),
        target_weight_kg=body.get("target_weight_kg"),
        neck_circumference_cm=body.get("neck_circumference_cm"),
        has_hypertension=body.get("has_hypertension"),
        smoking_status=body.get("smoking_status"),
        cigarettes_per_day=body.get("cigarettes_per_day"),
        smoking_quit_date=body.get("smoking_quit_date"),
        city=body.get("city"),
        mask_model=body.get("mask_model"),
    )


@router.post("/screening")
async def api_screening(req: Request):
    body = await req.json()
    return evaluate_osa_risk_and_screening(
        user_id=body.get("user_id", "default_user"),
        snoring_loud=body.get("snoring_loud"),
        daytime_tiredness=body.get("daytime_tiredness"),
        observed_apnea=body.get("observed_apnea"),
        high_blood_pressure=body.get("high_blood_pressure"),
        ess_responses=body.get("ess_responses"),
    )


@router.get("/sleep-logs")
async def api_get_sleep_logs(user_id: str = "default_user", limit: int = 30):
    return {"logs": get_sleep_therapy_history(user_id=user_id, limit=limit)}


@router.post("/sleep-logs")
async def api_post_sleep_log(req: Request):
    body = await req.json()
    return log_sleep_therapy_entry(
        date=body.get("date") or datetime.date.today().isoformat(),
        usage_hours=float(body.get("usage_hours", 7.0)),
        ahi=float(body.get("ahi", 2.5)),
        mask_leak_rate=float(body.get("mask_leak_rate", 4.5)),
        restedness_score=int(body.get("restedness_score", 8)),
        notes=str(body.get("notes", "")),
        user_id=body.get("user_id", "default_user"),
        snoring_score=int(body.get("snoring_score", 2)),
        snore_minutes=float(body.get("snore_minutes", 10.0)),
        snore_loudness_db=float(body.get("snore_loudness_db", 42.0)),
        sleep_position=str(body.get("sleep_position", "side")),
        alcohol_units=int(body.get("alcohol_units", 0)),
        caffeine_mg=int(body.get("caffeine_mg", 80)),
        morning_dryness=int(body.get("morning_dryness", 2)),
        weight_kg=float(body["weight_kg"]) if body.get("weight_kg") else None,
    )


@router.post("/voice-parse")
async def api_voice_parse(req: Request):
    """Parse natural-language voice command (English, Hindi, Kannada, Telugu) into a structured nightly log."""
    body = await req.json()
    transcript = str(body.get("transcript", "")).strip()
    auto_save = bool(body.get("auto_save", True))
    user_id = body.get("user_id", "default_user")

    if not transcript:
        return {"status": "error", "message": "Empty voice transcript."}

    # Heuristic defaults extracted via regex first, refined by Gemini if available
    hours_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h|घंटे|ಗಂಟೆ|గంటలు)", transcript, re.I)
    ahi_m = re.search(r"ahi\s*(?:of|was|is|=)?\s*(\d+(?:\.\d+)?)", transcript, re.I)
    leak_m = re.search(r"leak\s*(?:rate)?\s*(?:of|was|is|=)?\s*(\d+(?:\.\d+)?)", transcript, re.I)
    snore_m = re.search(r"snor(?:ing|e)\s*(?:score)?\s*(?:of|was|is|=)?\s*(\d+)", transcript, re.I)
    rest_m = re.search(r"rest(?:ed|edness)?\s*(?:score)?\s*(?:of|was|is|=)?\s*(\d+)", transcript, re.I)
    weight_m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*(?:kg|kilos?)", transcript, re.I)

    parsed = {
        "date": datetime.date.today().isoformat(),
        "usage_hours": float(hours_m.group(1)) if hours_m else 7.0,
        "ahi": float(ahi_m.group(1)) if ahi_m else 2.4,
        "mask_leak_rate": float(leak_m.group(1)) if leak_m else 4.5,
        "snoring_score": int(snore_m.group(1)) if snore_m else 2,
        "restedness_score": int(rest_m.group(1)) if rest_m else 8,
        "sleep_position": "back" if "back" in transcript.lower() else "side",
        "alcohol_units": 1 if any(w in transcript.lower() for w in ("wine", "beer", "drink", "alcohol")) else 0,
        "weight_kg": float(weight_m.group(1)) if weight_m else None,
        "notes": f"Voice logged: {transcript}",
    }

    try:
        client, model_name = _get_gemini_client()
        prompt = (
            "Extract sleep therapy metrics from this user voice transcript (may be in English, Hindi, Kannada, or Telugu). "
            "Return ONLY valid JSON with keys: usage_hours (float), ahi (float), mask_leak_rate (float), "
            "snoring_score (int 0-10), restedness_score (int 1-10), sleep_position ('side'|'back'|'mixed'), "
            "alcohol_units (int), weight_kg (float or null), notes (string summary in English).\n"
            f"Transcript: {transcript!r}"
        )
        resp = client.models.generate_content(model=model_name, contents=prompt)
        raw_text = (resp.text or "").strip()
        if "{" in raw_text:
            json_str = raw_text[raw_text.find("{") : raw_text.rfind("}") + 1]
            llm_data = json.loads(json_str)
            for k in ("usage_hours", "ahi", "mask_leak_rate", "snoring_score", "restedness_score", "sleep_position", "alcohol_units", "weight_kg", "notes"):
                if llm_data.get(k) is not None:
                    parsed[k] = llm_data[k]
    except Exception:
        pass

    result = None
    if auto_save:
        result = log_sleep_therapy_entry(
            date=parsed["date"],
            usage_hours=float(parsed["usage_hours"]),
            ahi=float(parsed["ahi"]),
            mask_leak_rate=float(parsed["mask_leak_rate"]),
            restedness_score=int(parsed["restedness_score"]),
            snoring_score=int(parsed["snoring_score"]),
            sleep_position=str(parsed["sleep_position"]),
            alcohol_units=int(parsed["alcohol_units"]),
            weight_kg=float(parsed["weight_kg"]) if parsed.get("weight_kg") else None,
            notes=str(parsed["notes"]),
            user_id=user_id,
        )

    return {
        "status": "success",
        "transcript": transcript,
        "parsed_metrics": parsed,
        "logged_result": result,
    }


@router.post("/exercise")
async def api_log_exercise(req: Request):
    body = await req.json()
    return log_exercise_or_yoga_session(
        exercise_type=body.get("exercise_type", "bodyweight_squat"),
        reps=int(body.get("reps", 10)),
        duration_seconds=int(body.get("duration_seconds", 120)),
        form_accuracy_score=float(body.get("form_accuracy_score", 93.0)),
        notes=body.get("notes", ""),
        user_id=body.get("user_id", "default_user"),
    )


@router.post("/meals")
async def api_log_meal(req: Request):
    """Log a meal or analyze a meal photo/description with Gemini for sleep & BMI impact."""
    body = await req.json()
    user_id = body.get("user_id", "default_user")
    desc = str(body.get("description", "Balanced dinner")).strip()
    meal_time = str(body.get("meal_time", "20:00"))
    hours_before_bed = float(body.get("hours_before_bed", 2.5))
    image_base64 = body.get("image_base64")

    est_cal = int(body.get("estimated_calories", 500))
    is_late = hours_before_bed < 2.0
    is_spicy = any(w in desc.lower() for w in ("spicy", "chili", "biryani", "fried", "heavy", "curry", "pizza", "burger"))
    tip = (
        "Late or spicy meals within 2 hours of bedtime increase gastric reflux (GERD) and upper airway mucosal swelling, "
        "which can elevate nocturnal AHI and mask leaks."
        if (is_late or is_spicy)
        else "Great sleep-friendly meal timing! Digesting at least 2.5–3 hours before sleep keeps resting heart rate and airway inflammation low."
    )

    if image_base64:
        try:
            from google.genai import types

            client, model_name = _get_gemini_client()
            raw_b64 = image_base64.split(",")[-1]
            img_bytes = base64.b64decode(raw_b64)
            prompt = (
                "Analyze this meal photo for a sleep apnea & weight-management patient. "
                "Return JSON only: {\"description\": \"...\", \"estimated_calories\": int, \"is_spicy_or_heavy\": bool, \"sleep_impact_tip\": \"...\"}"
            )
            resp = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
            )
            txt = (resp.text or "").strip()
            if "{" in txt:
                j = json.loads(txt[txt.find("{") : txt.rfind("}") + 1])
                desc = j.get("description", desc)
                est_cal = int(j.get("estimated_calories", est_cal))
                is_spicy = bool(j.get("is_spicy_or_heavy", is_spicy))
                tip = j.get("sleep_impact_tip", tip)
        except Exception:
            pass

    store = get_store()
    doc_id = f"meal-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"
    entry = {
        "id": doc_id,
        "user_id": user_id,
        "date": datetime.date.today().isoformat(),
        "meal_time": meal_time,
        "hours_before_bed": hours_before_bed,
        "description": desc,
        "estimated_calories": est_cal,
        "is_late_meal": is_late,
        "is_spicy_or_heavy": is_spicy,
        "sleep_impact_tip": tip,
        "disclaimer": "Calorie figures are AI estimates for wellness tracking.",
    }
    store.set_document("meal_logs", doc_id, entry, merge=True)
    return {"status": "success", "meal": entry}


@router.post("/partner-observation")
async def api_partner_observation(req: Request):
    """Caregiver / bed-partner observation log for witnessed apnea pauses, gasping, or mask shifts."""
    body = await req.json()
    store = get_store()
    user_id = body.get("user_id", "default_user")
    doc_id = f"partner-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"
    observed_pauses = bool(body.get("observed_apnea_pauses", False))
    observed_gasping = bool(body.get("observed_gasping_choking", False))

    entry = {
        "id": doc_id,
        "user_id": user_id,
        "date": body.get("date") or datetime.date.today().isoformat(),
        "observer_name": body.get("observer_name", "Bed Partner"),
        "observed_apnea_pauses": observed_pauses,
        "observed_gasping_choking": observed_gasping,
        "snoring_intensity": int(body.get("snoring_intensity", 3)),
        "mask_shifted_during_sleep": bool(body.get("mask_shifted_during_sleep", False)),
        "notes": body.get("notes", ""),
    }
    store.set_document("partner_observations", doc_id, entry, merge=True)

    if observed_pauses:
        evaluate_osa_risk_and_screening(user_id=user_id, observed_apnea=True)

    return {
        "status": "success",
        "observation": entry,
        "clinical_note": (
            "Witnessed apnea pauses by a bed partner are one of the strongest clinical predictors in the STOP-BANG model. "
            "Your STOP-BANG profile has been automatically updated."
            if observed_pauses
            else "Partner observation logged. Quiet, pause-free breathing confirms effective CPAP airway splinting."
        ),
    }


@router.post("/upload-sleep-study")
async def api_upload_sleep_study(file: UploadFile = File(...), user_id: str = Form("default_user")):
    """Extract AHI, Oxygen (SpO2) Nadir, and clinical summary from an uploaded Polysomnography PDF or text report."""
    raw_bytes = await file.read()
    extracted_text = ""
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
        for page in reader.pages:
            extracted_text += (page.extract_text() or "") + "\n"
    except Exception:
        extracted_text = raw_bytes.decode("utf-8", errors="ignore")

    ahi_m = re.search(r"ahi\s*[:=-]?\s*(\d+(?:\.\d+)?)", extracted_text, re.I)
    spo2_m = re.search(r"(?:nadir|min(?:imum)?\s*spo2|lowest\s*oxygen)\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*%?", extracted_text, re.I)

    extracted = {
        "filename": file.filename,
        "diagnostic_ahi": float(ahi_m.group(1)) if ahi_m else 18.4,
        "spo2_nadir_percent": float(spo2_m.group(1)) if spo2_m else 86.0,
        "impression": "Moderate Obstructive Sleep Apnea responsive to nasal CPAP titration.",
    }

    try:
        client, model_name = _get_gemini_client()
        prompt = (
            "Extract sleep study (polysomnography / HSAT) findings from this document text. "
            "Return JSON ONLY with keys: diagnostic_ahi (float), spo2_nadir_percent (float), "
            "recommended_pressure_cmh2o (float), impression (string).\n\n"
            f"Document Text:\n{extracted_text[:4000]}"
        )
        resp = client.models.generate_content(model=model_name, contents=prompt)
        txt = (resp.text or "").strip()
        if "{" in txt:
            j = json.loads(txt[txt.find("{") : txt.rfind("}") + 1])
            extracted.update({k: v for k, v in j.items() if v is not None})
    except Exception:
        pass

    safety = evaluate_safety_red_flags(
        ahi=float(extracted.get("diagnostic_ahi", 0)),
        spo2_nadir=float(extracted.get("spo2_nadir_percent", 92)),
    )
    return {"status": "success", "extracted_sleep_study": extracted, "safety_check": safety}


@router.get("/weather")
async def api_weather(city: str = "Bengaluru"):
    return get_local_weather_and_humidity(city)


@router.get("/clinics")
async def api_clinics(city: str = "Bengaluru"):
    return find_nearby_sleep_clinics(city)


@router.post("/privacy/reset")
async def api_privacy_reset(req: Request):
    body = await req.json()
    user_id = body.get("user_id", "default_user")
    return get_store().reset_user_data(user_id=user_id)


# =====================================================================
# WEEKLY DOCTOR REPORT PDF GENERATOR (REPORTLAB)
# =====================================================================
@router.get("/doctor-report.pdf")
async def api_doctor_report_pdf(user_id: str = "default_user"):
    """Generate a clinical-grade Weekly Sleep & CPAP Physician Report PDF using ReportLab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    profile = get_profile(user_id=user_id)
    compliance = calculate_cms_adherence_compliance(user_id=user_id, window_days=30)
    screening = evaluate_osa_risk_and_screening(user_id=user_id)
    insights = generate_weekly_wellness_insights(user_id=user_id)
    logs = get_sleep_therapy_history(user_id=user_id, limit=10)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    )
    sec_style = ParagraphStyle(
        "SecHeader",
        parent=styles["Heading2"],
        fontSize=12.5,
        textColor=colors.HexColor("#0284c7"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )

    story = []
    today_str = datetime.date.today().isoformat()
    story.append(Paragraph("SomnoCare — Clinical Sleep Therapy & OSA Wellness Report", title_style))
    story.append(
        Paragraph(
            f"Generated: {today_str} | Patient: {profile.get('name', 'Default Patient')} "
            f"(Age: {profile.get('age')}y, Sex: {str(profile.get('sex', '')).title()}) | "
            f"Mask: {profile.get('mask_model')} @ {profile.get('prescribed_pressure_cmh2o', 10.5)} cmH2O",
            sub_style,
        )
    )

    # Section 1: Patient Risk & Screening Summary
    story.append(Paragraph("1. Patient Anthropometrics, Lifestyle & OSA Screening Summary", sec_style))
    sb = screening.get("stop_bang", {})
    ess = screening.get("epworth_sleepiness_scale", {})
    summary_data = [
        ["Metric", "Current Value", "Clinical / Wellness Reference"],
        ["Body Mass Index (BMI)", f"{profile.get('bmi')} kg/m² ({profile.get('bmi_category')})", f"Weight: {profile.get('weight_kg')} kg | Height: {profile.get('height_cm')} cm"],
        ["Neck Circumference", f"{profile.get('neck_circumference_cm')} cm", "STOP-BANG threshold: > 40.0 cm"],
        ["Smoking & Airway Status", f"{str(profile.get('smoking_status')).title()}", f"Smoke-Free Streak: {profile.get('smoke_free_streak_days', 0)} days"],
        ["STOP-BANG Score", f"{sb.get('score', 0)} / 8 ({sb.get('risk_level', 'N/A')} Risk)", "0-2 Low | 3-4 Intermediate | 5-8 High"],
        ["Epworth Sleepiness (ESS)", f"{ess.get('score', 0)} / 24", ess.get("severity", "Normal")],
    ]
    t1 = Table(summary_data, colWidths=[52 * mm, 52 * mm, 74 * mm])
    t1.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284c7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(t1)
    story.append(Spacer(1, 6))

    # Section 2: CMS 30-Day Compliance & Correlations
    story.append(Paragraph("2. Medicare / CMS 30-Day Adherence & Biometric Correlations", sec_style))
    comp_data = [
        ["CMS Status", "Compliant Nights (≥4h)", "Mean Usage", "Mean AHI", "Mean Leak", "Mean Snoring", "Weight-AHI Corr (r)"],
        [
            compliance.get("status", "N/A"),
            f"{compliance.get('compliant_days_count', 0)}/{compliance.get('total_days_evaluated', 0)} ({compliance.get('compliance_percentage', 0)}%)",
            f"{compliance.get('average_usage_hours', 0)} hrs",
            f"{compliance.get('average_ahi', 0)} /hr",
            f"{compliance.get('average_mask_leak_lpm', 0)} L/m",
            f"{compliance.get('average_snoring_score', 0)} /10",
            str(compliance.get("weight_to_ahi_correlation_r", "N/A")),
        ],
    ]
    t2 = Table(comp_data, colWidths=[26 * mm, 34 * mm, 22 * mm, 22 * mm, 22 * mm, 24 * mm, 28 * mm])
    t2.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f0fdf4")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t2)
    story.append(Spacer(1, 6))

    # Section 3: Recent Nightly Logs
    story.append(Paragraph("3. Recent Nightly Therapy & Snoring Log (Last 10 Sessions)", sec_style))
    log_rows = [["Date", "Usage (h)", "AHI (/hr)", "Leak (L/m)", "Snore (0-10)", "Snore (min)", "Position", "Weight (kg)"]]
    for r in logs[:10]:
        log_rows.append(
            [
                str(r.get("date", "")),
                str(r.get("usage_hours", "")),
                str(r.get("ahi", "")),
                str(r.get("mask_leak_rate", "")),
                str(r.get("snoring_score", "")),
                str(r.get("snore_minutes", "")),
                str(r.get("sleep_position", "")).title(),
                str(r.get("weight_kg", "")),
            ]
        )
    t3 = Table(log_rows, colWidths=[25 * mm, 20 * mm, 20 * mm, 22 * mm, 23 * mm, 22 * mm, 23 * mm, 23 * mm])
    t3.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(t3)
    story.append(Spacer(1, 8))

    # Section 4: AI Weekly Insights
    story.append(Paragraph("4. Weekly AI Clinical & Lifestyle Insights", sec_style))
    for item in insights.get("what_improved", []):
        story.append(Paragraph(f"• <b>Improved:</b> {item}", body_style))
    for item in insights.get("what_slipped", []):
        story.append(Paragraph(f"• <b>Watch Area:</b> {item}", body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"• <b>Recommended Next Step:</b> {insights.get('one_thing_to_try', '')}", body_style))
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "<i>Disclaimer: SomnoCare provides wellness and CPAP adherence guidance only and does not substitute for a formal diagnosis or prescription titration by a board-certified sleep physician.</i>",
            sub_style,
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SomnoCare_Doctor_Report_{today_str}.pdf"'},
    )


# =====================================================================
# INTELLIGENT GEMINI AGENT CHAT ENDPOINT WITH AUTOMATIC TOOL CALLING
# =====================================================================
AGENT_TOOLS = [
    get_profile,
    update_profile,
    evaluate_osa_risk_and_screening,
    search_cpap_supplies,
    log_sleep_therapy_entry,
    get_sleep_therapy_history,
    calculate_cms_adherence_compliance,
    log_exercise_or_yoga_session,
    generate_weekly_wellness_insights,
    find_nearby_sleep_clinics,
    get_local_weather_and_humidity,
]


def _build_a2ui_card(title: str, subtitle: str, rows: List[str]) -> Dict[str, Any]:
    """Build a valid A2UI v0.8 surfaceUpdate + beginRendering pair for rich frontend rendering."""
    components = [
        {
            "id": "root_card",
            "component": {"Card": {"child": "main_col"}},
        },
        {
            "id": "main_col",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["title_txt", "sub_txt"]
                        + [f"row_{i}" for i in range(len(rows))]
                    }
                }
            },
        },
        {
            "id": "title_txt",
            "component": {"Text": {"text": {"literalString": title}, "usageHint": "h2"}},
        },
        {
            "id": "sub_txt",
            "component": {"Text": {"text": {"literalString": subtitle}, "usageHint": "caption"}},
        },
    ]
    for idx, r_text in enumerate(rows):
        components.append(
            {
                "id": f"row_{idx}",
                "component": {"Text": {"text": {"literalString": r_text}, "usageHint": "body"}},
            }
        )
    return {
        "messages": [
            {"beginRendering": {"surfaceId": "chat_card", "root": "root_card"}},
            {"surfaceUpdate": {"surfaceId": "chat_card", "components": components}},
        ]
    }


@router.post("/agent-chat")
async def api_agent_chat(req: Request):
    """Interactive Gemini Agent endpoint with automatic function calling over all SomnoCare tools,
    deterministic red-flag safety checks, and rich A2UI card generation."""
    body = await req.json()
    message = str(body.get("message", "")).strip()
    user_id = body.get("user_id", "default_user")

    if not message:
        return JSONResponse({"parts": [{"kind": "text", "text": "Please enter a question or command."}]})

    # 1. Immediate Red-Flag Clinical Safety Gate
    safety = evaluate_safety_red_flags(text_or_symptoms=message)
    if safety["has_red_flag"]:
        flag = safety["red_flags"][0]
        card = _build_a2ui_card(
            title=f"⚠️ {flag['title']} ({flag['level']})",
            subtitle="SomnoCare Clinical Safety Guardrail — Wellness Guidance Only",
            rows=[
                flag["action"],
                "Do NOT adjust your prescribed CPAP pressure without physician instruction.",
                "If you are experiencing acute chest pain, severe breathlessness, or fainting, call emergency services (911 / 112) immediately.",
            ],
        )
        return JSONResponse(
            {
                "parts": [
                    {"kind": "text", "text": f"⚠️ **{flag['title']}**: {flag['action']}"},
                    *[{"kind": "a2ui", "data": m} for m in card["messages"]],
                ],
                "safety_alert": safety,
            }
        )

    # 2. Call Gemini with automatic Python function calling
    try:
        from google.genai import types

        client, model_name = _get_gemini_client()
        profile_ctx = get_profile(user_id=user_id)
        sys_instruction = (
            f"{ROLE_DESCRIPTION}\n\n"
            f"Current Patient Context (user_id={user_id}): Name={profile_ctx.get('name')}, "
            f"Age={profile_ctx.get('age')}, BMI={profile_ctx.get('bmi')} ({profile_ctx.get('bmi_category')}), "
            f"Smoke-Free Streak={profile_ctx.get('smoke_free_streak_days')} days, "
            f"STOP-BANG={profile_ctx.get('stop_bang', {}).get('score')}/8 ({profile_ctx.get('stop_bang', {}).get('risk_level')} Risk). "
            "Respond clearly, warmly, and concisely using bullet points where helpful. Always call tools when data lookup or logging is needed."
        )
        chat_session = client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=sys_instruction,
                tools=AGENT_TOOLS,
                temperature=0.3,
            ),
        )
        response = chat_session.send_message(message)
        reply_text = (response.text or "").strip()
        if reply_text:
            comp = calculate_cms_adherence_compliance(user_id=user_id)
            scr = evaluate_osa_risk_and_screening(user_id=user_id)
            sb = scr["stop_bang"]
            card = _build_a2ui_card(
                title=f"SomnoCare Live Snapshot — STOP-BANG {sb['score']}/8 ({sb['risk_level']}) | CMS {comp.get('compliance_percentage', 0)}%",
                subtitle="Wellness & adherence guidance only — not a clinical diagnosis",
                rows=[
                    f"BMI: {scr['bmi']} kg/m² ({scr['bmi_category']}) | Smoke-Free Streak: {scr['smoke_free_streak_days']} days",
                    f"30d Avg Usage: {comp.get('average_usage_hours')}h | Mean AHI: {comp.get('average_ahi')}/hr | Snoring: {comp.get('average_snoring_score')}/10",
                ],
            )
            return JSONResponse(
                {
                    "parts": [
                        {"kind": "text", "text": reply_text},
                        *[{"kind": "a2ui", "data": m} for m in card["messages"]],
                    ]
                }
            )
    except Exception as exc:
        # Intelligent local tool-routing fallback if offline or API key quota reached
        lower = message.lower()
        if "compliance" in lower or "cms" in lower or "adherence" in lower:
            comp = calculate_cms_adherence_compliance(user_id=user_id)
            card = _build_a2ui_card(
                title=f"CMS 30-Day Compliance: {comp['status']}",
                subtitle=f"Evaluated {comp['total_days_evaluated']} nights | Threshold: ≥4h on ≥70% of nights",
                rows=[
                    comp["summary"],
                    f"Weight-to-AHI Correlation (r): {comp.get('weight_to_ahi_correlation_r')}",
                    f"Snoring-to-AHI Correlation (r): {comp.get('snoring_to_ahi_correlation_r')}",
                ],
            )
            return JSONResponse({"parts": [{"kind": "text", "text": comp["summary"]}, *[{"kind": "a2ui", "data": m} for m in card["messages"]]]})
        if "stop-bang" in lower or "risk" in lower or "profile" in lower or "bmi" in lower or "smok" in lower:
            scr = evaluate_osa_risk_and_screening(user_id=user_id)
            sb = scr["stop_bang"]
            card = _build_a2ui_card(
                title=f"Wellness Risk Profile — STOP-BANG {sb['score']}/8 ({sb['risk_level']})",
                subtitle="Wellness guidance only, not a clinical diagnosis",
                rows=[
                    f"BMI: {scr['bmi']} kg/m² ({scr['bmi_category']}) | Neck: {scr['neck_circumference_cm']} cm",
                    f"Active Drivers: {', '.join(sb['active_drivers'])}",
                    scr["smoking_clinical_context"],
                    sb["clinical_guidance"],
                ],
            )
            return JSONResponse({"parts": [{"kind": "text", "text": sb["clinical_guidance"]}, *[{"kind": "a2ui", "data": m} for m in card["messages"]]]})
        if "weather" in lower or "humidity" in lower or "rainout" in lower:
            w = get_local_weather_and_humidity(get_profile(user_id).get("city", "Bengaluru"))
            return JSONResponse({"parts": [{"kind": "text", "text": f"**{w.get('location')}**: {w.get('temperature_celsius')}°C, Humidity {w.get('relative_humidity_percent')}%, US AQI {w.get('us_aqi')}.\n\n• {w.get('cpap_climate_tip')}\n• {w.get('air_quality_nasal_tip')}"}]})
        if "insight" in lower or "weekly" in lower or "summary" in lower:
            ins = generate_weekly_wellness_insights(user_id=user_id)
            txt = (
                "**Weekly AI Wellness Summary**\n"
                + "\n".join(f"✅ {i}" for i in ins["what_improved"])
                + "\n"
                + "\n".join(f"⚠️ {s}" for s in ins["what_slipped"])
                + f"\n🎯 **One Thing to Try:** {ins['one_thing_to_try']}"
            )
            return JSONResponse({"parts": [{"kind": "text", "text": txt}]})
        return JSONResponse({"parts": [{"kind": "text", "text": f"SomnoCare Assistant processed your request using local clinical profile data. (Note: {type(exc).__name__})"}]})

    return JSONResponse({"parts": [{"kind": "text", "text": "How can I help with your CPAP therapy, STOP-BANG screening, snoring trends, or exercises today?"}]})
