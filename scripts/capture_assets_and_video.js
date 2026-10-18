/**
 * Capture high-resolution prototype snapshots AND record a 3-to-4 minute (205s)
 * live working video demonstration of SomnoCare v2.0.
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:8085';
const OUT_DIR = path.resolve(__dirname, '..', 'submission');
const SHOT_DIR = path.join(OUT_DIR, 'screenshots');

fs.mkdirSync(SHOT_DIR, { recursive: true });

async function injectCaptionBanner(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-caption-banner')) return;
    const banner = document.createElement('div');
    banner.id = 'demo-caption-banner';
    banner.style.cssText = `
      position: fixed;
      bottom: 18px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 99999;
      background: rgba(15, 23, 42, 0.94);
      color: #f8fafc;
      border: 2px solid #0284c7;
      border-radius: 16px;
      padding: 12px 24px;
      font-family: Inter, system-ui, sans-serif;
      font-size: 16px;
      font-weight: 700;
      box-shadow: 0 20px 45px rgba(2, 6, 23, 0.55);
      max-width: 86vw;
      text-align: center;
      letter-spacing: 0.01em;
    `;
    banner.innerHTML = `<span style="color:#38bdf8;margin-right:8px;">● LIVE DEMO</span><span id="demo-caption-text">SomnoCare — CPAP, Sleep Apnea Screening & Lifestyle Coach</span>`;
    document.body.appendChild(banner);
  });
}

async function setCaption(page, stepTitle, subtitle, waitMs) {
  await injectCaptionBanner(page);
  await page.evaluate(({ stepTitle, subtitle }) => {
    const el = document.getElementById('demo-caption-text');
    if (el) {
      el.innerHTML = `<strong style="color:#38bdf8">${stepTitle}:</strong> ${subtitle}`;
    }
  }, { stepTitle, subtitle });
  await page.waitForTimeout(waitMs);
}

(async () => {
  console.log('Launching Browser for Screenshots + 3.5-Minute Video Recording...');
  let browser;
  try {
    browser = await chromium.launch({ channel: 'msedge', headless: true });
  } catch (e) {
    browser = await chromium.launch({ channel: 'chrome', headless: true });
  }

  // 1. First pass: Quick high-resolution clean screenshots for Pitch Deck & README
  const shotContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const shotPage = await shotContext.newPage();
  await shotPage.goto(BASE_URL, { waitUntil: 'networkidle' });
  await shotPage.waitForTimeout(1200);

  // Screenshot 1: Login & Personalization Gateway (Light Mode)
  await shotPage.screenshot({ path: path.join(SHOT_DIR, '01_login_gateway_light.png') });

  // Click Demo Sign-In
  await shotPage.click('#login-form button[type="submit"]');
  await shotPage.waitForTimeout(1200);

  // Screenshot 2: Step 1 Daily Summary in Light Mode
  await shotPage.screenshot({ path: path.join(SHOT_DIR, '02_daily_summary_light.png') });

  // Screenshot 3: Step 1 Daily Summary in Dark Mode
  await shotPage.click('#btn-theme-toggle');
  await shotPage.waitForTimeout(800);
  await shotPage.screenshot({ path: path.join(SHOT_DIR, '03_daily_summary_dark.png') });

  // Switch back to Light Mode
  await shotPage.click('#btn-theme-toggle');
  await shotPage.waitForTimeout(600);

  // Screenshot 4: Step 2 Log Sleep & Acoustic Snoring Detector
  await shotPage.click('button[data-tab="snoring"]');
  await shotPage.waitForTimeout(600);
  await shotPage.click('button[onclick="simulateSnoreBurst()"]');
  await shotPage.waitForTimeout(1200);
  await shotPage.screenshot({ path: path.join(SHOT_DIR, '04_snoring_and_voice_log.png') });

  // Screenshot 5: Step 3 Body, BMI, Smoking & STOP-BANG Risk Check
  await shotPage.click('button[data-tab="profile"]');
  await shotPage.waitForTimeout(900);
  await shotPage.screenshot({ path: path.join(SHOT_DIR, '05_bmi_stopbang_screening.png') });

  // Screenshot 6: Step 4 OpenCV / MediaPipe Pose Exercise & Yoga Coach
  await shotPage.click('button[data-tab="exercise"]');
  await shotPage.waitForTimeout(600);
  await shotPage.click('#btn-sim-pose');
  await shotPage.waitForTimeout(1400);
  await shotPage.screenshot({ path: path.join(SHOT_DIR, '06_opencv_pose_yoga_coach.png') });

  // Screenshot 7: Step 5 Ask AI Coach (A2UI) & Security Center
  await shotPage.click('button[data-tab="agent"]');
  await shotPage.waitForTimeout(900);
  await shotPage.screenshot({ path: path.join(SHOT_DIR, '07_ai_coach_and_security.png') });

  await shotContext.close();
  console.log('Saved 7 high-res screenshots to submission/screenshots/.');

  // 2. Second pass: Record the 3-to-4 minute (target ~198 seconds = 3m 18s) Live Video Demo
  const videoDir = path.join(OUT_DIR, 'video_raw');
  fs.mkdirSync(videoDir, { recursive: true });

  const vidContext = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: videoDir, size: { width: 1280, height: 720 } },
  });
  const page = await vidContext.newPage();
  const startWall = Date.now();

  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await setCaption(
    page,
    'Welcome to SomnoCare (0:00 - 0:25)',
    'Simplified CPAP Adherence, Sleep Apnea Screening (STOP-BANG/ESS) & Lifestyle Companion built on Google Cloud & Gemini 2.5 Flash',
    9000
  );

  // Show Registration Tab on Login Modal
  await page.click('#tab-auth-register');
  await setCaption(
    page,
    'Personalized Onboarding & Security',
    'New patients can create a personalized account with Age, Height, Weight & a 4-Digit Privacy PIN (PBKDF2-HMAC-SHA256 hashed)',
    8000
  );

  await page.click('#tab-auth-login');
  await setCaption(
    page,
    'Secure Sign-In & Brute-Force Protection',
    'Signing in as patient Arjun Mehta (Age 52) with signed HMAC-SHA256 session tokens and Firestore audit logging',
    7000
  );

  await page.click('#login-form button[type="submit"]');
  await setCaption(
    page,
    'Step 1: Easy Daily Summary (Light Mode Default)',
    'Designed for everyday simplicity — 5 plain-language health cards: Insurance 4h/70% Status, AHI Events/hr, BMI, STOP-BANG & Smoke-Free Streak',
    11000
  );

  // Toggle Dark Mode and back to Light Mode
  await page.click('#btn-theme-toggle');
  await setCaption(
    page,
    '1-Click Light & Dark Mode Accessibility',
    'High-contrast Dark Mode for bedroom/nighttime CPAP checks, and bright Light Mode for daytime readability',
    8000
  );

  await page.click('#btn-theme-toggle');
  await setCaption(
    page,
    'Clinical Trend Analytics (14-Day History)',
    'Tracks CPAP Hours & AHI vs. Snoring Score, plus Weight & BMI drop correlated with AHI reduction (Pearson r = +0.94)',
    10000
  );

  await page.evaluate(() => window.scrollBy({ top: 420, behavior: 'smooth' }));
  await setCaption(
    page,
    'Positional Therapy & Gamified Streaks',
    'Compares Back-Sleeping AHI (6.1/hr) vs. Side-Sleeping AHI (3.3/hr) alongside unlocked adherence & smoke-free badges',
    10000
  );
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));

  // Test 4-Digit PIN Lock Screen
  await page.click('button[onclick="lockSession()"]');
  await setCaption(
    page,
    '4-Digit Privacy PIN Lock Screen',
    'Protects sensitive sleep & medical records when sharing a phone or tablet with family members',
    7000
  );
  await page.fill('#pin-unlock-input', '1404');
  await page.waitForTimeout(1500);
  await page.click('button[onclick="unlockWithPin()"]');
  await setCaption(
    page,
    'PIN Verified & Session Unlocked',
    'Security event logged in real time to the Firestore security_audit_logs collection',
    6000
  );

  // Step 2: Log Sleep & Snoring
  await page.click('button[data-tab="snoring"]');
  await setCaption(
    page,
    'Step 2: Log Sleep, Voice Commands & Acoustic Snoring Detector',
    'Patients can log sleep in 3 simple ways: Acoustic Snore Detector, Multilingual Voice Command, or Quick Daily Form',
    9000
  );

  await page.click('button[onclick="simulateSnoreBurst()"]');
  await setCaption(
    page,
    'On-Device WebAudio FFT Snoring Classifier',
    'Analyzes 80–350 Hz palatal vibration bands locally in the browser — raw bedroom audio is never uploaded to the cloud',
    11000
  );

  await page.fill('#voice-transcript-input', 'Log 7.8 hours, AHI 1.9, snoring score 1, side sleeping, 0 alcohol');
  await setCaption(
    page,
    'Hands-Free Multilingual Voice Logging (EN / HI / KN / TE)',
    'Speaking or typing natural language automatically extracts CPAP hours, AHI, snoring score & sleep position via Gemini',
    8000
  );
  await page.click('button[onclick="submitVoiceTranscript()"]');
  await setCaption(
    page,
    'Voice Log Saved to Firestore & Charts Updated',
    'Logged 7.8h usage, AHI 1.9 events/hr, Snoring 1/10, and Side Sleeping position with instant coaching feedback',
    8000
  );

  // Step 3: My Body & Risk Check (BMI, Age, Smoking, STOP-BANG, ESS)
  await page.click('button[data-tab="profile"]');
  await setCaption(
    page,
    'Step 3: My Body, BMI, Age, Smoking & OSA Risk Check',
    'Manage Age, Height, Weight, Neck Size (cm), Blood Pressure, and Smoking Quit Date in one uncluttered view',
    10000
  );

  await page.fill('#pf-weight', '89.4');
  await page.click('#profile-form button[type="submit"]');
  await setCaption(
    page,
    'Live BMI & Smoke-Free Airway Recovery Tracking',
    'Updating weight to 89.4 kg recalculates BMI (29.2 kg/m²) and links weight loss directly to AHI improvement',
    9000
  );

  await page.evaluate(() => window.scrollBy({ top: 360, behavior: 'smooth' }));
  await setCaption(
    page,
    'Official 8-Item STOP-BANG & Epworth Sleepiness Scale (ESS)',
    'Combines questionnaire answers with BMI, Age (>50), Neck Size (>40cm) & Sex to compute clinical OSA risk',
    10000
  );
  await page.click('button[onclick="submitScreening()"]');
  await setCaption(
    page,
    'Clinical Screening Score Updated',
    'Displays STOP-BANG Risk Tier (5/8 High Risk) and Epworth Daytime Alertness Score (8/24) with drowsy-driving checks',
    8000
  );
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));

  // Step 4: Easy Exercise, Yoga & Throat Therapy
  await page.click('button[data-tab="exercise"]');
  await setCaption(
    page,
    'Step 4: OpenCV / MediaPipe Pose Exercise, Yoga & Throat Coach',
    'Real-time 2D skeletal landmark tracking & joint-angle geometry (calcAngleDegrees) for rep counting and posture cues',
    9000
  );

  await page.click('#btn-sim-pose');
  await setCaption(
    page,
    'Exercise 1: Bodyweight Squat (Metabolic BMI & OSA Risk Reduction)',
    'Tracks Hip-Knee-Ankle flexion angles (<100°) and counts completed repetitions automatically in the browser',
    10000
  );

  await page.selectOption('#pose-exercise-select', 'yoga_bridge_setu_bandhasana');
  await page.evaluate(() => changePoseExercise());
  await setCaption(
    page,
    'Exercise 2: Yoga Bridge Pose (Setu Bandhasana)',
    'Checks Shoulder-Hip-Knee thoracic alignment (>162°) with live cues: "Raise your hips higher and expand the ribcage"',
    10000
  );

  await page.selectOption('#pose-exercise-select', 'oropharyngeal_tongue_slide');
  await page.evaluate(() => changePoseExercise());
  await setCaption(
    page,
    'Exercise 3: Oropharyngeal Throat & Tongue Exercises',
    'Supportive myofunctional therapy toning the genioglossus and soft palate muscles to reduce upper airway collapse',
    9000
  );

  await page.click('button[onclick="saveCompletedWorkout()"]');
  await setCaption(
    page,
    'Workout Logged & Guided 4-7-8 Pranayama Breathing',
    'Saving the workout updates the patient profile and unlocks guided nasal breathing and Open-Meteo CPAP humidifier tuning',
    9000
  );

  // Step 5: Ask AI Coach & Security Center
  await page.click('button[data-tab="agent"]');
  await setCaption(
    page,
    'Step 5: Conversational Gemini 2.5 Flash Coach + A2UI Cards',
    'Powered by Google ADK with 12 clinical tools, Firestore Memory Bank, and rich A2UI v0.8 visual cards',
    9000
  );

  await page.fill('#input', 'Summarize my CMS compliance, BMI trend, smoking streak, and snoring correlation.');
  await page.click('#form button[type="submit"]');
  await setCaption(
    page,
    'Gemini Multi-Tool Execution & A2UI Card Rendering',
    'The agent queries Firestore profile, sleep logs, and Pearson correlations to deliver personalized coaching',
    12000
  );

  await page.evaluate(() => window.scrollBy({ top: 480, behavior: 'smooth' }));
  await setCaption(
    page,
    'Security & Privacy Center + Sleep Study PDF Extractor + Doctor Report',
    'Granular Camera/Mic privacy toggles, live Security Audit Log, and 1-Click Physician PDF Report export. Thank you!',
    11000
  );

  // Ensure total duration is strictly between 185s and 225s (3 to 4 minutes)
  const elapsedMs = Date.now() - startWall;
  const targetMs = 198000; // 3 minutes 18 seconds
  if (elapsedMs < targetMs) {
    const remaining = targetMs - elapsedMs;
    console.log(`Padding final ${remaining}ms to hit exact 3m 18s target...`);
    await page.waitForTimeout(remaining);
  }

  const finalSec = ((Date.now() - startWall) / 1000).toFixed(1);
  console.log(`Recorded demo duration: ${finalSec} seconds.`);

  await vidContext.close();
  await browser.close();

  // Move recorded video to submission/SomnoCare_Demo_Video.webm
  const files = fs.readdirSync(videoDir).filter(f => f.endsWith('.webm'));
  if (files.length > 0) {
    const src = path.join(videoDir, files[0]);
    const dest = path.join(OUT_DIR, 'SomnoCare_Demo_Video.webm');
    fs.copyFileSync(src, dest);
    console.log(`Saved final demo video to: ${dest}`);
  }
})();
