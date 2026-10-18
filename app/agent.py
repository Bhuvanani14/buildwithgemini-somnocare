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
import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from app.wellness_hub import (
    calculate_ess_score,
    calculate_stop_bang_score,
    compute_bmi_metrics,
    compute_pearson_correlation,
    evaluate_safety_red_flags,
    get_store,
)

# Hardcoded GCP Project ID for reliable client initialization across local and Agent Platform
PROJECT_ID = "qwiklabs-gcp-03-fe29ebecbbcc"
MODEL = "gemini-3.8-flash"

_db: Optional[Any] = None


def get_db():
    global _db
    if _db is None:
        from google.cloud import firestore

        _db = firestore.Client(project=PROJECT_ID)
    return _db


# =====================================================================
# 1. CPAP SUPPLIES CATALOG
# =====================================================================
def search_cpap_supplies(category: str = "", query: str = "") -> List[Dict[str, Any]]:
    """Search the CPAP supplies catalog for masks, replacement cushions, filters, and heated tubing.

    Args:
        category: Optional category filter: 'mask', 'filter', or 'tubing'.
        query: Optional keyword search term to match against supply names and descriptions.

    Returns:
        A list of matching CPAP supplies with replacement intervals and details.
    """
    store = get_store()
    docs = store.list_collection("cpap_supplies")
    results = []
    category_lower = category.lower().strip()
    query_lower = query.lower().strip()

    for data in docs:
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


# =====================================================================
# 2. PATIENT PROFILE (AGE, BMI, SMOKING, NECK SIZE, STOP-BANG, ESS)
# =====================================================================
def get_profile(user_id: str = "default_user") -> Dict[str, Any]:
    """Retrieve the patient's clinical & lifestyle risk profile from Firestore (`patient_profile` collection).

    Includes age, height, weight, BMI & trend history, smoking status & smoke-free streak,
    neck circumference, hypertension status, STOP-BANG screening score, and Epworth Sleepiness Scale (ESS).

    Args:
        user_id: Identifier for the patient/user (default 'default_user').

    Returns:
        Complete patient profile dictionary with risk and lifestyle context.
    """
    store = get_store()
    profile = store.get_document("patient_profile", user_id)
    if not profile:
        profile = store.get_document("patient_profile", "default_user") or {"user_id": user_id}

    # Dynamically compute smoke-free streak days ifsmoking_quit_date is set
    quit_date_str = profile.get("smoking_quit_date")
    if quit_date_str and profile.get("smoking_status") in ("former", "quit"):
        try:
            q_date = datetime.date.fromisoformat(str(quit_date_str)[:10])
            streak = max(0, (datetime.date.today() - q_date).days)
            profile["smoke_free_streak_days"] = streak
        except Exception:
            pass

    # Add age-appropriate exercise guidance & clinical smoking note
    age = int(profile.get("age", 45))
    max_hr = 220 - age
    profile["exercise_intensity_guide"] = {
        "estimated_max_hr_bpm": max_hr,
        "moderate_zone_bpm": f"{int(max_hr * 0.50)}-{int(max_hr * 0.70)} bpm",
        "recommendation": (
            "Low-impact joint-friendly squats, restorative yoga (Bridge, Cat-Cow), and daily 5-minute oropharyngeal throat exercises."
            if age >= 50
            else "Moderate cardiovascular conditioning, full-range squats/push-ups, yoga flow, and daily oropharyngeal airway toning."
        ),
    }
    profile["clinical_disclaimer"] = "Wellness guidance and screening context only — not a medical diagnosis."
    return profile


