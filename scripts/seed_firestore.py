"""Seed script to populate Firestore with sample travel destinations."""

import time
from google.cloud import firestore

# IMPORTANT: Hardcoded project ID as string (do not use google.auth.default() or GOOGLE_CLOUD_PROJECT)
PROJECT_ID = "qwiklabs-gcp-01-68eca9383e32"

DESTINATIONS = [
    {
        "id": "tokyo-japan",
        "name": "Tokyo",
        "country": "Japan",
        "category": "Culture & Modern City",
        "description": "Dynamic capital blending ultra-modern skyscrapers, ancient temples, vibrant street food, and serene gardens.",
        "budget_tier": "$$$",
        "popular_activities": ["Visit Senso-ji Temple", "Explore Shibuya Crossing", "Sushi tasting in Tsukiji", "Stroll Shinjuku Gyoen"],
        "best_season": "Spring & Autumn",
        "rating": 4.9,
    },
    {
        "id": "paris-france",
        "name": "Paris",
        "country": "France",
        "category": "Romance & Art",
        "description": "The City of Light, famous for world-class museums, iconic landmarks, haute cuisine, and romantic Seine river cruises.",
        "budget_tier": "$$$$",
        "popular_activities": ["Tour the Louvre Museum", "Eiffel Tower at sunset", "Bakery tour in Le Marais", "Walk along Canal Saint-Martin"],
        "best_season": "Spring & Early Autumn",
        "rating": 4.8,
    },
    {
        "id": "rio-de-janeiro",
        "name": "Rio de Janeiro",
        "country": "Brazil",
        "category": "Nature & Beach",
        "description": "Breathtaking coastal city known for Copacabana beach, Christ the Redeemer statue, and vibrant Samba culture.",
        "budget_tier": "$$",
        "popular_activities": ["Sugarloaf Mountain Cable Car", "Relax at Ipanema Beach", "Visit Christ the Redeemer", "Samba night in Lapa"],
        "best_season": "December to March",
        "rating": 4.7,
    },
    {
        "id": "kyoto-japan",
        "name": "Kyoto",
        "country": "Japan",
        "category": "History & Tradition",
        "description": "Cultural heart of Japan filled with classical Zen gardens, bamboo groves, traditional wooden houses, and geisha districts.",
        "budget_tier": "$$$",
        "popular_activities": ["Fushimi Inari Torii Gates", "Arashiyama Bamboo Grove", "Traditional Tea Ceremony", "Kinkaku-ji Golden Pavilion"],
        "best_season": "Spring & Autumn",
        "rating": 4.9,
    },
    {
        "id": "reykjavik-iceland",
        "name": "Reykjavik",
        "country": "Iceland",
        "category": "Adventure & Landscapes",
        "description": "Gateway to volcanic landscapes, geothermal hot springs, cascading waterfalls, and spectacular Northern Lights.",
        "budget_tier": "$$$$",
        "popular_activities": ["Soak in the Blue Lagoon", "Golden Circle Tour", "Northern Lights Hunt", "South Coast Waterfall Hike"],
        "best_season": "Winter or Summer",
        "rating": 4.8,
    },
]

def seed_firestore():
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("destinations")
    print(f"Seeding Firestore collection 'destinations' in project '{PROJECT_ID}'...")

    for item in DESTINATIONS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        for attempt in range(5):
            try:
                doc_ref.set(item)
                print(f"  ✓ Seeded destination: {item['name']} ({doc_id})")
                break
            except Exception as e:
                if attempt == 4:
                    raise e
                time.sleep(2)
        time.sleep(0.5)

    print("Firestore seeding complete!")

if __name__ == "__main__":
    seed_firestore()
