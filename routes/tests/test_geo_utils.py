import math
import unittest
from routes.services.geo_utils import (
    haversine_distance_miles,
    compute_cumulative_polyline_distances,
    project_point_to_segment,
    calculate_route_bounding_box,
    SpatialPolylineIndex,
)


class GeoUtilsTestCase(unittest.TestCase):
    def test_haversine_distance_same_point(self):
        dist = haversine_distance_miles(34.0522, -118.2437, 34.0522, -118.2437)
        self.assertAlmostEqual(dist, 0.0, places=4)

    def test_haversine_distance_known_cities(self):
        # LA (34.0522, -118.2437) to Las Vegas (36.1699, -115.1398) is ~228 miles great-circle
        dist = haversine_distance_miles(34.0522, -118.2437, 36.1699, -115.1398)
        self.assertGreater(dist, 220.0)
        self.assertLess(dist, 240.0)

    def test_cumulative_polyline_distances(self):
        coords = [
            [-118.2437, 34.0522],
            [-117.0000, 34.5000],
            [-115.1398, 36.1699],
        ]
        cum_dist = compute_cumulative_polyline_distances(coords)
        self.assertEqual(len(cum_dist), 3)
        self.assertEqual(cum_dist[0], 0.0)
        self.assertGreater(cum_dist[1], 0.0)
        self.assertGreater(cum_dist[2], cum_dist[1])

    def test_project_point_to_segment(self):
        # Segment along equator from lon 0 to 10 at lat 0
        t, p_lat, p_lon = project_point_to_segment(1.0, 5.0, 0.0, 0.0, 0.0, 10.0)
        self.assertAlmostEqual(t, 0.5, places=2)
        self.assertAlmostEqual(p_lat, 0.0, places=2)
        self.assertAlmostEqual(p_lon, 5.0, places=2)

    def test_calculate_bounding_box(self):
        coords = [[-118.0, 34.0], [-115.0, 36.0]]
        min_lat, max_lat, min_lon, max_lon = calculate_route_bounding_box(coords, buffer_miles=15.0)
        self.assertLess(min_lat, 34.0)
        self.assertGreater(max_lat, 36.0)
        self.assertLess(min_lon, -118.0)
        self.assertGreater(max_lon, -115.0)

    def test_spatial_polyline_index(self):
        coords = [
            [-118.2437, 34.0522],
            [-116.5000, 35.0000],
            [-115.1398, 36.1699],
        ]
        index = SpatialPolylineIndex(coords, grid_size_deg=0.3)
        # Query point close to middle vertex
        min_dist, route_dist = index.find_nearest_position(35.0, -116.5)
        self.assertLess(min_dist, 5.0)
        self.assertGreater(route_dist, 0.0)