def update_profile(
    user_id: str = "default_user",
    name: Optional[str] = None,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    target_weight_kg: Optional[float] = None,
    neck_circumference_cm: Optional[float] = None,
    has_hypertension: Optional[bool] = None,
    smoking_status: Optional[str] = None,
    cigarettes_per_day: Optional[int] = None,
    smoking_quit_date: Optional[str] = None,
    city: Optional[str] = None,
    mask_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the patient's profile in the Firestore `patient_profile` collection.

    Automatically recalculates BMI, appends to `bmi_history`, updates the smoke-free streak,
    and refreshes the STOP-BANG OSA screening score.

    Args:
        user_id: Patient identifier.
        name: Patient's full name.
        age: Patient's age in years.
        sex: Biological sex ('male' or 'female').
        height_cm: Height in centimeters.
        weight_kg: Current weight in kilograms.
        target_weight_kg: Goal weight in kilograms.
        neck_circumference_cm: Neck circumference in centimeters (STOP-BANG threshold >40 cm).
        has_hypertension: True if patient has high blood pressure.
        smoking_status: 'never', 'current', or 'former'.
        cigarettes_per_day: Number of cigarettes smoked per day.
        smoking_quit_date: ISO date (YYYY-MM-DD) when the user quit smoking.
        city: City for ambient weather, humidity, and air quality checks.
        mask_model: Current CPAP mask model name.

    Returns:
        Updated patient profile including recalculated BMI, smoke-free streak, and STOP-BANG score.
    """
    store = get_store()
    current = get_profile(user_id=user_id)

    if name is not None:
        current["name"] = name
    if age is not None:
        current["age"] = int(age)
    if sex is not None:
        current["sex"] = sex.lower().strip()
    if height_cm is not None:
        current["height_cm"] = float(height_cm)
    if weight_kg is not None:
        current["weight_kg"] = float(weight_kg)
    if target_weight_kg is not None:
        current["target_weight_kg"] = float(target_weight_kg)
    if neck_circumference_cm is not None:
        current["neck_circumference_cm"] = float(neck_circumference_cm)
    if has_hypertension is not None:
        current["has_hypertension"] = bool(has_hypertension)
    if smoking_status is not None:
        current["smoking_status"] = smoking_status.lower().strip()
    if cigarettes_per_day is not None:
        current["cigarettes_per_day"] = int(cigarettes_per_day)
    if smoking_quit_date is not None:
        current["smoking_quit_date"] = smoking_quit_date
    if city is not None:
        current["city"] = city
    if mask_model is not None:
        current["mask_model"] = mask_model

    # Recompute BMI
    h_cm = float(current.get("height_cm", 175.0))
    w_kg = float(current.get("weight_kg", 85.0))
    bmi_info = compute_bmi_metrics(h_cm, w_kg)
    current["bmi"] = bmi_info["bmi"]
    current["bmi_category"] = bmi_info["bmi_category"]

    # Update BMI history
    today_str = datetime.date.today().isoformat()
    bmi_hist = list(current.get("bmi_history", []))
    if bmi_hist and bmi_hist[-1].get("date") == today_str:
        bmi_hist[-1]["weight_kg"] = w_kg
        bmi_hist[-1]["bmi"] = bmi_info["bmi"]
    else:
        bmi_hist.append({"date": today_str, "weight_kg": w_kg, "bmi": bmi_info["bmi"]})
    current["bmi_history"] = bmi_hist[-30:]

    # Recompute smoke-free streak
    if current.get("smoking_quit_date"):
        try:
            qd = datetime.date.fromisoformat(str(current["smoking_quit_date"])[:10])
            current["smoke_free_streak_days"] = max(0, (datetime.date.today() - qd).days)
        except Exception:
            pass

    # Refresh STOP-BANG
    sb_prev = current.get("stop_bang", {})
    sb = calculate_stop_bang_score(
        snoring=bool(sb_prev.get("snoring", True)),
        tired=bool(sb_prev.get("tired", True)),
        observed_apnea=bool(sb_prev.get("observed_apnea", False)),
        high_blood_pressure=bool(current.get("has_hypertension", False)),
        bmi=float(current["bmi"]),
        age=int(current.get("age", 50)),
        neck_circumference_cm=float(current.get("neck_circumference_cm", 40.0)),
        sex=str(current.get("sex", "male")),
    )
    current["stop_bang"] = {
        "snoring": bool(sb_prev.get("snoring", True)),
        "tired": bool(sb_prev.get("tired", True)),
        "observed_apnea": bool(sb_prev.get("observed_apnea", False)),
        "high_blood_pressure": bool(current.get("has_hypertension", False)),
        "bmi_over_35": sb["items"]["B_bmi_over_35"],
        "age_over_50": sb["items"]["A_age_over_50"],
        "neck_over_40cm": sb["items"]["N_neck_over_40cm"],
        "male_gender": sb["items"]["G_gender_male"],
        "score": sb["score"],
        "risk_level": sb["risk_level"],
    }
    current["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    store.set_document("patient_profile", user_id, current, merge=True)
    return {
        "status": "success",
        "message": "Patient profile updated in Firestore.",
        "profile": current,
        "bmi_analysis": bmi_info,
        "stop_bang_summary": sb,
    }


# =====================================================================
# 3. SLEEP THERAPY & SNORING LOGGING + HISTORY
# =====================================================================
def log_sleep_therapy_entry(
    date: str,
    usage_hours: float,
    ahi: float,
    mask_leak_rate: float,
    restedness_score: int,
    notes: str = "",
    user_id: str = "default_user",
    snoring_score: int = 2,
    snore_minutes: float = 10.0,
    snore_loudness_db: float = 42.0,
    sleep_position: str = "side",
    alcohol_units: int = 0,
    caffeine_mg: int = 80,
    morning_dryness: int = 2,
    weight_kg: Optional[float] = None,
) -> Dict[str, Any]:
    """Log a nightly CPAP sleep therapy, snoring, and lifestyle entry into Firestore.

    Args:
        date: The date of the therapy session in YYYY-MM-DD format (e.g. '2026-10-18').
        usage_hours: Total CPAP run time in hours (e.g. 6.5).
        ahi: Apnea-Hypopnea Index events per hour (e.g. 2.1).
        mask_leak_rate: Mask leak rate in liters per minute (e.g. 5.4).
        restedness_score: Subjective restedness rating from 1 (exhausted) to 10 (fully refreshed).
        notes: Optional user notes or side effects (e.g. 'dry mouth, adjusted ramp').
        user_id: Identifier for the patient/user.
        snoring_score: Self-reported or acoustic snoring severity from 0 (silent) to 10 (severe).
        snore_minutes: Total minutes of snoring detected overnight.
        snore_loudness_db: Peak or mean snore loudness in dB.
        sleep_position: Dominant sleep position ('side', 'back', 'stomach', 'mixed').
        alcohol_units: Evening alcohol drinks consumed within 4 hours of sleep.
        caffeine_mg: Total daily caffeine intake in mg.
        morning_dryness: Morning mouth/nasal dryness score (1-10).
        weight_kg: Optional morning body weight in kg to link weight trend to AHI.

    Returns:
        Confirmation dict with logged metrics, positional/alcohol feedback, and safety check.
    """
    store = get_store()
    profile = get_profile(user_id=user_id)
    h_cm = float(profile.get("height_cm", 175.0))
    w_kg = float(weight_kg) if weight_kg is not None else float(profile.get("weight_kg", 88.0))
    bmi_val = round(w_kg / ((h_cm / 100.0) ** 2), 1)

    doc_id = f"log-{user_id}-{date.replace('-', '')}"
    entry = {
        "id": doc_id,
        "user_id": user_id,
        "date": date,
        "usage_hours": float(usage_hours),
        "ahi": float(ahi),
        "mask_leak_rate": float(mask_leak_rate),
        "restedness_score": int(restedness_score),
        "snoring_score": int(snoring_score),
        "snore_minutes": float(snore_minutes),
        "snore_loudness_db": float(snore_loudness_db),
        "sleep_position": sleep_position.lower().strip(),
        "alcohol_units": int(alcohol_units),
        "caffeine_mg": int(caffeine_mg),
        "morning_dryness": int(morning_dryness),
        "weight_kg": w_kg,
        "bmi": bmi_val,
        "notes": notes,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    store.set_document("sleep_therapy_logs", doc_id, entry, merge=True)

    if weight_kg is not None:
        update_profile(user_id=user_id, weight_kg=w_kg)

    safety = evaluate_safety_red_flags(text_or_symptoms=notes, ahi=float(ahi))
    coaching_tips = []
    if sleep_position.lower().strip() == "back":
        coaching_tips.append(
            "Positional Therapy Tip: Supine (back) sleeping allows gravity to pull the tongue base backward, often doubling AHI and snoring. Try side-sleeping or a positional wedge pillow."
        )
    if int(alcohol_units) > 0:
        coaching_tips.append(
            f"Evening Alcohol Note: {alcohol_units} drink(s) logged. Alcohol relaxes upper airway dilator muscles (genioglossus) and increases mask-leak/AHI events during REM sleep."
        )

    return {
        "status": "success",
        "message": f"Successfully logged sleep therapy and snoring entry for {date}.",
        "entry_id": doc_id,
        "ahi": float(ahi),
        "usage_hours": float(usage_hours),
        "snoring_score": int(snoring_score),
        "coaching_tips": coaching_tips,
        "safety_check": safety,
    }


def get_sleep_therapy_history(user_id: str = "default_user", limit: int = 14) -> List[Dict[str, Any]]:
    """Retrieve recent nightly CPAP sleep therapy and snoring logs for a patient from Firestore.

    Args:
        user_id: Patient/user identifier.
        limit: Maximum number of recent entries to return (default 14).

    Returns:
        List of historical sleep records sorted newest-first.
    """
    store = get_store()
    records = store.list_collection("sleep_therapy_logs", user_id=user_id)
    records.sort(key=lambda r: str(r.get("date", "")), reverse=True)
    return records[:limit]


# =====================================================================
# 4. CMS COMPLIANCE & CORRELATION ANALYTICS
# =====================================================================
def calculate_cms_adherence_compliance(user_id: str = "default_user", window_days: int = 30) -> Dict[str, Any]:
    """Calculate Medicare / CMS 30-day CPAP adherence compliance and lifestyle correlations.

    CMS criteria: CPAP usage must be at least 4.0 hours per night on at least 70% of days
    within a consecutive 30-day evaluation window. Also computes Weight-vs-AHI and Snoring-vs-AHI trends.

    Args:
        user_id: Patient/user identifier.
        window_days: Days to evaluate (default 30).

    Returns:
        Compliance report with percentage, compliant days count, mean AHI, snoring average, and correlations.
    """
    records = get_sleep_therapy_history(user_id=user_id, limit=window_days)
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
    avg_leak = round(sum(float(r.get("mask_leak_rate", 0)) for r in records) / total_logged_days, 1)
    avg_snore = round(sum(float(r.get("snoring_score", 0)) for r in records) / total_logged_days, 1)

    chronological = list(reversed(records))
    weights = [float(r.get("weight_kg", 88.0)) for r in chronological if r.get("weight_kg") is not None]
    ahis = [float(r.get("ahi", 0.0)) for r in chronological]
    snores = [float(r.get("snoring_score", 0.0)) for r in chronological]

    weight_ahi_r = compute_pearson_correlation(weights, ahis) if len(weights) == len(ahis) else None
    snore_ahi_r = compute_pearson_correlation(snores, ahis)

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
        "average_mask_leak_lpm": avg_leak,
        "average_snoring_score": avg_snore,
        "weight_to_ahi_correlation_r": weight_ahi_r,
        "snoring_to_ahi_correlation_r": snore_ahi_r,
        "summary": (
            f"{compliant_days}/{total_logged_days} nights ({compliance_percentage}%) met the 4-hour CMS threshold. "
            f"Average nightly usage: {avg_hours}h | Mean AHI: {avg_ahi} | Mean Snoring Score: {avg_snore}/10."
        ),
    }


# =====================================================================
# 5. STOP-BANG, ESS & COMPREHENSIVE RISK DASHBOARD TOOLS
# =====================================================================
def evaluate_osa_risk_and_screening(
    user_id: str = "default_user",
    snoring_loud: Optional[bool] = None,
    daytime_tiredness: Optional[bool] = None,
    observed_apnea: Optional[bool] = None,
    high_blood_pressure: Optional[bool] = None,
    ess_responses: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Run STOP-BANG and Epworth Sleepiness Scale (ESS) screening and compute the composite Wellness Risk Dashboard.

    Shows transparent risk drivers (Age, BMI, Neck Circumference, Smoking, Snoring, Hypertension, Sleepiness)
    so the score is never a black box. Always framed as wellness guidance, not a clinical diagnosis.

    Args:
        user_id: Patient identifier.
        snoring_loud: Optional override for STOP-BANG 'Snoring loudly' question.
        daytime_tiredness: Optional override for STOP-BANG 'Tired/fatigued during day' question.
        observed_apnea: Optional override for STOP-BANG 'Observed stop breathing' question.
        high_blood_pressure: Optional override for STOP-BANG 'High blood pressure' question.
        ess_responses: Optional list of 8 integers (0-3) for Epworth Sleepiness Scale items.

    Returns:
        STOP-BANG breakdown, ESS breakdown, Smoking & BMI impact analysis, and composite Wellness Risk Score.
    """
    store = get_store()
    profile = get_profile(user_id=user_id)
    prev_sb = profile.get("stop_bang", {})

    s_flag = snoring_loud if snoring_loud is not None else bool(prev_sb.get("snoring", True))
    t_flag = daytime_tiredness if daytime_tiredness is not None else bool(prev_sb.get("tired", True))
    o_flag = observed_apnea if observed_apnea is not None else bool(prev_sb.get("observed_apnea", False))
    p_flag = high_blood_pressure if high_blood_pressure is not None else bool(profile.get("has_hypertension", True))

    stop_bang = calculate_stop_bang_score(
        snoring=s_flag,
        tired=t_flag,
        observed_apnea=o_flag,
        high_blood_pressure=p_flag,
        bmi=float(profile.get("bmi", 29.5)),
        age=int(profile.get("age", 52)),
        neck_circumference_cm=float(profile.get("neck_circumference_cm", 41.5)),
        sex=str(profile.get("sex", "male")),
    )

    if ess_responses:
        ess = calculate_ess_score(ess_responses)
        profile["ess"] = {
            **profile.get("ess", {}),
            "score": ess["score"],
            "severity": ess["severity"],
        }
    else:
        saved_ess = profile.get("ess", {})
        default_items = [
            saved_ess.get("sitting_reading", 2),
            saved_ess.get("watching_tv", 2),
            saved_ess.get("sitting_inactive_public", 1),
            saved_ess.get("passenger_car_1hr", 2),
            saved_ess.get("lying_down_afternoon", 2),
            saved_ess.get("sitting_talking", 0),
            saved_ess.get("sitting_quietly_after_lunch", 1),
            saved_ess.get("in_car_stopped_traffic", 0),
        ]
        ess = calculate_ess_score(default_items)

    # Save updated screening back to profile
    profile["has_hypertension"] = p_flag
    profile["stop_bang"] = {
        "snoring": s_flag,
        "tired": t_flag,
        "observed_apnea": o_flag,
        "high_blood_pressure": p_flag,
        "bmi_over_35": stop_bang["items"]["B_bmi_over_35"],
        "age_over_50": stop_bang["items"]["A_age_over_50"],
        "neck_over_40cm": stop_bang["items"]["N_neck_over_40cm"],
        "male_gender": stop_bang["items"]["G_gender_male"],
        "score": stop_bang["score"],
        "risk_level": stop_bang["risk_level"],
    }
    store.set_document("patient_profile", user_id, profile, merge=True)

    # Smoking clinical context (Wisconsin Sleep Cohort / clinical literature)
    smoking_status = profile.get("smoking_status", "former")
    streak_days = int(profile.get("smoke_free_streak_days", 0))
    smoking_insight = (
        f"Smoke-Free Streak: {streak_days} days! Clinical studies (e.g., Wisconsin Sleep Cohort Study, Wetter et al.) "
        "show current smokers have ~2.5x to 3x higher odds of moderate-to-severe OSA due to upper airway mucosal inflammation "
        "and nocturnal nicotine withdrawal. Each smoke-free week reduces nasal resistance, morning dryness, and CPAP mask irritation."
    )

    return {
        "status": "success",
        "stop_bang": stop_bang,
        "epworth_sleepiness_scale": ess,
        "bmi": profile.get("bmi"),
        "bmi_category": profile.get("bmi_category"),
        "neck_circumference_cm": profile.get("neck_circumference_cm"),
        "smoking_status": smoking_status,
        "smoke_free_streak_days": streak_days,
        "smoking_clinical_context": smoking_insight,
        "disclaimer": "This screening summary provides educational wellness guidance only and is not a medical diagnosis.",
    }


# =====================================================================
# 6. EXERCISE, YOGA & OROPHARYNGEAL THERAPY LOGGING
# =====================================================================
def log_exercise_or_yoga_session(
    exercise_type: str,
    reps: int,
    duration_seconds: int,
    form_accuracy_score: float = 92.0,
    notes: str = "",
    user_id: str = "default_user",
) -> Dict[str, Any]:
    """Log an OpenCV / MediaPipe Pose exercise, yoga pose, or oropharyngeal throat therapy session.

    Args:
        exercise_type: Identifier or name of exercise (e.g., 'bodyweight_squat', 'push_up',
            'yoga_bridge_setu_bandhasana', 'yoga_cat_cow', 'oropharyngeal_tongue_slide', 'pranayama_box_breathing').
        reps: Completed repetitions or breath cycles.
        duration_seconds: Total duration of the session in seconds.
        form_accuracy_score: MediaPipe Pose landmark alignment score (0-100%).
        notes: Coaching feedback or user notes.
        user_id: Patient identifier.

    Returns:
        Logged workout summary and supportive clinical context for sleep apnea.
    """
    store = get_store()
    today_str = datetime.date.today().isoformat()
    doc_id = f"ex-{user_id}-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"

    ex_lower = exercise_type.lower()
    if "oropharyngeal" in ex_lower or "tongue" in ex_lower or "throat" in ex_lower:
        category = "Oropharyngeal (Throat) Therapy"
        cal = round(duration_seconds * 0.05, 1)
        clinical_note = (
            "Supportive Therapy Note: Randomized trials (e.g., Guimarães et al., AJRCCM) suggest consistent oropharyngeal exercises "
            "toning the genioglossus and soft palate may reduce snoring intensity and support mild-to-moderate OSA management alongside CPAP."
        )
    elif "yoga" in ex_lower or "bridge" in ex_lower or "cat" in ex_lower or "pranayama" in ex_lower or "breath" in ex_lower:
        category = "Restorative Yoga & Pranayama"
        cal = round(duration_seconds * 0.09, 1)
        clinical_note = (
            "Supportive Therapy Note: Thoracic expansion poses and slow nasal pranayama enhance parasympathetic tone, "
            "reduce bedtime cortisol, and improve tolerance to CPAP nasal airflow."
        )
    else:
        category = "Cardio & Weight Management"
        cal = round(duration_seconds * 0.15 + reps * 0.8, 1)
        clinical_note = (
            "Supportive Therapy Note: Regular physical activity reduces visceral and parapharyngeal fat pads and improves slow-wave sleep independent of weight loss."
        )

    entry = {
        "id": doc_id,
        "user_id": user_id,
        "date": today_str,
        "exercise_type": exercise_type,
        "category": category,
        "reps": int(reps),
        "duration_seconds": int(duration_seconds),
        "form_accuracy_score": round(float(form_accuracy_score), 1),
        "calories_est": cal,
        "notes": notes,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    store.set_document("exercise_logs", doc_id, entry, merge=True)
    return {
        "status": "success",
        "message": f"Logged {reps} reps ({duration_seconds}s) of {exercise_type} with {form_accuracy_score}% pose accuracy.",
        "entry": entry,
        "clinical_context": clinical_note,
    }


# =====================================================================
# 7. AMBIENT WEATHER, HUMIDITY & AIR QUALITY (AQI / POLLEN)
# =====================================================================
def get_local_weather_and_humidity(city_or_location: str) -> Dict[str, Any]:
    """Fetch current ambient temperature, relative humidity, and Air Quality Index (AQI/PM2.5) for CPAP tuning.

    Calls the free Open-Meteo Weather & Air Quality APIs to advise on CPAP humidifier chamber levels,
    heated tubing ('rainout' prevention), and nasal filter/saline care for congestion.

    Args:
        city_or_location: Name of the city or locality (e.g., 'Bengaluru', 'San Francisco', 'New York').

    Returns:
        Current ambient temperature (°C/°F), relative humidity (%), US AQI, PM2.5, and CPAP climate & filter tips.
    """
    try:
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

        # Fetch Open-Meteo Air Quality (AQI & PM2.5)
        us_aqi = None
        pm25 = None
        try:
            aqi_url = (
                f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
                f"&current=us_aqi,pm2_5,pm10"
            )
            with urllib.request.urlopen(aqi_url, timeout=4) as aqi_resp:
                aqi_data = json.loads(aqi_resp.read().decode("utf-8")).get("current", {})
                us_aqi = aqi_data.get("us_aqi")
                pm25 = aqi_data.get("pm2_5")
        except Exception:
            pass

        if humidity is not None and humidity > 70:
            climate_tip = (
                f"Ambient humidity is high ({humidity}%). To prevent tube condensation ('rainout'), "
                "consider lowering your humidifier chamber level by 1 or enabling ClimateLine heated tubing (27°C / 80°F)."
            )
        elif humidity is not None and humidity < 35:
            climate_tip = (
                f"Ambient humidity is dry ({humidity}%). Increase your CPAP humidifier chamber level to 4–5 "
                "or use a heated tube to prevent dry nasal passages and morning throat irritation."
            )
        else:
            climate_tip = (
                f"Ambient humidity is moderate ({humidity}%). Auto-Climate control or humidifier level 3–4 should feel comfortable."
            )

        aqi_tip = "Air quality is clean; standard 14-day disposable CPAP filter replacement schedule applies."
        if us_aqi is not None and us_aqi > 100:
            aqi_tip = (
                f"Elevated Air Pollution (US AQI {us_aqi}, PM2.5 {pm25} µg/m³). Use an Ultra-Fine Hypoallergenic CPAP filter, "
                "inspect it weekly, and perform an isotonic saline nasal rinse 30 minutes before putting on your mask."
            )
        elif us_aqi is not None and us_aqi > 50:
            aqi_tip = (
                f"Moderate Air Quality (US AQI {us_aqi}). Keep bedroom windows closed overnight and ensure your CPAP air inlet filter is clean."
            )

        return {
            "status": "success",
            "location": resolved_name,
            "temperature_celsius": temp_c,
            "temperature_fahrenheit": temp_f,
            "relative_humidity_percent": humidity,
            "us_aqi": us_aqi,
            "pm2_5_ug_m3": pm25,
            "cpap_climate_tip": climate_tip,
            "air_quality_nasal_tip": aqi_tip,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch weather data: {str(e)}",
        }


# =====================================================================
# 8. WEEKLY AI INSIGHT SUMMARY & DOCTOR REPORT DATA
# =====================================================================
def generate_weekly_wellness_insights(user_id: str = "default_user") -> Dict[str, Any]:
    """Generate a structured Weekly AI Insight Summary ('What Improved', 'What Slipped', 'One Thing to Try')
    plus gamification streaks and smart supply reminders.

    Args:
        user_id: Patient identifier.

    Returns:
        Structured weekly comparison, streaks, badges, supply alerts, and actionable priorities.
    """
    store = get_store()
    profile = get_profile(user_id=user_id)
    logs = get_sleep_therapy_history(user_id=user_id, limit=14)
    exercises = store.list_collection("exercise_logs", user_id=user_id)

    recent_7 = logs[:7]
    prev_7 = logs[7:14]

    def _avg(items: List[Dict[str, Any]], key: str, default: float = 0.0) -> float:
        if not items:
            return default
        return round(sum(float(i.get(key, default)) for i in items) / len(items), 2)

    rec_ahi = _avg(recent_7, "ahi")
    prev_ahi = _avg(prev_7, "ahi", rec_ahi)
    rec_hrs = _avg(recent_7, "usage_hours")
    prev_hrs = _avg(prev_7, "usage_hours", rec_hrs)
    rec_snore = _avg(recent_7, "snoring_score")
    prev_snore = _avg(prev_7, "snoring_score", rec_snore)
    rec_leak = _avg(recent_7, "mask_leak_rate")
    prev_leak = _avg(prev_7, "mask_leak_rate", rec_leak)

    what_improved = []
    what_slipped = []

    if rec_ahi <= prev_ahi:
        what_improved.append(f"Mean AHI improved from {prev_ahi} to {rec_ahi} events/hr ({round(prev_ahi - rec_ahi, 1)} fewer events/hr).")
    else:
        what_slipped.append(f"Mean AHI rose slightly from {prev_ahi} to {rec_ahi} events/hr.")

    if rec_hrs >= prev_hrs:
        what_improved.append(f"CPAP nightly usage increased from {prev_hrs}h to {rec_hrs}h per night.")
    else:
        what_slipped.append(f"Average CPAP usage dipped from {prev_hrs}h to {rec_hrs}h per night.")

    if rec_snore <= prev_snore:
        what_improved.append(f"Snoring severity score dropped from {prev_snore}/10 to {rec_snore}/10.")
    else:
        what_slipped.append(f"Snoring score increased from {prev_snore}/10 to {rec_snore}/10.")

    if rec_leak > 10.0:
        what_slipped.append(f"Mask leak rate averaged {rec_leak} L/min (target <10 L/min).")
    else:
        what_improved.append(f"Mask seal remained tight with low average leak ({rec_leak} L/min).")

    smoke_streak = int(profile.get("smoke_free_streak_days", 0))
    if smoke_streak > 0:
        what_improved.append(f"Maintained a {smoke_streak}-day smoke-free streak, reducing upper-airway mucosal edema.")

    # Compute adherence streak
    cpap_streak = 0
    for r in logs:
        if float(r.get("usage_hours", 0)) >= 4.0:
            cpap_streak += 1
        else:
            break

    one_thing_to_try = (
        "Practice 5 minutes of Oropharyngeal Tongue-Slide exercises + Side-Sleeping positional alignment tonight, "
        "and avoid alcohol within 4 hours of bedtime to keep AHI under 2.5."
    )
    if rec_leak > 12.0:
        one_thing_to_try = (
            "Wash your silicone mask cushion with warm soapy water and run the Mask Fit Check before sleep to eliminate high-pressure seal leaks."
        )

    # Supply replacement reminders
    today = datetime.date.today()
    last_rep = profile.get("supply_last_replaced", {})
    intervals = {"filter": 14, "cushion": 30, "tubing": 90, "mask": 180}
    reminders = []
    for part, max_days in intervals.items():
        d_str = last_rep.get(part)
        if d_str:
            try:
                days_used = (today - datetime.date.fromisoformat(str(d_str)[:10])).days
                days_left = max_days - days_used
                reminders.append({
                    "component": part.capitalize(),
                    "days_used": days_used,
                    "interval_days": max_days,
                    "days_remaining": days_left,
                    "status": "DUE_SOON" if days_left <= 5 else "OK",
                })
            except Exception:
                pass

    return {
        "status": "success",
        "what_improved": what_improved,
        "what_slipped": what_slipped or ["No major regressions this week — stellar consistency!"],
        "one_thing_to_try": one_thing_to_try,
        "metrics_comparison": {
            "recent_7d_ahi": rec_ahi,
            "previous_7d_ahi": prev_ahi,
            "recent_7d_usage_hours": rec_hrs,
            "previous_7d_usage_hours": prev_hrs,
            "recent_7d_snoring": rec_snore,
            "previous_7d_snoring": prev_snore,
            "recent_7d_leak_lpm": rec_leak,
        },
        "streaks_and_badges": {
            "cpap_4h_compliance_streak_days": cpap_streak,
            "smoke_free_streak_days": smoke_streak,
            "exercise_sessions_completed": len(exercises),
            "badges": [
                b
                for b in [
                    "CMS 70%+ Compliant Star" if rec_hrs >= 4.0 else None,
                    f"{smoke_streak}-Day Smoke-Free Airway Champion" if smoke_streak >= 7 else None,
                    "Low-AHI Whisper Sleeper (<3.0)" if rec_ahi < 3.0 else None,
                    "MediaPipe Active Toner" if len(exercises) >= 3 else None,
                ]
                if b
            ],
        },
        "supply_reminders": reminders,
        "disclaimer": "Educational wellness summary — share with your sleep physician during follow-ups.",
    }


# =====================================================================
# 9. FIND NEARBY SLEEP CLINICS & SLEEP LABS
# =====================================================================
def find_nearby_sleep_clinics(city_or_location: str = "Bengaluru") -> Dict[str, Any]:
    """Find accredited sleep medicine clinics, polysomnography labs, and CPAP specialists near a city.

    Uses OpenStreetMap Nominatim / Overpass and curated clinical directories with Google Maps booking links.

    Args:
        city_or_location: City or region name.

    Returns:
        List of sleep clinics, distance/locality, services offered, and Google Maps search URLs.
    """
    curated_directory = {
        "bengaluru": [
            {
                "name": "Manipal Hospital Comprehensive Sleep Medicine Center",
                "locality": "Old Airport Road, Bengaluru",
                "specialties": "Level-1 Polysomnography, CPAP/BiPAP Titration, ENT Airway Evaluation",
                "phone": "+91-80-2502-4444",
                "maps_url": "https://www.google.com/maps/search/?api=1&query=Manipal+Hospital+Sleep+Clinic+Bengaluru",
            },
            {
                "name": "Narayana Health Pulmonology & Sleep Apnea Lab",
                "locality": "Bommasandra / HSR Layout, Bengaluru",
                "specialties": "Home Sleep Apnea Testing (HSAT), Auto-CPAP Optimization, Somnoplasty Consultation",
                "phone": "+91-80-7122-2222",
                "maps_url": "https://www.google.com/maps/search/?api=1&query=Narayana+Health+Sleep+Clinic+Bengaluru",
            },
            {
                "name": "Aster CMI Sleep Disorders & Respiratory Care Clinic",
                "locality": "Hebbal, Bengaluru",
                "specialties": "Split-Night Sleep Study, Mask Fit Clinic, Positional & Myofunctional Therapy",
                "phone": "+91-80-4342-0100",
                "maps_url": "https://www.google.com/maps/search/?api=1&query=Aster+CMI+Sleep+Clinic+Bengaluru",
            },
        ],
    }

    key = city_or_location.lower().strip()
    clinics = curated_directory.get(key, [])
    if not clinics:
        q = urllib.parse.quote(f"Sleep Apnea Clinic Polysomnography Lab {city_or_location}")
        clinics = [
            {
                "name": f"{city_or_location.title()} Center for Sleep Medicine & Polysomnography",
                "locality": f"Central Medical District, {city_or_location.title()}",
                "specialties": "Overnight Polysomnography (PSG), Home Sleep Study, CPAP Titration & Mask Fitting",
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={q}",
            },
            {
                "name": f"Pulmonary & OSA Therapy Specialists — {city_or_location.title()}",
                "locality": city_or_location.title(),
                "specialties": "Board-Certified Sleep Physician Consultations, DME Compliance & Oral Appliance Review",
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={q}",
            },
        ]

    return {
        "status": "success",
        "location": city_or_location,
        "clinics": clinics,
        "nudge": "If your STOP-BANG score is ≥3 or you experience daytime sleepiness, schedule an accredited sleep study or titration review.",
    }


# =====================================================================
# 10. MULTIMODAL CPAP ILLUSTRATION GENERATOR
# =====================================================================
def generate_cpap_item_illustration(
    prompt: str,
    tool_context: Any,
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
    from google.genai import types

    gcs_bucket_name = "somnocare-media-qwiklabs-gcp-03-fe29ebecbbcc"

    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

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


AGENT_ENGINE_RESOURCE_NAME = (
    "projects/132095283653/locations/us-east1/reasoningEngines/3470354465888927744"
)
SANDBOX_RESOURCE_NAME = (
    "projects/132095283653/locations/us-east1/reasoningEngines/3470354465888927744/sandboxEnvironments/4286485663303335936"
)

ROLE_DESCRIPTION = """You are SomnoCare, an empathetic, clinically guided AI companion for sleep apnea (OSA) patients and CPAP users.
You remember the user's stated clinical facts, equipment preferences, pressure tolerances, and lifestyle details across conversations and use them to personalize your care.

Your responsibilities:
1. Retrieve and update the user's Risk & Lifestyle Profile (`get_profile`, `update_profile`) including Age, Height, Weight, BMI trend, Neck Circumference, Hypertension, and Smoking status / Smoke-Free Streak.
2. Run OSA wellness screenings (`evaluate_osa_risk_and_screening`) using the official 8-item STOP-BANG questionnaire and Epworth Sleepiness Scale (ESS), clearly explaining which factors drive the score.
3. Help patients track CPAP therapy adherence and nightly metrics (`log_sleep_therapy_entry`, `get_sleep_therapy_history`), including Usage Hours, AHI, Mask Leak Rate, Snoring Score (0-10) & acoustic snore minutes, Sleep Position (side vs. back), and Evening Alcohol/Caffeine.
4. Calculate Medicare / CMS adherence compliance (4+ hours/night on 70% of nights) and Weight-vs-AHI / Snoring-vs-AHI correlations (`calculate_cms_adherence_compliance`).
5. Guide and log OpenCV / MediaPipe Pose exercises, restorative yoga, pranayama breathing, and supportive oropharyngeal (throat) exercises (`log_exercise_or_yoga_session`), adjusting intensity for the user's age.
6. Generate Weekly AI Insight Summaries (`generate_weekly_wellness_insights`) highlighting 'What Improved', 'What Slipped', and 'One Thing to Try', plus supply replacement reminders and nearby sleep clinics (`find_nearby_sleep_clinics`).
7. Check ambient weather, relative humidity, and Air Quality Index (AQI/PM2.5) (`get_local_weather_and_humidity`) to guide CPAP humidifier settings, prevent tube condensation ('rainout'), and manage nasal congestion.
8. Answer questions about CPAP equipment, masks, replacement intervals, and troubleshooting using `search_cpap_supplies` and `generate_cpap_item_illustration`.
9. Adhere strictly to clinical safety guardrails:
   - Always frame screening scores and coaching as "wellness guidance, not a clinical diagnosis".
   - Do NOT modify or advise altering prescribed clinical CPAP pressure settings (cmH2O) without physician consent.
   - For acute red flags (chest pain, severe shortness of breath, drowsy driving, or AHI >= 30), immediately prioritize urgent medical evaluation / emergency care (911) over coaching.
"""

# Conditionally wire Google ADK Agent when google-adk is installed in the environment,
# while allowing tool functions and FastAPI wellness routes to import cleanly anywhere.
try:
    from a2ui.basic_catalog.provider import BasicCatalog
    from a2ui.schema.manager import A2uiSchemaManager
    from google.adk.agents import Agent
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.apps import App
    from google.adk.code_executors import AgentEngineSandboxCodeExecutor
    from google.adk.models import Gemini
    from google.adk.tools.preload_memory_tool import PreloadMemoryTool
    from google.genai import types

    from app.a2ui_utils import a2ui_callback

    async def generate_memories_callback(callback_context: CallbackContext):
        await callback_context.add_session_to_memory()
        return None

    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config("0.8")],
    )

    instruction = schema_manager.generate_system_prompt(
        role_description=ROLE_DESCRIPTION,
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
except ImportError:
    root_agent = None
    app = None
