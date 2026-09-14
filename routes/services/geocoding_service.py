import hashlib
import json
import logging
import os
import re
from typing import Dict, Any, Optional
import requests
from django.conf import settings
from django.core.cache import cache
from routes.exceptions import (
    GeocodingNotFoundError,
    NonUSALocationError,
    GeocodingServiceError,
)

logger = logging.getLogger(__name__)

# US State abbreviations mapping
US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


def normalize_location_query(query: str) -> str:
    cleaned = query.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    return cleaned


def make_cache_key(prefix: str, value: str) -> str:
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{h}"


class GeocodingService:
    """
    Geocodes human-readable USA locations into coordinates.
    Employs a resilient multi-tier strategy:
    1. Fast in-memory cache lookup.
    2. Local high-performance US cities database lookup (offline, immune to rate limits).
    3. External Nominatim OpenStreetMap API query with USA verification and graceful fallback.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        timeout: int = 5,
    ):
        self.api_url = api_url or getattr(
            settings, "GEOCODING_API_URL", "https://nominatim.openstreetmap.org/search"
        )
        self.user_agent = user_agent or getattr(
            settings, "GEOCODING_USER_AGENT", "SpotterFuelOptimizer/1.0"
        )
        self.timeout = timeout
        self.cache_ttl = getattr(settings, "CACHE_TTL_SECONDS", 86400)
        self._local_cache = self._load_local_city_cache()

    def _load_local_city_cache(self) -> Dict[str, list]:
        path = os.path.join(settings.BASE_DIR, "data", "cities_coordinates_cache.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load local city cache: {e}")
        return {}

    def _lookup_local_city(self, location_name: str) -> Optional[Dict[str, Any]]:
        norm = normalize_location_query(location_name)
        # Check if coordinates string directly (e.g. "34.05, -118.24")
        coord_match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)$", norm)
        if coord_match:
            lat, lon = float(coord_match.group(1)), float(coord_match.group(2))
            return {
                "name": location_name.strip(),
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "display_name": location_name.strip(),
            }

        # Try parsing "City, State"
        parts = [p.strip() for p in norm.split(",")]
        if len(parts) >= 2:
            city_str = parts[0].upper()
            state_str = parts[1].lower()
            state_abbr = US_STATES.get(state_str, parts[1].upper())
            key = f"{city_str}|{state_abbr}"
            if key in self._local_cache:
                lat, lon = self._local_cache[key]
                return {
                    "name": location_name.strip(),
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "display_name": f"{parts[0].title()}, {state_abbr}, USA",
                }
        elif len(parts) == 1:
            city_str = parts[0].upper()
            # Match first matching city in cache
            for k, coords in self._local_cache.items():
                if k.startswith(f"{city_str}|"):
                    return {
                        "name": location_name.strip(),
                        "latitude": round(coords[0], 6),
                        "longitude": round(coords[1], 6),
                        "display_name": f"{location_name.strip()}, USA",
                    }
        return None

    def geocode(self, location_name: str) -> Dict[str, Any]:
        if not location_name or not location_name.strip():
            raise GeocodingNotFoundError("Location name cannot be empty.")

        norm_key = normalize_location_query(location_name)
        cache_key = make_cache_key("geocoding", norm_key)
        cached_result = cache.get(cache_key)

        if cached_result:
            logger.info(f"Geocoding cache hit for '{location_name}'")
            return cached_result

        # Tier 2: Check local pre-indexed US city coordinates database
        local_result = self._lookup_local_city(location_name)
        if local_result:
            logger.info(f"Local coordinates hit for '{location_name}' -> ({local_result['latitude']}, {local_result['longitude']})")
            cache.set(cache_key, local_result, self.cache_ttl)
            return local_result

        # Tier 3: Query external Nominatim geocoding API
        logger.info(f"Querying external geocoder for '{location_name}'")
        params = {
            "q": location_name,
            "format": "json",
            "limit": 1,
            "countrycodes": "us",
            "addressdetails": 1,
        }
        headers = {"User-Agent": self.user_agent}

        try:
            response = requests.get(
                self.api_url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.warning(f"External geocoder request failed ({e}). Checking fuzzy fallback.")
            raise GeocodingServiceError(f"Geocoding service unavailable: {str(e)}")

        if not data or not isinstance(data, list) or len(data) == 0:
            raise GeocodingNotFoundError(
                f"Location '{location_name}' could not be resolved within the USA."
            )

        top_result = data[0]
        country_code = top_result.get("address", {}).get("country_code", "").lower()
        if country_code and country_code != "us":
            raise NonUSALocationError(
                f"Location '{location_name}' is located outside the USA."
            )

        latitude = round(float(top_result["lat"]), 6)
        longitude = round(float(top_result["lon"]), 6)

        result = {
            "name": location_name.strip(),
            "latitude": latitude,
            "longitude": longitude,
            "display_name": top_result.get("display_name", location_name.strip()),
        }

        cache.set(cache_key, result, self.cache_ttl)
        return result
