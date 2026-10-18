# SomnoCare v2.0 — Intelligent CPAP Therapy, OSA Risk Screening & Lifestyle Command Center

SomnoCare is an end-to-end clinical-guidance AI companion and wellness platform designed to assist Obstructive Sleep Apnea (OSA) patients with Continuous Positive Airway Pressure (CPAP) therapy, validated risk screening, acoustic snoring analysis, and biomechanical exercise coaching. Built using the **Google Agent Development Kit (ADK)**, **FastAPI**, and **Gemini**, SomnoCare unites nightly adherence tracking with a comprehensive **Risk & Lifestyle Layer**.

---

![SomnoCare Demo](demo.gif)

---

## Key Capabilities & Features

### 1. Risk & Lifestyle Profile Layer (`patient_profile` Collection)
- **BMI & Weight Trajectory Tracking**: Computes Body Mass Index from height and weight, tracks historical trends, and calculates the **Pearson correlation ($r$) between weight change and AHI reduction**.
- **Smoking & Airway Recovery Tracker**: Logs smoking status, cigarettes/day, and quit date; computes a live **Smoke-Free Streak** and surfaces verified clinical evidence (e.g., *Wisconsin Sleep Cohort Study*, Wetter et al.) linking smoking-induced mucosal edema to OSA severity and morning mask dryness.
- **Official STOP-BANG Screening (0–8)**: Evaluates Snoring, Tiredness, Observed Apnea, Blood Pressure, BMI ($>35\text{ kg/m}^2$), Age ($>50$), Neck Circumference ($>40\text{ cm}$), and Biological Sex using the two-step Chung et al. clinical stratification (**Low / Intermediate / High**), showing transparent factor drivers.
- **Epworth Sleepiness Scale (ESS, 0–24)**: 8-situation daytime somnolence questionnaire with automatic **Drowsy Driving Red-Flag Detection**.

### 2. Acoustic Snoring Detector, Sleep Position & Nightly CPAP Logging (`sleep_therapy_logs`)
- **On-Device Web Audio FFT Snore Analyzer**: Processes sleep audio 100% locally in the browser (100–600 Hz palatal/pharyngeal band) to detect snore bursts, dB loudness, and snore minutes without uploading raw bedroom audio.
- **Positional & Evening Lifestyle Tracking**: Logs dominant sleep position (**Side vs. Back/Supine**), evening alcohol units, daily caffeine (mg), and morning dryness alongside CPAP usage hours, AHI, and mask leak rate (L/min).
- **Dual Interactive Clinical Charts**: Visualizes **14-Night AHI vs. Snoring Score & Usage Hours** and **Body Weight / BMI vs. AHI Trajectory**.

### 3. OpenCV / MediaPipe Pose Exercise, Yoga & Oropharyngeal Coach (`exercise_logs`)
- **Real-Time Joint-Angle Biomechanics**: Browser-side skeletal tracking and interactive simulation with automatic rep counting and live posture cues (e.g., *"Raise your hips higher"*, *"Depth reached <100°"*).
- **Age-Adapted Intensity**: Dynamically computes target heart rate zones ($220 - \text{Age}$) and recommends age-appropriate exercises.
- **5 Curated OSA & Wellness Routines**:
  1. **Bodyweight Squat** (Knee flexion angle $<100^\circ$)
  2. **Incline / Standard Push-Up** (Elbow flexion angle)
  3. **Yoga: Setu Bandhasana (Bridge Pose)** (Hip extension & thoracic airway expansion)
  4. **Yoga: Cat-Cow (Marjaryasana-Bitilasana)** (Cervical & thoracic mobility)
  5. **Supportive Oropharyngeal (Throat) Exercises** (Tongue slide, palatal suction, soft palate lift, and buccal resistance based on Guimarães et al., *AJRCCM*, presented as supportive care alongside CPAP).

### 4. Lifestyle, Pranayama Breathing, Diet & Ambient Climate/AQI Tuner
- **Guided Pranayama & Box Breathing Pacer**: Animated 4-7-8 parasympathetic wind-down and 4-4-4-4 Navy Box Breathing timer to ease mask claustrophobia and lower bedtime heart rate.
- **Sleep-Friendly Meal & Photo Logger**: Logs meal timing and estimates calories (with optional **Gemini Multimodal Photo Analysis**), warning when late ($<2\text{h}$ before bed) or spicy meals increase gastroesophageal reflux and airway edema.
- **Ambient Weather, Humidity & Air Quality (AQI / PM2.5)**: Extends the **Open-Meteo Weather & Air Quality APIs** to tune CPAP humidifier chamber levels, prevent tube condensation ("rainout"), and alert users when elevated PM2.5/AQI requires hypoallergenic filter checks and pre-bedtime saline nasal rinses.

