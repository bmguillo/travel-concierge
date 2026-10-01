import inspect
import json
import os
import urllib.parse
import urllib.request
import uuid

from google import genai
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google.genai import types

# IMPORTANT: Hardcode project ID and Cloud Storage bucket as strings as required for Agent Platform compatibility
FIRESTORE_PROJECT = "qwiklabs-gcp-01-68eca9383e32"
STORAGE_BUCKET_NAME = "travel-concierge-assets-qwiklabs-gcp-01-68eca9383e32"


def _get_db():
    return firestore.Client(project=FIRESTORE_PROJECT)

def search_destinations(query: str = "") -> list[dict]:
    """Search for travel destinations in the catalog database.

    Args:
        query: Optional filter keyword like a country, city name, or category (e.g. 'Japan', 'Paris', 'Beach', 'Romance').

    Returns:
        List of matching travel destination documents.
    """
    db = _get_db()
    docs = db.collection("destinations").stream()
    results = []
    q_lower = query.strip().lower()

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        if not q_lower:
            results.append(data)
        else:
            searchable_text = f"{data.get('name', '')} {data.get('country', '')} {data.get('category', '')} {data.get('description', '')}".lower()
            if q_lower in searchable_text:
                results.append(data)

    return results

def get_destination_details(destination_id: str) -> dict:
    """Get full details for a specific travel destination by its ID.

    Args:
        destination_id: Unique identifier of the destination (e.g. 'tokyo-japan', 'paris-france', 'rio-de-janeiro').

    Returns:
        Destination details object or error message if not found.
    """
    db = _get_db()
    doc_ref = db.collection("destinations").document(destination_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"error": f"Destination with ID '{destination_id}' not found."}

    data = doc.to_dict()
    data["id"] = doc.id
    return data

def add_destination(
    name: str,
    country: str,
    category: str,
    description: str,
    budget_tier: str,
    popular_activities: list[str],
    best_season: str,
    rating: float = 4.5,
) -> dict:
    """Add a new travel destination to the Firestore catalog database.

    Args:
        name: Name of the city or location (e.g. 'Kyoto', 'Venice').
        country: Country where the destination is located (e.g. 'Japan', 'Italy').
        category: Theme or type (e.g. 'History & Tradition', 'Coastal', 'Adventure').
        description: A compelling summary of what makes this destination special.
        budget_tier: Price level indicator ('$', '$$', '$$$', '$$$$').
        popular_activities: List of recommended things to do at the destination.
        best_season: Recommended time of year to visit.
        rating: Rating out of 5.0 (default 4.5).

    Returns:
        Confirmation dict with the newly created destination document ID.
    """
    db = _get_db()
    doc_id = f"{name.lower().replace(' ', '-')}-{country.lower().replace(' ', '-')}"
    item = {
        "id": doc_id,
        "name": name,
        "country": country,
        "category": category,
        "description": description,
        "budget_tier": budget_tier,
        "popular_activities": popular_activities,
        "best_season": best_season,
        "rating": rating,
    }
    db.collection("destinations").document(doc_id).set(item)
    return {"status": "success", "message": f"Successfully added destination '{name}'", "destination": item}

def save_travel_itinerary(user_id: str, destination_name: str, itinerary_notes: str, days: int = 3) -> dict:
    """Save a custom travel itinerary for a user to Firestore.

    Args:
        user_id: Unique user identifier or username.
        destination_name: Name of the travel destination.
        itinerary_notes: Detailed day-by-day plan or notes for the trip.
        days: Duration of the trip in days (default 3).

    Returns:
        Status message with saved itinerary details.
    """
    db = _get_db()
    doc_ref = db.collection("user_itineraries").document()
    itinerary_data = {
        "id": doc_ref.id,
        "user_id": user_id,
        "destination_name": destination_name,
        "itinerary_notes": itinerary_notes,
        "days": days,
    }
    doc_ref.set(itinerary_data)
    return {"status": "success", "message": f"Itinerary saved for {destination_name}", "itinerary_id": doc_ref.id}


def convert_currency(amount: float, from_currency: str = "USD", to_currency: str = "JPY") -> dict:
    """Convert a monetary amount between currencies using live exchange rates.

    Args:
        amount: The numerical amount of money to convert (e.g. 250.0).
        from_currency: 3-letter source currency code (e.g. 'USD', 'EUR', 'GBP').
        to_currency: 3-letter target currency code (e.g. 'JPY', 'EUR', 'BRL', 'ISK').

    Returns:
        Dict containing original amount, converted amount, target currency, and exchange rate.
    """
    from_curr = from_currency.strip().upper()
    to_curr = to_currency.strip().upper()

    fallback_rates = {
        "USD": 1.0,
        "JPY": 155.0,
        "EUR": 0.92,
        "BRL": 5.60,
        "ISK": 138.0,
        "GBP": 0.79,
    }

    rate = None
    try:
        url = f"https://open.er-api.com/v6/latest/{from_curr}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("result") == "success":
                rate = data.get("rates", {}).get(to_curr)
    except Exception:
        pass

    if rate is None:
        from_usd = fallback_rates.get(from_curr, 1.0)
        to_usd = fallback_rates.get(to_curr, 1.0)
        rate = to_usd / from_usd

    converted_amount = round(amount * rate, 2)
    return {
        "original_amount": amount,
        "from_currency": from_curr,
        "converted_amount": converted_amount,
        "to_currency": to_curr,
        "exchange_rate": round(rate, 4),
    }


