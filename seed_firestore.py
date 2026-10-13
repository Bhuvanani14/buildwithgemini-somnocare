import datetime
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-fe29ebecbbcc"

def seed():
    db = firestore.Client(project=PROJECT_ID)
    print(f"Connecting to Firestore with project: {PROJECT_ID}")

    supplies = [
        {
            "id": "mask-airfit-p10",
            "name": "AirFit P10 Nasal Pillows",
            "category": "mask",
            "type": "Nasal Pillows",
            "description": "Ultra-quiet, minimalist nasal pillows mask with flexible woven-mesh vent.",
            "replacement_interval_days": 180,
            "cushion_replacement_interval_days": 14,
            "in_stock": True,
            "best_for": "Active sleepers, reading before bed, minimal facial contact."
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
            "best_for": "Mouth breathing, high CPAP pressures, frequent nasal congestion."
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
            "best_for": "Nose breathers seeking stability and secure seal across varying pressures."
        },
        {
            "id": "filter-hypoallergenic",
            "name": "Ultra-Fine Hypoallergenic Air Filters (2-Pack)",
            "category": "filter",
            "type": "Disposable Filter",
            "description": "Blocks fine particulate matter, pollen, and pet dander from entering CPAP airway.",
            "replacement_interval_days": 14,
            "in_stock": True,
            "best_for": "Allergy sufferers and dust prevention."
        },
        {
            "id": "climate-line-tubing",
            "name": "ClimateLineAir Heated Tubing (15mm)",
            "category": "tubing",
            "type": "Heated Tubing",
            "description": "Maintains comfortable air temperature and prevents condensation (rainout) in tube.",
            "replacement_interval_days": 90,
            "in_stock": True,
            "best_for": "Preventing tube rainout, dry throat, and cold airway sensations."
        }
    ]

    for item in supplies:
        doc_ref = db.collection("cpap_supplies").document(item["id"])
        doc_ref.set(item)
        print(f"Seeded supply: {item['name']}")

    # Seed sample sleep logs
    sample_logs = [
        {
            "id": "log-user1-20261011",
            "user_id": "default_user",
            "date": "2026-10-11",
            "usage_hours": 7.2,
            "ahi": 2.4,
            "mask_leak_rate": 4.1,
            "restedness_score": 8,
            "notes": "Felt well-rested, no mask leaks.",
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        },
        {
            "id": "log-user1-20261012",
            "user_id": "default_user",
            "date": "2026-10-12",
            "usage_hours": 6.5,
            "ahi": 3.8,
            "mask_leak_rate": 8.5,
            "restedness_score": 7,
            "notes": "Slight dry mouth in morning, raised humidity level.",
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        }
    ]

    for log in sample_logs:
        doc_ref = db.collection("sleep_therapy_logs").document(log["id"])
        doc_ref.set(log)
        print(f"Seeded sleep log: {log['id']}")

    print("Seeding complete.")

if __name__ == "__main__":
    seed()