### 5. AI Upgrades, Care Team & Clinical Safety Guardrails
- **Multilingual Hands-Free Voice Logging**: Dictate nightly logs in **English, Hindi, Kannada, or Telugu** (e.g., *"Log 7.5 hours, AHI 2.1, snoring score 2, side sleeping"*) parsed into structured Firestore entries by Gemini.
- **Weekly AI Insight Summary**: Automatically synthesizes **What Improved**, **What Slipped**, and **One High-Impact Thing to Try**, plus **Gamification Badges** and **Smart DME Supply Replacement Reminders**.
- **Weekly Doctor Report PDF Generator**: One-click clinical PDF (`/api/doctor-report.pdf` powered by ReportLab) containing anthropometrics, STOP-BANG/ESS scores, 30-day Medicare CMS compliance, correlations, and 10-day logs ready for a sleep physician.
- **Caregiver / Bed-Partner View & Sleep Study PDF Extractor**: Partner observation form for witnessed apnea pauses (`partner_observations`) and a Polysomnography (PSG) PDF parser (`/api/upload-sleep-study`) that extracts diagnostic AHI and $\text{SpO}_2$ nadir.
- **Find Nearby Sleep Clinics**: Curated sleep lab directory with direct Google Maps links.
- **Deterministic Red-Flag Safety Rules**: Urgent alerts for chest pain, acute dyspnea, drowsy driving, severe residual AHI ($\ge 30$), or $\text{SpO}_2 < 85\%$, always framing outputs as *"wellness guidance, not a medical diagnosis"*.

---

## Architecture & Wired Services

| Capability | Component / Service | Implementation |
| :--- | :--- | :--- |
| **Foundation Model** | Gemini 3.8 Flash / Gemini 2.5 Flash | Core agent reasoning, tool calling, voice & PDF parsing |
| **Image Model** | Gemini 3.1 Flash Lite Image (`gemini-3.1-flash-lite-image`) | On-demand CPAP equipment & mask fit diagrams |
| **Long-Term Memory** | Vertex AI Memory Bank | `PreloadMemoryTool` + post-session memory callbacks |
| **Database** | Google Cloud Firestore + Local Hybrid Mirror | `patient_profile`, `sleep_therapy_logs`, `cpap_supplies`, `exercise_logs`, `meal_logs`, `partner_observations` |
| **Computer Vision & Audio** | MediaPipe Pose / Canvas + Web Audio FFT | Client-side joint-angle rep counter & acoustic snore detector |
| **Physician Reporting** | ReportLab PDF Engine | Automated `/api/doctor-report.pdf` clinical summary |
| **UI Protocol** | Modern Tailwind/Chart.js SPA + A2UI v0.8 | Interactive 7-tab command center + structured A2UI cards |

---

## Project Structure

```
somnocare/
├── app/
│   ├── agent.py               # Root ADK agent, 12 clinical/lifestyle tools, callbacks & sandbox wiring
│   ├── wellness_hub.py        # Hybrid Firestore/local storage & STOP-BANG, ESS, BMI, correlation calculators
│   ├── api_routes.py          # FastAPI REST & multimodal endpoints (/api/dashboard, /api/doctor-report.pdf, etc.)
│   ├── a2ui_utils.py          # A2UI v0.8 response formatting callback
│   ├── fast_api_app.py        # ADK FastAPI serving app, wellness routes & A2A routing
│   └── app_utils/             # Services registry and session management
├── frontend/
│   ├── main.py                # Unified FastAPI server hosting the SPA, REST APIs, and Agent chat
│   ├── static/
│   │   ├── index.html         # 7-tab responsive Command Center UI
│   │   ├── app.css            # Glassmorphic dark clinical theme & A2UI styles
│   │   └── app.js             # Chart.js trends, Web Audio snore FFT, Pose skeleton coach & voice logger
│   └── requirements.txt       # Frontend & API dependencies
├── seed_firestore.py          # Seeds CPAP supplies, patient profile, and 14 nights of clinical logs
└── tests/unit/test_dummy.py   # Unit & API test suite covering calculators, tools, PDF export & red flags
```

---

## Quick Start (Local Development)

### 1. Configure Environment
Copy `.env.example` to `.env` and set either your `GEMINI_API_KEY` (Google AI Studio) or Google Cloud Vertex AI project credentials:
```bash
cp .env.example .env
```

### 2. Run the Full-Stack Command Center
```bash
pip install -r frontend/requirements.txt
python frontend/main.py
```
Open **http://localhost:8080** in your browser to explore:
- **Risk & Trend Command** (KPIs, AHI vs. Snoring chart, Weight vs. AHI chart, Weekly AI Insights, Badges, Supply Reminders)
- **Profile, STOP-BANG & ESS** (BMI calculator, Smoke-Free Streak, interactive STOP-BANG & Epworth questionnaires)
- **Sleep, Snore & Voice Log** (On-device Web Audio snore visualizer, multilingual voice logging, positional/alcohol log)
- **OpenCV Pose & Yoga Coach** (Real-time joint-angle rep counter for Squats, Push-Ups, Bridge Pose, Cat-Cow, and Oropharyngeal Throat exercises)
- **Breathing, Diet & Climate** (Animated 4-7-8 Pranayama timer, Meal & Photo logger, live Open-Meteo Humidity + AQI tuner)
- **Care Team, PDF & Clinics** (Downloadable Doctor PDF Report, Partner Observation log, Sleep Study PDF extractor, Sleep Clinic finder)
- **SomnoCare Gemini Agent** (Conversational AI assistant with A2UI v0.8 rich card rendering)

### 3. Run Unit & API Tests
```bash
python -m unittest tests/unit/test_dummy.py -v
```
