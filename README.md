# 🫁 SomnoCare — Simplified AI CPAP Adherence, Sleep Apnea Screening & Lifestyle Companion

[![Live Prototype](https://img.shields.io/badge/Live_Prototype-somnocare--ai.netlify.app-0284c7?style=for-the-badge&logo=googlecloud)](https://somnocare-ai.netlify.app)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Bhuvanani14%2Fsomnocare-0f172a?style=for-the-badge&logo=github)](https://github.com/Bhuvanani14/somnocare)
[![Built with Google ADK & Gemini 2.5 Flash](https://img.shields.io/badge/Google_ADK-Gemini_2.5_Flash-10b981?style=for-the-badge&logo=google)](https://google.github.io/adk-docs/)
[![Unit Tests](https://img.shields.io/badge/Tests-8%2F8_Passing-059669?style=for-the-badge)](./tests/unit/test_dummy.py)

> **Live Deployed Prototype:** **[https://somnocare-ai.netlify.app](https://somnocare-ai.netlify.app)**  
> **GitHub Repository:** **[https://github.com/Bhuvanani14/somnocare](https://github.com/Bhuvanani14/somnocare)**  
> **Prescribed Pitch Deck (`.pptx`):** [`submission/SomnoCare_Pitch_Deck.pptx`](./submission/SomnoCare_Pitch_Deck.pptx)  
> **Video Demonstration (3–4 Min):** [`submission/SomnoCare_Demo_Video.webm`](./submission/SomnoCare_Demo_Video.webm)  
> **Submission Write-Up:** [`submission/SUBMISSION_DETAILS.md`](./submission/SUBMISSION_DETAILS.md)

---

## 🌟 Brief Description (Firebase, Firestore, Cloud Run & Gemini)

**SomnoCare** transforms CPAP therapy management and Obstructive Sleep Apnea (OSA) risk screening into an **effortless, plain-language 5-step experience** built for everyday patients and older adults. It features **Light Mode (default) and Dark Mode**, **PBKDF2-SHA256 authentication**, **personalized account onboarding**, a **4-digit Privacy PIN lock screen**, and **100% on-device camera/microphone privacy**.

### How SomnoCare Leverages Google Cloud & Gemini:
- **Gemini 2.5 Flash & Google Agent Development Kit (`google-adk`, `google-genai`)**:
  - Powers `somnocare_agent` ([`app/agent.py`](./app/agent.py)) with **12 specialized clinical tools** (`get_profile`, `update_profile`, `evaluate_osa_risk_and_screening`, `calculate_cms_adherence_compliance`, `log_sleep_therapy_entry`, `log_exercise_or_yoga_session`, `get_local_weather_for_humidifier`, `find_nearby_sleep_clinics`, `generate_weekly_wellness_insights`, etc.).
  - Performs **multilingual natural-language voice sleep logging** (English, Hindi, Kannada, Telugu), **Sleep Study PDF/OCR extraction** (Diagnostic AHI & $\text{SpO}_2$ nadir), and renders structured **A2UI v0.8 visual cards** in chat.
  - Enforces a deterministic **Red-Flag Clinical Safety Guard** that halts coaching and escalates to emergency/physician care if chest pain, syncope, drowsy driving, or $\text{AHI} \ge 30$ is detected.
- **Firebase & Google Cloud Firestore (`google-cloud-firestore`)**:
  - Persists longitudinal patient records across seven collections (`patient_profile`, `sleep_logs`, `exercise_logs`, `meal_logs`, `partner_observations`, `users_auth`, `security_audit_logs`) with a zero-downtime hybrid JSON fallback ([`app/wellness_hub.py`](./app/wellness_hub.py)) and an **ADK Session Memory Bank** ([`app/memory_bank.py`](./app/memory_bank.py)).
- **Google Cloud Run (`Dockerfile`, `deploy_cloud_run.sh`)**:
  - Stateless, containerized FastAPI + Uvicorn microservice serving the REST APIs, ADK Agent, ReportLab Physician PDF generator (`/api/doctor-report.pdf`), and simplified Light/Dark SPA on `$PORT=8080`.

---

## ✨ Key Features (Simplified 5-Step Interface)

| Step | Feature Area | What It Does |
|---|---|---|
| **Login & Security** | **Authentication, Personalization & PIN Lock** | Sign in (`arjun@somnocare.ai` / `SomnoCare@2026`), 1-Click Demo Login, Create Personalized Account, 4-Digit Privacy PIN Lock (`1404`), Granular Camera/Mic Consents & Security Audit Log. |
| **Step 1** | **My Daily Summary (Light & Dark Mode)** | 5 plain-language health cards: **Insurance 4h/70% Status**, **Breathing Events (AHI)**, **BMI & Weight**, **STOP-BANG Risk**, and **Smoke-Free Streak**, plus 14-day trend charts & gamified badges. |
| **Step 2** | **Log Sleep, Snoring & Voice** | **On-Device WebAudio FFT Snoring Detector** (80–350 Hz palatal band), **Multilingual Voice Logging** (EN/HI/KN/TE), and manual logging with sleep position (`side` vs. `back`) & alcohol/caffeine tracking. |
| **Step 3** | **My Body, BMI, Smoking & Risk Check** | Tracks **Age**, **Height/Weight**, **BMI trend**, **Neck Circumference**, **Smoking Quit Streak**, official 8-item **STOP-BANG** questionnaire, and 8-item **Epworth Sleepiness Scale (ESS)**. |
| **Step 4** | **OpenCV / MediaPipe Exercise, Yoga & Breathing** | Real-time 2D skeletal pose tracking & joint-angle rep counting (`calcAngleDegrees`) for **Bodyweight Squats**, **Push-ups**, **Yoga Bridge (*Setu Bandhasana*)**, **Cat-Cow**, and **Oropharyngeal Throat/Tongue Exercises**, plus **4-7-8 Pranayama** & **Open-Meteo Weather/AQI CPAP Humidifier Tuner**. |
| **Step 5** | **Ask AI Coach, Doctor PDF & Security** | Conversational **Gemini 2.5 Flash Coach** with **A2UI v0.8 cards**, **Sleep Study PDF Extractor**, **Partner Observation Log**, **Nearby Sleep Clinics**, and **1-Click Physician PDF Report**. |

---

## 🚀 Quick Start (Local & Cloud Run)

### 1. Run Locally
```bash
pip install fastapi uvicorn google-genai google-adk google-cloud-firestore reportlab PyPDF2 python-multipart python-dotenv httpx
export PORT=8085
python frontend/main.py
```
Open **[http://localhost:8085](http://localhost:8085)** in your browser.
- **Demo Account:** `arjun@somnocare.ai` / `SomnoCare@2026` (or click **Instant 1-Click Demo Login**)
- **Default 4-Digit Privacy PIN:** `1404`

### 2. Run Unit & API Verification Suite
```bash
python -m unittest tests/unit/test_dummy.py -v
```

### 3. Deploy to Google Cloud Run
```bash
chmod +x deploy_cloud_run.sh
./deploy_cloud_run.sh
```
Or directly via `gcloud`:
```bash
gcloud run deploy somnocare --source . --region us-central1 --allow-unauthenticated --port 8080
```
