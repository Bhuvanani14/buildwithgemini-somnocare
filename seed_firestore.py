from app.wellness_hub import get_store


def seed():
    print("Seeding SomnoCare Firestore & Local Hybrid Store (cpap_supplies, sleep_therapy_logs, patient_profile, exercise_logs)...")
    store = get_store()
    result = store.reset_user_data("default_user")
    profile = store.get_document("patient_profile", "default_user") or {}
    logs = store.list_collection("sleep_therapy_logs", user_id="default_user")
    supplies = store.list_collection("cpap_supplies")
    print(f"Seeded {len(supplies)} CPAP supplies, {len(logs)} nightly sleep/snoring logs, and profile for {profile.get('name')} (BMI {profile.get('bmi')}, STOP-BANG {profile.get('stop_bang', {}).get('score')}/8).")
    print(result["message"])


if __name__ == "__main__":
    seed()
