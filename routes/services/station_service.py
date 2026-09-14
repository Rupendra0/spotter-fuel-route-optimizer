import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from routes.models import FuelStation
from routes.services.geo_utils import (
    calculate_route_bounding_box,
    SpatialPolylineIndex,
)

logger = logging.getLogger(__name__)


class StationService:
    """
    Identifies fuel stations within a corridor along the driving route
    and calculates their sequential position (miles from start) along the route.
    Uses SpatialPolylineIndex for ultra-fast geospatial lookups.
    """

    def __init__(self, corridor_radius_miles: Optional[float] = None):
        self.corridor_radius = (
            corridor_radius_miles
            if corridor_radius_miles is not None
            else getattr(settings, "ROUTE_STATION_RADIUS_MILES", 15.0)
        )

    def get_candidate_stations_along_route(
        self,
        route_coordinates: List[List[float]],
        total_route_distance_miles: float,
    ) -> List[Dict[str, Any]]:
        """
        Finds all fuel stations within corridor_radius miles of the route polyline.
        Returns stations ordered by distance_from_start_miles.
        """
        if not route_coordinates or len(route_coordinates) < 2:
            return []

        # 1. Calculate bounding box for SQL pre-filtering
        min_lat, max_lat, min_lon, max_lon = calculate_route_bounding_box(
            route_coordinates, self.corridor_radius
        )

        logger.info(
            f"Bounding box for corridor ({self.corridor_radius} mi): "
            f"lat=[{min_lat:.3f}, {max_lat:.3f}], lon=[{min_lon:.3f}, {max_lon:.3f}]"
        )

        # 2. Query stations inside bounding box
        stations_query = FuelStation.objects.filter(
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lon,
            longitude__lte=max_lon,
        ).only(
            "id",
            "opis_id",
            "name",
            "address",
            "city",
            "state",
            "rack_id",
            "retail_price",
            "latitude",
            "longitude",
        )

        bbox_stations = list(stations_query)
        logger.info(f"Stations found within bounding box: {len(bbox_stations)}")

        if not bbox_stations:
            return []

        # 3. Build fast 2D spatial index over polyline segments
        spatial_index = SpatialPolylineIndex(route_coordinates, grid_size_deg=0.3)

        # 4. Filter stations using indexed proximity queries
        candidate_stations = []
        for st in bbox_stations:
            dist_to_route, dist_from_start = spatial_index.find_nearest_position(
                st.latitude, st.longitude
            )

            if dist_to_route <= self.corridor_radius:
                clamped_dist = max(0.0, min(total_route_distance_miles, dist_from_start))
                candidate_stations.append(
                    {
                        "station_id": st.id,
                        "opis_id": st.opis_id,
                        "name": st.name,
                        "address": st.address,
                        "city": st.city,
                        "state": st.state,
                        "rack_id": st.rack_id,
                        "retail_price": float(st.retail_price),
                        "latitude": st.latitude,
                        "longitude": st.longitude,
                        "distance_from_start_miles": round(clamped_dist, 2),
                        "distance_to_route_miles": round(dist_to_route, 2),
                    }
                )

        # 5. Sort candidate stations sequentially along the route
        candidate_stations.sort(key=lambda s: s["distance_from_start_miles"])
        logger.info(
            f"Candidate stations within {self.corridor_radius} mi corridor: {len(candidate_stations)}"
        )

        return candidate_stations
