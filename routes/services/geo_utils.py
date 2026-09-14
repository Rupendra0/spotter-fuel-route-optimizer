import math
from typing import List, Tuple, Dict, Set

EARTH_RADIUS_MILES = 3958.8


def haversine_distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth
    using the Haversine formula.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_MILES * c


def compute_cumulative_polyline_distances(coordinates: List[List[float]]) -> List[float]:
    """
    Given a list of GeoJSON coordinates [[lon, lat], ...], compute the cumulative
    driving distance in miles at each vertex.
    """
    if not coordinates:
        return []

    distances = [0.0]
    total = 0.0
    for i in range(1, len(coordinates)):
        lon1, lat1 = coordinates[i - 1]
        lon2, lat2 = coordinates[i]
        step = haversine_distance_miles(lat1, lon1, lat2, lon2)
        total += step
        distances.append(total)

    return distances


def project_point_to_segment(
    p_lat: float, p_lon: float,
    a_lat: float, a_lon: float,
    b_lat: float, b_lon: float
) -> Tuple[float, float, float]:
    """
    Project point P onto segment AB using local equirectangular projection.
    Returns:
        t: fraction along segment [0.0, 1.0]
        proj_lat: latitude of closest point on segment
        proj_lon: longitude of closest point on segment
    """
    mid_lat_rad = math.radians((a_lat + b_lat) / 2.0)
    cos_lat = math.cos(mid_lat_rad)

    dx = (b_lon - a_lon) * cos_lat
    dy = b_lat - a_lat
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq < 1e-12:
        return 0.0, a_lat, a_lon

    ux = (p_lon - a_lon) * cos_lat
    uy = p_lat - a_lat
    t = (ux * dx + uy * dy) / seg_len_sq

    t_clamped = max(0.0, min(1.0, t))
    proj_lat = a_lat + t_clamped * (b_lat - a_lat)
    proj_lon = a_lon + t_clamped * (b_lon - a_lon)

    return t_clamped, proj_lat, proj_lon


def calculate_route_bounding_box(
    coordinates: List[List[float]],
    buffer_miles: float
) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box [min_lat, max_lat, min_lon, max_lon] around polyline
    with a buffer in miles.
    """
    if not coordinates:
        return 0.0, 0.0, 0.0, 0.0

    lats = [c[1] for c in coordinates]
    lons = [c[0] for c in coordinates]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    mid_lat = (min_lat + max_lat) / 2.0
    lat_buffer_deg = buffer_miles / 69.0
    lon_buffer_deg = buffer_miles / (69.0 * max(0.2, math.cos(math.radians(mid_lat))))

    return (
        min_lat - lat_buffer_deg,
        max_lat + lat_buffer_deg,
        min_lon - lon_buffer_deg,
        max_lon + lon_buffer_deg,
    )


class SpatialPolylineIndex:
    """
    High-performance 2D spatial grid index for route polyline segments.
    Accelerates station proximity queries from O(N * M) to O(N * k) where k << M.
    """

    def __init__(self, coordinates: List[List[float]], grid_size_deg: float = 0.3):
        self.coordinates = coordinates
        self.grid_size = grid_size_deg
        self.cumulative_distances = compute_cumulative_polyline_distances(coordinates)
        self.grid: Dict[Tuple[int, int], List[int]] = {}
        self._build_index()

    def _build_index(self):
        for i in range(len(self.coordinates) - 1):
            a_lon, a_lat = self.coordinates[i]
            b_lon, b_lat = self.coordinates[i + 1]

            min_gx = int(math.floor(min(a_lon, b_lon) / self.grid_size))
            max_gx = int(math.floor(max(a_lon, b_lon) / self.grid_size))
            min_gy = int(math.floor(min(a_lat, b_lat) / self.grid_size))
            max_gy = int(math.floor(max(a_lat, b_lat) / self.grid_size))

            for gx in range(min_gx, max_gx + 1):
                for gy in range(min_gy, max_gy + 1):
                    cell = (gx, gy)
                    if cell not in self.grid:
                        self.grid[cell] = []
                    self.grid[cell].append(i)

    def find_nearest_position(
        self, station_lat: float, station_lon: float
    ) -> Tuple[float, float]:
        """
        Locates the closest segment along the polyline using the spatial index.
        Returns:
            (min_distance_to_route_miles, distance_from_start_miles)
        """
        gx = int(math.floor(station_lon / self.grid_size))
        gy = int(math.floor(station_lat / self.grid_size))

        candidate_indices: List[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = (gx + dx, gy + dy)
                if cell in self.grid:
                    candidate_indices.extend(self.grid[cell])

        if not candidate_indices:
            return float("inf"), 0.0

        min_dist_to_route = float("inf")
        best_route_dist = 0.0
        seen: Set[int] = set()

        for idx in candidate_indices:
            if idx in seen:
                continue
            seen.add(idx)

            a_lon, a_lat = self.coordinates[idx]
            b_lon, b_lat = self.coordinates[idx + 1]

            t, proj_lat, proj_lon = project_point_to_segment(
                station_lat, station_lon,
                a_lat, a_lon,
                b_lat, b_lon
            )

            dist = haversine_distance_miles(station_lat, station_lon, proj_lat, proj_lon)
            if dist < min_dist_to_route:
                min_dist_to_route = dist
                seg_dist = self.cumulative_distances[idx + 1] - self.cumulative_distances[idx]
                best_route_dist = self.cumulative_distances[idx] + t * seg_dist

        return min_dist_to_route, best_route_dist
