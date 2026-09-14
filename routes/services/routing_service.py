import hashlib
import logging
from typing import Dict, Any, Optional
import requests
from django.conf import settings
from django.core.cache import cache
from routes.exceptions import NoRouteFoundError, RoutingServiceError

logger = logging.getLogger(__name__)

METERS_TO_MILES = 0.000621371


class RoutingService:
    """
    Handles fetching driving routes, distances, durations, and GeoJSON geometry
    from Open Source Routing Machine (OSRM) with local caching.
    """

    def __init__(self, api_url: Optional[str] = None, timeout: int = 15):
        self.api_url = (
            api_url
            or getattr(
                settings,
                "ROUTING_API_URL",
                "https://router.project-osrm.org/route/v1/driving/",
            )
        ).rstrip("/") + "/"
        self.timeout = timeout
        self.cache_ttl = getattr(settings, "CACHE_TTL_SECONDS", 86400)

    def get_route(
        self,
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> Dict[str, Any]:
        cache_key = (
            f"route_{start_lat:.4f}_{start_lon:.4f}_{dest_lat:.4f}_{dest_lon:.4f}".replace("-", "m").replace(".", "p")
        )
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Routing cache hit for {cache_key}")
            return cached

        endpoint = (
            f"{self.api_url}{start_lon},{start_lat};{dest_lon},{dest_lat}"
            f"?overview=full&geometries=geojson"
        )
        logger.info(f"Fetching driving route from OSRM: ({start_lat},{start_lon}) -> ({dest_lat},{dest_lon})")

        try:
            response = requests.get(
                endpoint,
                headers={"User-Agent": "SpotterFuelOptimizer/1.0 (assessment)"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            logger.error("OSRM routing request timed out.")
            raise RoutingServiceError("Routing service request timed out.")
        except requests.RequestException as e:
            logger.error(f"OSRM routing request failed: {e}")
            raise RoutingServiceError(f"Routing service unavailable: {str(e)}")

        code = data.get("code")
        routes = data.get("routes", [])

        if code != "Ok" or not routes:
            logger.warning(f"OSRM returned no route. Code: {code}")
            raise NoRouteFoundError("No driving route found between the specified locations.")

        primary_route = routes[0]
        distance_meters = primary_route.get("distance", 0.0)
        duration_seconds = primary_route.get("duration", 0.0)
        geometry = primary_route.get("geometry", {})

        distance_miles = round(distance_meters * METERS_TO_MILES, 2)
        duration_minutes = round(duration_seconds / 60.0, 1)

        result = {
            "distance_miles": distance_miles,
            "duration_minutes": duration_minutes,
            "geometry": geometry,
        }

        cache.set(cache_key, result, self.cache_ttl)
        return result
