import datetime
import json
import math
import os
import pathlib
import uuid
from typing import Any, Dict, List, Optional

DATA_DIR = pathlib.Path(
    os.environ.get(
        "SOMNOCARE_DATA_DIR",
        str(pathlib.Path(__file__).resolve().parent.parent / "data"),
    )
)
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_STORE_PATH = DATA_DIR / "local_firestore_store.json"

DEFAULT_SUPPLIES: List[Dict[str, Any]] = [
    {
        "id": "mask-airfit-p10",
        "name": "AirFit P10 Nasal Pillows",
        "category": "mask",
        "type": "Nasal Pillows",
        "description": "Ultra-quiet, minimalist nasal pillows mask with flexible woven-mesh vent.",
        "replacement_interval_days": 180,
        "cushion_replacement_interval_days": 14,
        "in_stock": True,
        "best_for": "Active sleepers, reading before bed, minimal facial contact.",
    },
    {
        "id": "mask-airfit-f20",
        "name": "AirFit F20 Full Face Mask",
        "category": "mask",
        "type": "Full Face",
        "description": "InfinitySeal silicone cushion designed for high pressure and mouth breathers.",
        "replacement_interval_days": 180,
        "cushion_replacement_interval_days": 30,
        "in_stock": True,
        "best_for": "Mouth breathing, high CPAP pressures, frequent nasal congestion.",
    },
    {
        "id": "mask-airfit-n20",
        "name": "AirFit N20 Nasal Mask",
        "category": "mask",
        "type": "Nasal Cradle/Mask",
        "description": "Comfortable nasal mask fitting 99% of face shapes with magnetic clips.",
        "replacement_interval_days": 180,
        "cushion_replacement_interval_days": 30,
        "in_stock": True,
        "best_for": "Nose breathers seeking stability and secure seal across varying pressures.",
    },
    {
        "id": "filter-hypoallergenic",
        "name": "Ultra-Fine Hypoallergenic Air Filters (2-Pack)",
        "category": "filter",
        "type": "Disposable Filter",
        "description": "Blocks fine particulate matter, pollen, and pet dander from entering CPAP airway.",
        "replacement_interval_days": 14,
        "in_stock": True,
        "best_for": "Allergy sufferers and dust prevention.",
    },
    {
        "id": "climate-line-tubing",
        "name": "ClimateLineAir Heated Tubing (15mm)",
        "category": "tubing",
        "type": "Heated Tubing",
        "description": "Maintains comfortable air temperature and prevents condensation (rainout) in tube.",
        "replacement_interval_days": 90,
        "in_stock": True,
        "best_for": "Preventing tube rainout, dry throat, and cold airway sensations.",
    },
]