def get_live_destination_weather(city_name: str) -> dict:
    """Fetch real-time weather and temperature for a destination city using public weather services.

    Args:
        city_name: Name of the city (e.g. 'Tokyo', 'Paris', 'Rio de Janeiro', 'Reykjavik').

    Returns:
        Dict containing current temperature, weather conditions, wind speed, and location details.
    """
    # Read optional API key from environment variable if configured
    api_key = os.getenv("WEATHER_API_KEY", os.getenv("OPENWEATHER_API_KEY", ""))

    try:
        # Step 1: Geocode city name to lat/lon using Open-Meteo public geocoding API
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city_name)}&count=1"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))

        results = geo_data.get("results", [])
        if not results:
            return {"error": f"City '{city_name}' not found."}

        location = results[0]
        lat = location["latitude"]
        lon = location["longitude"]
        city = location.get("name", city_name)
        country = location.get("country", "")

        # Step 2: Fetch current weather forecast
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        if api_key:
            weather_url += f"&apikey={api_key}"

        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_w, timeout=5) as resp_w:
            w_data = json.loads(resp_w.read().decode("utf-8"))

        current = w_data.get("current_weather", {})
        temp_c = current.get("temperature", 20.0)
        temp_f = round((temp_c * 9 / 5) + 32, 1)
        windspeed = current.get("windspeed", 0.0)

        weather_code = current.get("weathercode", 0)
        conditions = "Clear / Sunny" if weather_code <= 3 else "Cloudy / Rainy"

        return {
            "city": city,
            "country": country,
            "temperature_celsius": temp_c,
            "temperature_fahrenheit": temp_f,
            "condition": conditions,
            "windspeed_kmh": windspeed,
            "latitude": lat,
            "longitude": lon,
        }
    except Exception as e:
        return {"error": f"Could not retrieve weather for '{city_name}': {str(e)}"}


def _get_maps_api_key() -> str:
    key = os.getenv("MAPS_API_KEY", os.getenv("GOOGLE_MAPS_API_KEY", ""))
    if not key:
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MAPS_API_KEY=") or line.startswith("GOOGLE_MAPS_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        if key:
                            break
    return key


def geocode_address(address: str) -> dict:
    """Convert a street address or landmark name into geographic coordinates using Google Geocoding API.

    Args:
        address: The landmark, street address, or location to geocode (e.g. 'Tokyo Station', 'Eiffel Tower, Paris').

    Returns:
        Dict containing formatted address, location coordinates (latitude, longitude), and place ID.
    """
    api_key = _get_maps_api_key()
    if not api_key:
        return {"error": "MAPS_API_KEY environment variable is not set."}

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") != "OK" or not data.get("results"):
            return {"error": f"Geocoding failed for '{address}': {data.get('status')}"}

        result = data["results"][0]
        location = result["geometry"]["location"]
        return {
            "name": address,
            "address": result.get("formatted_address", address),
            "location": {
                "latitude": location["lat"],
                "longitude": location["lng"],
            },
            "place_id": result.get("place_id", ""),
        }
    except Exception as e:
        return {"error": f"Geocoding request error: {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius_meters: int = 1500,
    max_results: int = 5,
) -> dict:
    """Find nearby places of a given type around coordinates using Google Places API (New).

    Args:
        latitude: Latitude coordinate of the search center.
        longitude: Longitude coordinate of the search center.
        place_type: Type of place to search for (e.g. 'restaurant', 'hotel', 'tourist_attraction', 'museum', 'cafe').
        radius_meters: Search radius in meters (default 1500m).
        max_results: Maximum number of places to return (default 5).

    Returns:
        Dict containing a list of nearby places with key fields (name, address, location, rating).
    """
    api_key = _get_maps_api_key()
    if not api_key:
        return {"error": "MAPS_API_KEY environment variable is not set."}

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.types",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": min(max_results, 20),
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": float(radius_meters),
            }
        },
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        raw_places = data.get("places", [])
        places_list = []
        for p in raw_places:
            display_name = p.get("displayName", {}).get("text", "")
            places_list.append({
                "name": display_name,
                "address": p.get("formattedAddress", ""),
                "location": {
                    "latitude": p.get("location", {}).get("latitude"),
                    "longitude": p.get("location", {}).get("longitude"),
                },
                "rating": p.get("rating"),
                "types": p.get("types", []),
            })

        return {
            "center": {"latitude": latitude, "longitude": longitude},
            "place_type": place_type,
            "count": len(places_list),
            "places": places_list,
        }
    except Exception as e:
        return {"error": f"Places API search failed: {str(e)}"}


