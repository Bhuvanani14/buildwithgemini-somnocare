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
"""
Comprehensive Unit & API Verification Suite for SomnoCare v2.0.
Can be run via `pytest` or directly via `python -m unittest tests/unit/test_dummy.py`.
"""

import os
import unittest

os.environ["SOMNOCARE_FORCE_LOCAL_DB"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.agent import (  # noqa: E402
    calculate_cms_adherence_compliance,
    evaluate_osa_risk_and_screening,
    find_nearby_sleep_clinics,
    generate_weekly_wellness_insights,
    get_profile,
    get_sleep_therapy_history,
    log_exercise_or_yoga_session,
    log_sleep_therapy_entry,
    search_cpap_supplies,
    update_profile,
)
from app.wellness_hub import (  # noqa: E402
    calculate_ess_score,
    calculate_stop_bang_score,
    compute_bmi_metrics,
    compute_pearson_correlation,
    evaluate_safety_red_flags,
    get_store,
)
from frontend.main import app as fastapi_app  # noqa: E402


class TestSomnoCareSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        get_store().reset_user_data("default_user")
        cls.client = TestClient(fastapi_app)

    def test_bmi_calculator(self) -> None:
        res = compute_bmi_metrics(height_cm=175.0, weight_kg=90.3)
        self.assertAlmostEqual(res["bmi"], 29.5, places=1)
        self.assertEqual(res["bmi_category"], "Overweight")

    def test_stop_bang_official_thresholds(self) -> None:
        # High risk >= 5
        high = calculate_stop_bang_score(
            snoring=True,
            tired=True,
            observed_apnea=True,
            high_blood_pressure=True,
            bmi=36.0,
            age=55,
            neck_circumference_cm=42.0,
            sex="male",
        )
        self.assertEqual(high["score"], 8)
        self.assertEqual(high["risk_level"], "High")

        # Low risk <= 2
        low = calculate_stop_bang_score(
            snoring=False,
            tired=True,
            observed_apnea=False,
            high_blood_pressure=False,
            bmi=23.0,
            age=30,
            neck_circumference_cm=36.0,
            sex="female",
        )
        self.assertEqual(low["score"], 1)
        self.assertEqual(low["risk_level"], "Low")

    def test_epworth_sleepiness_scale_and_drowsy_driving(self) -> None:
        normal = calculate_ess_score([1, 1, 1, 1, 1, 0, 1, 0])
        self.assertEqual(normal["score"], 6)
        self.assertFalse(normal["drowsy_driving_red_flag"])

        severe = calculate_ess_score([3, 3, 2, 3, 3, 1, 2, 2])
        self.assertEqual(severe["score"], 19)
        self.assertTrue(severe["drowsy_driving_red_flag"])

    def test_red_flag_safety_rules(self) -> None:
        emergency = evaluate_safety_red_flags(text_or_symptoms="I have crushing chest pain and shortness of breath")
        self.assertTrue(emergency["has_red_flag"])
        self.assertEqual(emergency["red_flags"][0]["level"], "EMERGENCY_911")

        high_ahi = evaluate_safety_red_flags(ahi=34.5)
        self.assertTrue(high_ahi["has_red_flag"])
        self.assertEqual(high_ahi["red_flags"][0]["level"], "CLINICAL_ALERT")

    def test_profile_and_compliance_tools(self) -> None:
        prof = get_profile("default_user")
        self.assertIn("bmi", prof)
        self.assertIn("stop_bang", prof)

        upd = update_profile(user_id="default_user", weight_kg=89.5, age=53)
        self.assertEqual(upd["status"], "success")
        self.assertEqual(upd["profile"]["age"], 53)

        comp = calculate_cms_adherence_compliance("default_user")
        self.assertTrue(comp["is_compliant"])
        self.assertIsNotNone(comp["weight_to_ahi_correlation_r"])
        self.assertIsNotNone(comp["snoring_to_ahi_correlation_r"])

    def test_sleep_and_exercise_logging_tools(self) -> None:
        log_res = log_sleep_therapy_entry(
            date="2026-10-18",
            usage_hours=7.5,
            ahi=2.0,
            mask_leak_rate=3.8,
            restedness_score=9,
            snoring_score=1,
            sleep_position="side",
            alcohol_units=0,
            weight_kg=89.5,
            notes="Restful side-sleeping session",
        )
        self.assertEqual(log_res["status"], "success")

        ex_res = log_exercise_or_yoga_session(
            exercise_type="oropharyngeal_tongue_slide",
            reps=20,
            duration_seconds=240,
            form_accuracy_score=96.0,
        )
        self.assertEqual(ex_res["status"], "success")

    def test_fastapi_endpoints_and_doctor_pdf(self) -> None:
        r_dash = self.client.get("/api/dashboard")
        self.assertEqual(r_dash.status_code, 200)
        body = r_dash.json()
        self.assertEqual(body["status"], "success")
        self.assertTrue(len(body["sleep_logs"]) >= 10)

        r_voice = self.client.post(
            "/api/voice-parse",
            json={"transcript": "Log 7.4 hours, AHI 2.1, snoring score 2, side sleeping", "auto_save": True},
        )
        self.assertEqual(r_voice.status_code, 200)
        self.assertEqual(r_voice.json()["status"], "success")

        r_pdf = self.client.get("/api/doctor-report.pdf")
        self.assertEqual(r_pdf.status_code, 200)
        self.assertEqual(r_pdf.headers["content-type"], "application/pdf")
        self.assertTrue(r_pdf.content.startswith(b"%PDF"))

        r_chat = self.client.post("/chat", json={"message": "I have severe chest pain right now"})
        self.assertEqual(r_chat.status_code, 200)
        chat_data = r_chat.json()
        self.assertTrue(chat_data.get("safety_alert", {}).get("has_red_flag"))

    def test_authentication_and_security_controls(self) -> None:
        r_login = self.client.post(
            "/api/auth/login",
            json={"email": "demo@somnocare.ai", "password": "SomnoCare2026!"},
        )
        self.assertEqual(r_login.status_code, 200)
        login_data = r_login.json()
        self.assertEqual(login_data["status"], "success")
        self.assertIn("token", login_data)
        self.assertEqual(r_login.headers.get("X-Content-Type-Options"), "nosniff")

        r_pin = self.client.post(
            "/api/auth/verify-pin",
            json={"user_id": "default_user", "pin": "1404"},
        )
        self.assertEqual(r_pin.status_code, 200)
        self.assertEqual(r_pin.json()["status"], "success")

        r_reg = self.client.post(
            "/api/auth/register",
            json={
                "name": "Test Patient",
                "email": "patient.test@somnocare.ai",
                "password": "SafePassword123!",
                "age": 48,
                "height_cm": 172.0,
                "weight_kg": 84.0,
                "pin": "2580",
            },
        )
        self.assertEqual(r_reg.status_code, 200)
        self.assertEqual(r_reg.json()["status"], "success")

        r_audit = self.client.get("/api/security/audit")
        self.assertEqual(r_audit.status_code, 200)
        self.assertTrue(len(r_audit.json().get("logs", [])) >= 2)


def test_dummy() -> None:
    """Backwards-compatible pytest entry point."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSomnoCareSuite)
    result = unittest.TextTestRunner().run(suite)
    assert result.wasSuccessful()


if __name__ == "__main__":
    unittest.main()

