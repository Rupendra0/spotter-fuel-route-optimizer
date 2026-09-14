from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
import requests
from routes.services.geocoding_service import GeocodingService
from routes.services.routing_service import RoutingService
from routes.exceptions import (
    GeocodingNotFoundError,
    NonUSALocationError,
    GeocodingServiceError,
    NoRouteFoundError,
    RoutingServiceError,
)


class GeocodingServiceTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.service = GeocodingService()

    @patch("requests.get")
    def test_geocode_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "34.052235",
                "lon": "-118.243683",
                "display_name": "Los Angeles, CA, USA",
                "address": {"country_code": "us"},
            }
        ]
        mock_get.return_value = mock_response

        res = self.service.geocode("Test City, ZZ")
        self.assertEqual(res["latitude"], 34.052235)
        self.assertEqual(res["longitude"], -118.243683)

        # Second call should hit cache and NOT call requests.get again
        res_cached = self.service.geocode("Test City, ZZ")
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(res_cached["latitude"], 34.052235)

    @patch("requests.get")
    def test_geocode_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        with self.assertRaises(GeocodingNotFoundError):
            self.service.geocode("NonExistentPlaceXYZ123, ZZ")

    @patch("requests.get")
    def test_geocode_non_usa_location(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "48.8566",
                "lon": "2.3522",
                "display_name": "Paris, France",
                "address": {"country_code": "fr"},
            }
        ]
        mock_get.return_value = mock_response

        with self.assertRaises(NonUSALocationError):
            self.service.geocode("Paris, France")

    @patch("requests.get")
    def test_geocode_timeout_error(self, mock_get):
        mock_get.side_effect = requests.Timeout("Connection timed out")
        with self.assertRaises(GeocodingServiceError):
            self.service.geocode("UnknownTownABC, ZZ")


class RoutingServiceTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.service = RoutingService()

    @patch("requests.get")
    def test_get_route_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 435000.0,  # ~270.3 miles
                    "duration": 14400.0,   # ~240 minutes
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-118.24, 34.05], [-115.14, 36.17]],
                    },
                }
            ],
        }
        mock_get.return_value = mock_response

        route = self.service.get_route(34.05, -118.24, 36.17, -115.14)
        self.assertAlmostEqual(route["distance_miles"], 270.3, delta=0.5)
        self.assertEqual(route["duration_minutes"], 240.0)

        # Verify caching: second call doesn't re-query
        route_cached = self.service.get_route(34.05, -118.24, 36.17, -115.14)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(route_cached["distance_miles"], route["distance_miles"])

    @patch("requests.get")
    def test_get_route_no_route(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "NoRoute", "routes": []}
        mock_get.return_value = mock_response

        with self.assertRaises(NoRouteFoundError):
            self.service.get_route(34.05, -118.24, 36.17, -115.14)

    @patch("requests.get")
    def test_get_route_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("Routing timeout")
        with self.assertRaises(RoutingServiceError):
            self.service.get_route(34.05, -118.24, 36.17, -115.14)
