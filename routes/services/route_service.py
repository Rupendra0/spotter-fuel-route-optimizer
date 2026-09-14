import hashlib
import logging
import time
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache
from routes.services.geocoding_service import GeocodingService
from routes.services.routing_service import RoutingService
from routes.services.station_service import StationService
from routes.services.fuel_optimizer import FuelOptimizer

logger = logging.getLogger(__name__)


class RouteService:
    """
    Coordinates the full end-to-end route optimization pipeline:
    Geocoding -> Routing -> Corridor Station Filtering -> Fuel Optimization -> Response Assembly
    """

    def __init__(
        self,
        geocoding_service: Optional[GeocodingService] = None,
        routing_service: Optional[RoutingService] = None,
        station_service: Optional[StationService] = None,
        fuel_optimizer: Optional[FuelOptimizer] = None,
    ):
        self.geocoding_service = geocoding_service or GeocodingService()
        self.routing_service = routing_service or RoutingService()
        self.station_service = station_service or StationService()
        self.fuel_optimizer = fuel_optimizer or FuelOptimizer(
            max_range_miles=getattr(settings, "VEHICLE_MAX_RANGE_MILES", 500.0),
            fuel_economy_mpg=getattr(settings, "VEHICLE_MPG", 10.0),
            tank_capacity_gallons=getattr(settings, "VEHICLE_TANK_CAPACITY_GALLONS", 50.0),
        )
        self.cache_ttl = getattr(settings, "CACHE_TTL_SECONDS", 86400)

    def plan_optimized_route(
        self,
        start_location: str,
        finish_location: str,
        corridor_radius_miles: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes the route optimization pipeline.
        """
        t0 = time.time()
        start_clean = start_location.strip().lower()
        finish_clean = finish_location.strip().lower()
        corridor = corridor_radius_miles or getattr(settings, "ROUTE_STATION_RADIUS_MILES", 15.0)

        # High-level pipeline cache check
        plan_hash = hashlib.sha256(f"{start_clean}|{finish_clean}|{corridor}".encode()).hexdigest()[:16]
        cache_key = f"route_plan_{plan_hash}"
        cached_plan = cache.get(cache_key)
        if cached_plan:
            logger.info(f"Route plan cache hit for '{start_location}' -> '{finish_location}'")
            return cached_plan

        logger.info(f"Route request initiated: '{start_location}' -> '{finish_location}'")

        # Step 1: Geocode start and destination
        start_info = self.geocoding_service.geocode(start_location)
        finish_info = self.geocoding_service.geocode(finish_location)

        # Step 2: Fetch route geometry and distance (single external call, cached)
        route_data = self.routing_service.get_route(
            start_lat=start_info["latitude"],
            start_lon=start_info["longitude"],
            dest_lat=finish_info["latitude"],
            dest_lon=finish_info["longitude"],
        )

        total_distance = route_data["distance_miles"]
        duration_minutes = route_data["duration_minutes"]
        geometry = route_data["geometry"]
        coordinates = geometry.get("coordinates", [])

        # Step 3: Find candidate stations along route corridor (100% local)
        self.station_service.corridor_radius = corridor
        candidate_stations = self.station_service.get_candidate_stations_along_route(
            route_coordinates=coordinates,
            total_route_distance_miles=total_distance,
        )

        # Step 4: Run fuel optimization algorithm
        opt_result = self.fuel_optimizer.optimize(
            total_distance_miles=total_distance,
            candidate_stations=candidate_stations,
        )

        elapsed_ms = round((time.time() - t0) * 1000, 1)
        logger.info(
            f"Route calculation completed in {elapsed_ms}ms. "
            f"Distance: {total_distance} mi, Stops: {opt_result['summary']['number_of_stops']}, "
            f"Fuel cost: ${opt_result['summary']['total_fuel_cost']}"
        )

        response_payload = {
            "start": {
                "name": start_info["name"],
                "latitude": start_info["latitude"],
                "longitude": start_info["longitude"],
                "display_name": start_info.get("display_name", ""),
            },
            "finish": {
                "name": finish_info["name"],
                "latitude": finish_info["latitude"],
                "longitude": finish_info["longitude"],
                "display_name": finish_info.get("display_name", ""),
            },
            "route": {
                "distance_miles": total_distance,
                "duration_minutes": duration_minutes,
                "geometry": geometry,
            },
            "vehicle": {
                "max_range_miles": self.fuel_optimizer.max_range,
                "fuel_efficiency_mpg": self.fuel_optimizer.mpg,
                "tank_capacity_gallons": self.fuel_optimizer.tank_capacity,
            },
            "fuel_stops": opt_result["fuel_stops"],
            "summary": opt_result["summary"],
            "meta": {
                "candidate_stations_considered": len(candidate_stations),
                "computation_time_ms": elapsed_ms,
            },
        }

        # Cache complete plan
        cache.set(cache_key, response_payload, self.cache_ttl)
        return response_payload
