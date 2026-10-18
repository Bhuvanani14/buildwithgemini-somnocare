# 🏆 Gen AI Academy APAC Edition — Prototype Submission Details

## 1. Key Submission Links & Assets

| Deliverable | Link / File Location | Status |
|---|---|---|
| **Deployed Prototype Link** | **[https://somnocare-ai.netlify.app](https://somnocare-ai.netlify.app)** *(Live 24/7 Public Cloud Deployment)* | ✅ Live & Verified (HTTP 200) |
| **GitHub Repository** | **[https://github.com/Bhuvanani14/somnocare](https://github.com/Bhuvanani14/somnocare)** *(Renamed to `somnocare`)* | ✅ Public & Accessible |
| **Prescribed Pitch Deck** | [`submission/SomnoCare_Pitch_Deck.pptx`](../SomnoCare_Pitch_Deck.pptx) *(Built on the official 11-slide Gen AI Academy template)* | ✅ Ready for Upload |
| **Video Demonstration (3–4 Min)** | [`submission/SomnoCare_Demo_Video.webm`](./SomnoCare_Demo_Video.webm) *(3m 18s / 198s end-to-end live walkthrough)* | ✅ Strictly within 3:00–4:00 window |
| **Cloud Run Deployment Script** | [`Dockerfile`](../Dockerfile) & [`deploy_cloud_run.sh`](../deploy_cloud_run.sh) | ✅ Production-Ready |

---

## 2. Brief Description of What We Built (Copy-Paste Ready for Submission Form)

**SomnoCare** is an intelligent, everyday-friendly **CPAP Adherence, Obstructive Sleep Apnea (OSA) Risk Screening, Snoring DSP & Computer-Vision Exercise Companion** designed so any layperson or older adult can easily screen their sleep apnea risk, stay compliant with CPAP therapy, and strengthen their upper airway.

While nearly 1 billion adults globally suffer from Obstructive Sleep Apnea, up to **50% of prescribed CPAP patients abandon therapy within the first year** due to mask leaks, nasal dryness, intimidating clinical charts, and unaddressed lifestyle triggers (BMI, smoking, supine sleeping, and low airway muscle tone). SomnoCare bridges this gap through a clean, uncluttered **5-Step Light & Dark Mode interface** secured with **PBKDF2-HMAC-SHA256 authentication, personalized patient onboarding, a 4-digit Privacy PIN lock screen, and a real-time Security Audit Log**.

### How We Leverage Google Cloud, Firebase, Firestore, Cloud Run & Gemini:

1. **Google Agent Development Kit (ADK) & Gemini 2.5 Flash (`google-adk` & `google-genai`)**:
   - At the core of SomnoCare is `somnocare_agent` (`app/agent.py`), an autonomous clinical & lifestyle coach powered by **Gemini 2.5 Flash** with **12 specialized ADK tools**:
     - `get_profile` & `update_profile`: Manages patient **Age**, **Height/Weight**, automatic **BMI calculation & trend tracking**, **Neck Circumference**, **Hypertension**, and **Smoking status / Smoke-Free Streak**.
     - `evaluate_osa_risk_and_screening`: Computes the official 8-item **STOP-BANG** OSA risk score (Chung et al.) and the 8-item **Epworth Sleepiness Scale (ESS)** (Johns) with automated drowsy-driving red-flag detection.
     - `calculate_cms_adherence_compliance`: Audits the **CMS 4 hours/night × 70% of nights** insurance rule and calculates live **Pearson correlation coefficients ($r$)** linking **Weight/BMI change $\leftrightarrow$ AHI ($r = +0.94$)** and **Snoring $\leftrightarrow$ AHI ($r = +0.97$)**.
     - `log_sleep_therapy_entry` & `log_exercise_or_yoga_session`: Logs nightly CPAP usage, AHI, mask leak (L/min), snoring score (0–10), sleep position (`back` vs. `side`), evening alcohol/caffeine, and exercise repetitions.
     - **Multimodal Gemini Capabilities**: Parses natural-language voice sleep logs across **English, Hindi, Kannada, and Telugu** (`/api/voice-parse`), extracts Diagnostic AHI and $\text{SpO}_2$ nadir from uploaded **Polysomnography (PSG) Sleep Study PDFs** (`/api/upload-sleep-study`), and renders interactive **A2UI v0.8 rich clinical cards** inside the chat interface.
     - **Deterministic Red-Flag Safety Guard**: Automatically intercepts emergency symptoms (chest pain, syncope, drowsy driving, or $\text{AHI} \ge 30$) before coaching and directs the patient to urgent medical care.

2. **Firebase & Google Cloud Firestore (`google-cloud-firestore`)**:
   - SomnoCare persists structured longitudinal telemetry across seven Firestore collections (`patient_profile`, `sleep_logs`, `exercise_logs`, `meal_logs`, `partner_observations`, `users_auth`, and `security_audit_logs`), backed by a zero-downtime hybrid JSON synchronization layer (`StorageBackend` in `app/wellness_hub.py`) and an **ADK Session Memory Bank** (`app/memory_bank.py`) so the agent remembers every patient's mask model, pressure settings, BMI trajectory, and smoke-free streak across sessions.

3. **Google Cloud Run (`Dockerfile` & `deploy_cloud_run.sh`)**:
   - Packaged as a stateless, autoscaling **Cloud Run** container (`python:3.12-slim` + `uvicorn` on `$PORT=8080`) serving the unified FastAPI REST API, ADK Agent endpoint, ReportLab Physician PDF generator (`/api/doctor-report.pdf`), and simplified Light/Dark Mode SPA with hardened HTTP security headers (`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`).

4. **Privacy-Preserving On-Device Edge AI (MediaPipe / OpenCV Pose & WebAudio FFT)**:
   - **Computer-Vision Exercise, Yoga & Throat Coach**: Uses **MediaPipe Pose / OpenCV 2D skeletal landmark geometry** in the browser to compute real-time joint angles (`calcAngleDegrees`) and count repetitions for **Bodyweight Squats**, **Push-ups**, **Yoga Bridge Pose (*Setu Bandhasana*)**, **Cat-Cow (*Marjaryasana*)**, and **Oropharyngeal Throat/Tongue Exercises** (genioglossus & soft-palate myofunctional toning) plus a guided **4-7-8 Pranayama breathing pacer**.
   - **Acoustic Snoring Detector**: Uses an on-device **WebAudio API Fast Fourier Transform (FFT)** analyzer targeting the **80–350 Hz palatal vibration band** to quantify snore events, snore minutes, and peak decibels ($\text{dB}$) locally in the browser—ensuring raw bedroom audio and webcam video never leave the patient's device.