def _default_seed_store() -> Dict[str, Dict[str, Any]]:
    today = datetime.date.today()
    supplies_map = {item["id"]: item for item in DEFAULT_SUPPLIES}

    # Generate 14 realistic nights of sleep, snoring, weight, lifestyle & CPAP data
    logs_map: Dict[str, Any] = {}
    bmi_history: List[Dict[str, Any]] = []
    base_weight = 92.4
    height_cm = 175.0

    sample_patterns = [
        # (days_ago, usage_hrs, ahi, leak_lpm, rested, snore_score, snore_mins, snore_db, pos, alc, caf, weight_delta, notes)
        (13, 5.2, 6.8, 14.2, 5, 7, 48, 58, "back", 2, 3, 0.0, "Slept on back after late dinner; noticeable snoring and mask leak."),
        (12, 5.8, 5.9, 11.5, 6, 6, 39, 55, "back", 1, 2, -0.1, "Slight dry mouth in morning, adjusted humidifier to level 4."),
        (11, 6.4, 4.7, 9.0, 6, 5, 31, 52, "mixed", 0, 2, -0.2, "Better seal after tightening lower straps."),
        (10, 3.8, 7.2, 16.5, 4, 8, 55, 61, "back", 2, 3, -0.1, "Removed mask early due to nasal congestion; high snoring."),
        (9, 6.7, 4.1, 7.8, 7, 4, 24, 49, "side", 0, 1, -0.4, "Used saline nasal rinse before bed; side-sleeping helped."),
        (8, 7.1, 3.6, 6.2, 7, 4, 20, 47, "side", 0, 1, -0.6, "Did throat exercises and 10 min yoga wind-down."),
        (7, 6.9, 3.4, 5.9, 8, 3, 18, 46, "side", 0, 1, -0.8, "Smoke-free streak building; morning throat dryness subsiding."),
        (6, 7.4, 2.9, 4.8, 8, 3, 14, 45, "side", 0, 1, -1.0, "Comfortable night with ClimateLine heated tube."),
        (5, 6.2, 4.5, 9.4, 6, 5, 27, 51, "mixed", 1, 2, -0.9, "Had 1 glass of wine at dinner; AHI ticked up slightly."),
        (4, 7.5, 2.5, 4.3, 8, 2, 11, 43, "side", 0, 1, -1.2, "Completed oropharyngeal exercise routine and squats."),
        (3, 7.8, 2.1, 3.9, 9, 2, 9, 42, "side", 0, 1, -1.5, "Great sleep efficiency, woke up refreshed with zero dry mouth."),
        (2, 7.3, 2.4, 4.1, 8, 2, 10, 43, "side", 0, 1, -1.7, "Consistent side position; mask seal 99%."),
        (1, 6.5, 3.8, 8.5, 7, 3, 16, 46, "mixed", 0, 2, -1.9, "Slight dry mouth in morning, raised humidity level."),
        (0, 7.6, 1.9, 3.5, 9, 1, 7, 40, "side", 0, 1, -2.1, "Felt well-rested, lowest AHI and snoring score this month!"),
    ]

    for (
        days_ago,
        usage_hrs,
        ahi,
        leak_lpm,
        rested,
        snore_score,
        snore_mins,
        snore_db,
        pos,
        alc,
        caf,
        w_delta,
        notes,
    ) in sample_patterns:
        d_str = (today - datetime.timedelta(days=days_ago)).isoformat()
        doc_id = f"log-default_user-{d_str.replace('-', '')}"
        w_kg = round(base_weight + w_delta, 1)
        bmi_val = round(w_kg / ((height_cm / 100.0) ** 2), 1)
        logs_map[doc_id] = {
            "id": doc_id,
            "user_id": "default_user",
            "date": d_str,
            "usage_hours": usage_hrs,
            "ahi": ahi,
            "mask_leak_rate": leak_lpm,
            "restedness_score": rested,
            "snoring_score": snore_score,
            "snore_minutes": snore_mins,
            "snore_loudness_db": snore_db,
            "sleep_position": pos,
            "alcohol_units": alc,
            "caffeine_mg": caf * 80,
            "morning_dryness": max(1, min(10, int(round(leak_lpm / 2.2)))),
            "weight_kg": w_kg,
            "bmi": bmi_val,
            "notes": notes,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        bmi_history.append({"date": d_str, "weight_kg": w_kg, "bmi": bmi_val, "ahi": ahi})

    quit_date = (today - datetime.timedelta(days=18)).isoformat()
    profile_doc = {
        "user_id": "default_user",
        "name": "Arjun Mehta",
        "age": 52,
        "sex": "male",
        "height_cm": height_cm,
        "weight_kg": round(base_weight - 2.1, 1),
        "target_weight_kg": 82.0,
        "bmi": round((base_weight - 2.1) / ((height_cm / 100.0) ** 2), 1),
        "bmi_category": "Overweight",
        "neck_circumference_cm": 41.5,
        "has_hypertension": True,
        "smoking_status": "former",
        "cigarettes_per_day": 0,
        "previous_cigarettes_per_day": 10,
        "smoking_quit_date": quit_date,
        "smoke_free_streak_days": 18,
        "mask_model": "AirFit N20 Nasal Mask",
        "prescribed_pressure_cmh2o": 10.5,
        "city": "Bengaluru",
        "preferred_language": "en-IN",
        "bmi_history": bmi_history,
        "stop_bang": {
            "snoring": True,
            "tired": True,
            "observed_apnea": False,
            "high_blood_pressure": True,
            "bmi_over_35": False,
            "age_over_50": True,
            "neck_over_40cm": True,
            "male_gender": True,
            "score": 5,
            "risk_level": "High",
        },
        "ess": {
            "sitting_reading": 2,
            "watching_tv": 2,
            "sitting_inactive_public": 1,
            "passenger_car_1hr": 2,
            "lying_down_afternoon": 2,
            "sitting_talking": 0,
            "sitting_quietly_after_lunch": 1,
            "in_car_stopped_traffic": 0,
            "score": 10,
            "severity": "Higher Normal Daytime Sleepiness",
        },
        "supply_last_replaced": {
            "cushion": (today - datetime.timedelta(days=22)).isoformat(),
            "filter": (today - datetime.timedelta(days=11)).isoformat(),
            "tubing": (today - datetime.timedelta(days=65)).isoformat(),
            "mask": (today - datetime.timedelta(days=120)).isoformat(),
        },
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    exercises_map = {
        "ex-1": {
            "id": "ex-1",
            "user_id": "default_user",
            "date": (today - datetime.timedelta(days=2)).isoformat(),
            "exercise_type": "oropharyngeal_tongue_slide",
            "category": "Oropharyngeal (Throat) Therapy",
            "reps": 20,
            "duration_seconds": 300,
            "form_accuracy_score": 94.0,
            "calories_est": 15,
            "notes": "Completed tongue slide, soft palate elevation, and buccal resistance sets.",
        },
        "ex-2": {
            "id": "ex-2",
            "user_id": "default_user",
            "date": (today - datetime.timedelta(days=1)).isoformat(),
            "exercise_type": "yoga_bridge_setu_bandhasana",
            "category": "Restorative Yoga & Pranayama",
            "reps": 8,
            "duration_seconds": 420,
            "form_accuracy_score": 91.5,
            "calories_est": 38,
            "notes": "Bridge pose + Ujjayi chest-opening breathing before sleep.",
        },
        "ex-3": {
            "id": "ex-3",
            "user_id": "default_user",
            "date": today.isoformat(),
            "exercise_type": "bodyweight_squat",
            "category": "Cardio & Weight Management",
            "reps": 25,
            "duration_seconds": 360,
            "form_accuracy_score": 96.0,
            "calories_est": 55,
            "notes": "Morning squat & overhead chest-opener session tracked via MediaPipe Pose.",
        },
    }

    meals_map = {
        "meal-1": {
            "id": "meal-1",
            "user_id": "default_user",
            "date": today.isoformat(),
            "meal_time": "19:30",
            "hours_before_bed": 3.0,
            "description": "Grilled paneer & millet khichdi with cucumber raita (light, low-glycemic dinner)",
            "estimated_calories": 460,
            "is_late_meal": False,
            "is_spicy_or_heavy": False,
            "alcohol_units": 0,
            "caffeine_mg": 0,
            "sleep_impact_tip": "Great timing! Eating a light meal 3 hours before bedtime minimizes gastroesophageal reflux and upper airway edema.",
        }
    }

    partner_map = {
        "partner-1": {
            "id": "partner-1",
            "user_id": "default_user",
            "date": (today - datetime.timedelta(days=9)).isoformat(),
            "observer_name": "Priya (Spouse)",
            "observed_apnea_pauses": False,
            "observed_gasping_choking": False,
            "snoring_intensity": 2,
            "mask_shifted_during_sleep": False,
            "notes": "Much quieter when sleeping on the left side with the nasal mask.",
        }
    }

    return {
        "cpap_supplies": supplies_map,
        "sleep_therapy_logs": logs_map,
        "patient_profile": {"default_user": profile_doc},
        "exercise_logs": exercises_map,
        "meal_logs": meals_map,
        "partner_observations": partner_map,
    }


class StorageBackend:
    """Unified storage backend that transparently uses Google Cloud Firestore when available
    and mirrors/falls back to a fast local JSON store so the app works 100% offline or online."""

    def __init__(self, project_id: str = "qwiklabs-gcp-03-fe29ebecbbcc"):
        self.project_id = project_id
        self._firestore_client = None
        self._firestore_checked = False
        self._ensure_local_store()

    def _ensure_local_store(self) -> None:
        if not LOCAL_STORE_PATH.exists():
            seed_data = _default_seed_store()
            LOCAL_STORE_PATH.write_text(json.dumps(seed_data, indent=2, default=str), encoding="utf-8")

    def _read_local(self) -> Dict[str, Dict[str, Any]]:
        self._ensure_local_store()
        try:
            return json.loads(LOCAL_STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            seed_data = _default_seed_store()
            LOCAL_STORE_PATH.write_text(json.dumps(seed_data, indent=2, default=str), encoding="utf-8")
            return seed_data

    def _write_local(self, data: Dict[str, Dict[str, Any]]) -> None:
        LOCAL_STORE_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _get_firestore(self):
        if os.environ.get("SOMNOCARE_FORCE_LOCAL_DB", "").lower() in ("1", "true", "yes"):
            return None
        if not self._firestore_checked:
            self._firestore_checked = True
            try:
                from google.cloud import firestore  # type: ignore

                self._firestore_client = firestore.Client(project=self.project_id)
            except Exception:
                self._firestore_client = None
        return self._firestore_client

    def list_collection(self, collection: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        local_data = self._read_local()
        col_map = dict(local_data.get(collection, {}))

        fs = self._get_firestore()
        if fs is not None:
            try:
                col_ref = fs.collection(collection)
                docs = col_ref.stream()
                for d in docs:
                    item = d.to_dict()
                    if "timestamp" in item and hasattr(item["timestamp"], "isoformat"):
                        item["timestamp"] = item["timestamp"].isoformat()
                    col_map[d.id] = item
            except Exception:
                pass

        items = list(col_map.values())
        if user_id:
            items = [i for i in items if i.get("user_id") == user_id]
        return items

    def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        local_data = self._read_local()
        doc = local_data.get(collection, {}).get(doc_id)

        fs = self._get_firestore()
        if fs is not None:
            try:
                snap = fs.collection(collection).document(doc_id).get()
                if snap.exists:
                    fs_doc = snap.to_dict()
                    if fs_doc:
                        if "timestamp" in fs_doc and hasattr(fs_doc["timestamp"], "isoformat"):
                            fs_doc["timestamp"] = fs_doc["timestamp"].isoformat()
                        doc = fs_doc
            except Exception:
                pass
        return doc

    def set_document(self, collection: str, doc_id: str, payload: Dict[str, Any], merge: bool = True) -> Dict[str, Any]:
        local_data = self._read_local()
        col = local_data.setdefault(collection, {})
        if merge and doc_id in col and isinstance(col[doc_id], dict):
            merged = dict(col[doc_id])
            merged.update(payload)
            col[doc_id] = merged
        else:
            col[doc_id] = payload
        self._write_local(local_data)

        fs = self._get_firestore()
        if fs is not None:
            try:
                fs.collection(collection).document(doc_id).set(col[doc_id], merge=merge)
            except Exception:
                pass
        return col[doc_id]

    def reset_user_data(self, user_id: str = "default_user") -> Dict[str, Any]:
        """Reset or delete user data for privacy compliance."""
        seed = _default_seed_store()
        self._write_local(seed)
        return {"status": "success", "message": f"All personal wellness logs for {user_id} have been reset to clean defaults."}


_store: Optional[StorageBackend] = None


def get_store() -> StorageBackend:
    global _store
    if _store is None:
        _store = StorageBackend()
    return _store


# =====================================================================
# CLINICAL & WELLNESS CALCULATORS (STOP-BANG, ESS, BMI, SMOKING, CORR)
# =====================================================================

def compute_bmi_metrics(height_cm: float, weight_kg: float) -> Dict[str, Any]:
    if height_cm <= 0 or weight_kg <= 0:
        raise ValueError("Height and weight must be positive numbers.")
    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m * height_m), 1)
    if bmi < 18.5:
        category = "Underweight"
        osa_impact = "Low BMI-related airway load; focus on nasal patency and jaw/anatomical alignment."
    elif bmi < 25.0:
        category = "Healthy Weight"
        osa_impact = "Optimal weight range for upper airway patency and pharyngeal collapsibility."
    elif bmi < 30.0:
        category = "Overweight"
        osa_impact = "Moderate parapharyngeal fat pad load; a 5–10% weight reduction is clinically associated with a 15–25% reduction in AHI."
    elif bmi < 35.0:
        category = "Obesity (Class I)"
        osa_impact = "Elevated airway collapsibility; structured weight management and positional therapy strongly support CPAP efficacy."
    else:
        category = "Obesity (Class II+ / STOP-BANG Threshold >35)"
        osa_impact = "High STOP-BANG BMI risk factor (>35 kg/m²); consistent CPAP adherence and supervised metabolic/exercise plan recommended."
    return {
        "height_cm": round(height_cm, 1),
        "weight_kg": round(weight_kg, 1),
        "bmi": bmi,
        "bmi_category": category,
        "osa_clinical_context": osa_impact,
    }


def compute_pearson_correlation(xs: List[float], ys: List[float]) -> Optional[float]:
    n = min(len(xs), len(ys))
    if n < 3:
        return None
    xs = xs[:n]
    ys = ys[:n]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return 0.0
    return round(num / (den_x * den_y), 3)


def calculate_stop_bang_score(
    snoring: bool,
    tired: bool,
    observed_apnea: bool,
    high_blood_pressure: bool,
    bmi: float,
    age: int,
    neck_circumference_cm: float,
    sex: str,
) -> Dict[str, Any]:
    """Official Chung et al. (Anesthesiology / Chest) STOP-BANG 8-item OSA screening tool.
    Note: Presented strictly as wellness screening guidance, not a clinical diagnosis."""
    bmi_over_35 = float(bmi) > 35.0
    age_over_50 = int(age) > 50
    neck_over_40 = float(neck_circumference_cm) > 40.0
    is_male = str(sex).strip().lower() in ("male", "m")

    items = {
        "S_snoring_loud": bool(snoring),
        "T_tired_daytime": bool(tired),
        "O_observed_apnea": bool(observed_apnea),
        "P_blood_pressure": bool(high_blood_pressure),
        "B_bmi_over_35": bmi_over_35,
        "A_age_over_50": age_over_50,
        "N_neck_over_40cm": neck_over_40,
        "G_gender_male": is_male,
    }
    stop_subtotal = sum(
        1
        for k in ("S_snoring_loud", "T_tired_daytime", "O_observed_apnea", "P_blood_pressure")
        if items[k]
    )
    total_score = sum(1 for v in items.values() if v)

    # Official STOP-BANG two-step risk stratification (Chung et al., Chest 2016):
    # - 0 to 2: Low risk of moderate-to-severe OSA
    # - 3 to 4: Intermediate risk, UNLESS (STOP >= 2 AND (Male OR BMI > 35 OR Neck > 40cm)) -> High risk
    # - 5 to 8: High risk of moderate-to-severe OSA
    if total_score >= 5:
        risk_level = "High"
    elif total_score <= 2:
        risk_level = "Low"
    else:
        if stop_subtotal >= 2 and (is_male or bmi_over_35 or neck_over_40):
            risk_level = "High"
        else:
            risk_level = "Intermediate"

    active_drivers = []
    driver_labels = {
        "S_snoring_loud": "Loud habitual snoring",
        "T_tired_daytime": "Daytime fatigue / sleepiness",
        "O_observed_apnea": "Observed breathing pauses during sleep",
        "P_blood_pressure": "Hypertension (high blood pressure)",
        "B_bmi_over_35": f"BMI > 35 kg/m² (current: {bmi})",
        "A_age_over_50": f"Age > 50 years (current: {age})",
        "N_neck_over_40cm": f"Neck circumference > 40 cm (current: {neck_circumference_cm} cm)",
        "G_gender_male": "Male biological sex airway profile",
    }
    for k, active in items.items():
        if active:
            active_drivers.append(driver_labels[k])

    return {
        "score": total_score,
        "max_score": 8,
        "stop_subtotal": stop_subtotal,
        "risk_level": risk_level,
        "items": items,
        "active_drivers": active_drivers,
        "clinical_guidance": (
            "High wellness priority: Discuss an overnight polysomnography (sleep study) or CPAP pressure review with a board-certified sleep specialist."
            if risk_level == "High"
            else (
                "Moderate wellness priority: Track nightly snoring and AHI closely, practice positional & throat exercises, and consult a sleep physician if daytime fatigue persists."
                if risk_level == "Intermediate"
                else "Low screening score: Continue healthy sleep hygiene and regular wellness monitoring."
            )
        ),
        "disclaimer": "Wellness screening guidance only (Chung et al. STOP-BANG protocol) — not a medical diagnosis.",
    }


def calculate_ess_score(responses: List[int]) -> Dict[str, Any]:
    """Epworth Sleepiness Scale (Johns 1991): 8 situations rated 0–3 (total 0–24)."""
    padded = (list(responses) + [0] * 8)[:8]
    clamped = [max(0, min(3, int(x))) for x in padded]
    score = sum(clamped)
    if score <= 5:
        severity = "Lower Normal Daytime Sleepiness"
    elif score <= 10:
        severity = "Higher Normal Daytime Sleepiness"
    elif score <= 12:
        severity = "Mild Excessive Daytime Sleepiness"
    elif score <= 15:
        severity = "Moderate Excessive Daytime Sleepiness"
    else:
        severity = "Severe Excessive Daytime Sleepiness (Clinical Evaluation Advised)"

    drowsy_driving_flag = clamped[7] >= 2 or score >= 16
    return {
        "score": score,
        "max_score": 24,
        "item_scores": clamped,
        "severity": severity,
        "drowsy_driving_red_flag": drowsy_driving_flag,
        "guidance": (
            "URGENT SAFETY WARNING: Your score indicates significant daytime somnolence or risk while in traffic. Avoid driving when drowsy and consult your sleep physician promptly."
            if drowsy_driving_flag
            else "Your daytime alertness is within manageable bounds. Consistent CPAP usage ≥6 hours/night helps keep ESS below 10."
        ),
        "disclaimer": "Wellness guidance only — not a clinical diagnosis.",
    }


def evaluate_safety_red_flags(
    text_or_symptoms: str = "",
    ahi: Optional[float] = None,
    spo2_nadir: Optional[float] = None,
    drowsy_driving: bool = False,
    chest_pain: bool = False,
) -> Dict[str, Any]:
    """Deterministic clinical safety red-flag detector."""
    lower = (text_or_symptoms or "").lower()
    flags = []

    if chest_pain or any(w in lower for w in ("chest pain", "heart attack", "crushing chest", "severe shortness of breath", "lips turning blue", "cyanosis")):
        flags.append({
            "level": "EMERGENCY_911",
            "title": "Acute Cardiorespiratory Red Flag",
            "action": "Seek emergency medical care (Call 911 / Emergency Services immediately). Do not rely on coaching or adjust CPAP settings for acute chest pain or respiratory distress.",
        })

    if drowsy_driving or any(w in lower for w in ("fell asleep driving", "drowsy driving", "nodding off at the wheel", "microsleep while driving")):
        flags.append({
            "level": "URGENT_SAFETY",
            "title": "Drowsy Driving Hazard",
            "action": "Stop driving immediately if drowsy. Untreated or under-treated sleep apnea increases motor-vehicle crash risk 2.5x. Schedule an urgent review with your sleep physician.",
        })

    if ahi is not None and float(ahi) >= 30.0:
        flags.append({
            "level": "CLINICAL_ALERT",
            "title": f"Severe Residual AHI ({ahi} events/hr)",
            "action": "An AHI ≥ 30 indicates severe respiratory events. Check for major mask leaks or central apnea events and consult your sleep specialist before altering prescribed pressure.",
        })

    if spo2_nadir is not None and float(spo2_nadir) < 85.0:
        flags.append({
            "level": "CLINICAL_ALERT",
            "title": f"Significant Nocturnal Desaturation (SpO2 {spo2_nadir}%)",
            "action": "Oxygen saturation below 85% warrants prompt medical evaluation by a pulmonologist or sleep specialist.",
        })

    if any(w in lower for w in ("waking up choking", "gasping for air", "stopped breathing")):
        flags.append({
            "level": "PHYSICIAN_REVIEW",
            "title": "Nocturnal Choking / Observed Gasping",
            "action": "Nocturnal gasping is a cardinal indicator of airway collapse or suboptimal CPAP pressure/mask seal. Share your Weekly Doctor Report with a sleep specialist.",
        })

    return {
        "has_red_flag": len(flags) > 0,
        "red_flags": flags,
        "disclaimer": "SomnoCare provides wellness and adherence guidance only, not medical diagnosis or emergency care.",
    }