def generate_destination_image(
    destination_name: str,
    prompt_description: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Generate a photo or visual postcard for a travel destination using gemini-3.1-flash-lite-image in global region.

    Args:
        destination_name: Name of the travel destination (e.g. 'Kyoto', 'Paris', 'Rio de Janeiro').
        prompt_description: Optional additional scenic details or style description for the image.
        tool_context: Context object provided automatically by ADK for saving artifacts.

    Returns:
        Dict containing generation status, filename, and public HTTPS URL of the image on Cloud Storage.
    """
    image_prompt = (
        f"A beautiful, high quality travel photo of {destination_name}. {prompt_description}".strip()
    )

    try:
        # Step 1: Generate image using gemini-3.1-flash-lite-image model in global region
        client = genai.Client(vertexai=True, location="global", project=FIRESTORE_PROJECT)
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=image_prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        image_bytes = None
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return {"error": f"No image bytes generated for '{destination_name}'."}

        sanitized_name = "".join(c if c.isalnum() else "_" for c in destination_name.lower())
        filename = f"{sanitized_name}_{uuid.uuid4().hex[:8]}.jpg"

        # Step 2 (1): Save image with tool_context.save_artifact for Playground Artifacts panel
        if tool_context is not None:
            try:
                artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
                if inspect.isawaitable(res):
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        asyncio.run(res)
            except Exception as art_err:
                print(f"Warning: tool_context.save_artifact failed: {art_err}")

        # Step 3 (2): Upload raw image bytes directly to public GCS bucket (no local file writing)
        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")

        public_url = f"https://storage.googleapis.com/{STORAGE_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "destination_name": destination_name,
            "filename": filename,
            "public_url": public_url,
            "image_url": public_url,
            "message": f"Successfully generated image for {destination_name} and uploaded to public Cloud Storage.",
        }
    except Exception as e:
        return {"error": f"Failed to generate destination image: {str(e)}"}


def generate_destination_video(
    destination_name: str,
    prompt_description: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Generate a short video preview for a travel destination using Google's Omni model (gemini-omni-flash-preview) in global region.

    Args:
        destination_name: Name of the travel destination or attraction (e.g. 'Kyoto', 'Eiffel Tower Paris', 'Rio Beaches').
        prompt_description: Optional scenic details or style description for the video clip.
        tool_context: Context object provided automatically by ADK for saving artifacts.

    Returns:
        Dict containing generation status, filename, and public HTTPS URL of the video on Cloud Storage.
    """
    video_prompt = (
        f"A beautiful, high quality short video preview of {destination_name}. {prompt_description}".strip()
    )

    try:
        # Step 1: Generate video using gemini-omni-flash-preview model in global region
        client = genai.Client(vertexai=True, location="global", project=FIRESTORE_PROJECT)

        video_bytes = None
        mime_type = "video/mp4"

        try:
            res = client.interactions.create(
                model="gemini-omni-flash-preview",
                input=video_prompt,
                response_format=[{"type": "video"}]
            )
            if hasattr(res, "outputs") and res.outputs:
                for out in res.outputs:
                    out_dict = out.model_dump() if hasattr(out, "model_dump") else (out if isinstance(out, dict) else {})
                    video_info = out_dict.get("video") if isinstance(out_dict, dict) else None
                    if isinstance(video_info, dict):
                        data = video_info.get("bytes_base64") or video_info.get("data")
                        if data:
                            if isinstance(data, str):
                                import base64
                                video_bytes = base64.b64decode(data)
                            elif isinstance(data, bytes):
                                video_bytes = data
                            break
                    elif hasattr(out, "data") and getattr(out, "data", None):
                        video_bytes = getattr(out, "data")
                        break
        except Exception as inter_err:
            print(f"Interactions API error: {inter_err}")

        if not video_bytes:
            try:
                response = client.models.generate_content(
                    model="gemini-omni-flash-preview",
                    contents=video_prompt,
                    config=types.GenerateContentConfig(response_modalities=["VIDEO"]),
                )
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            video_bytes = part.inline_data.data
                            if part.inline_data.mime_type:
                                mime_type = part.inline_data.mime_type
                            break
            except Exception as gc_err:
                print(f"generate_content fallback error: {gc_err}")

        if not video_bytes:
            return {"error": f"Failed to retrieve video bytes for '{destination_name}'."}

        sanitized_name = "".join(c if c.isalnum() else "_" for c in destination_name.lower())
        filename = f"{sanitized_name}_{uuid.uuid4().hex[:8]}.mp4"

        # Step 2 (1): Save video with tool_context.save_artifact for Playground Artifacts panel
        if tool_context is not None:
            try:
                artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
                res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
                if inspect.isawaitable(res):
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        asyncio.run(res)
            except Exception as art_err:
                print(f"Warning: tool_context.save_artifact failed: {art_err}")

        # Step 3 (2): Upload video bytes directly to public GCS bucket (no local file writing)
        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{STORAGE_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "destination_name": destination_name,
            "filename": filename,
            "public_url": public_url,
            "video_url": public_url,
            "message": f"Successfully generated video for {destination_name} and uploaded to public Cloud Storage.",
        }
    except Exception as e:
        return {"error": f"Failed to generate destination video: {str(e)}"}





