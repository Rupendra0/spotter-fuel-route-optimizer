import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from routes.models import FuelStation


class RouteOptimizationApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.optimize_url = reverse("route-optimize")
        self.health_url = reverse("health-check")
        self.map_url = reverse("map-demo")

        # Create test fuel station
        FuelStation.objects.create(
            opis_id="TEST001",
            name="Test Petro Stop",
            address="I-15 Exit 100",
            city="Barstow",
            state="CA",
            retail_price=3.199,
            latitude=34.898,
            longitude=-117.022,
        )

    def test_health_check_endpoint(self):
        response = self.client.get(self.health_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["stations_loaded"], 1)

    def test_map_demo_endpoint(self):
        response = self.client.get(self.map_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spotter Route Optimizer")
        self.assertContains(response, "leaflet")

    def test_missing_start_parameter(self):
        response = self.client.post(
            self.optimize_url,
            data=json.dumps({"finish": "Las Vegas, NV"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("start", response.json()["details"])

    def test_missing_finish_parameter(self):
        response = self.client.post(
            self.optimize_url,
            data=json.dumps({"start": "Los Angeles, CA"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("finish", response.json()["details"])

    def test_blank_location_parameters(self):
        response = self.client.post(
            self.optimize_url,
            data=json.dumps({"start": "   ", "finish": "Las Vegas, NV"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_identical_start_and_finish(self):
        response = self.client.post(
            self.optimize_url,
            data=json.dumps({"start": "Los Angeles, CA", "finish": "Los Angeles, CA"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("routes.services.geocoding_service.GeocodingService.geocode")
    @patch("routes.services.routing_service.RoutingService.get_route")
    def test_successful_route_optimization(self, mock_get_route, mock_geocode):
        # Mock geocoding
        mock_geocode.side_effect = [
            {"name": "Los Angeles, CA", "latitude": 34.05, "longitude": -118.24, "display_name": "LA"},
            {"name": "Las Vegas, NV", "latitude": 36.17, "longitude": -115.14, "display_name": "Vegas"},
        ]
        # Mock routing
        mock_get_route.return_value = {
            "distance_miles": 270.0,
            "duration_minutes": 250.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-118.24, 34.05], [-117.02, 34.90], [-115.14, 36.17]],
            },
        }

        response = self.client.post(
            self.optimize_url,
            data=json.dumps({"start": "Los Angeles, CA", "finish": "Las Vegas, NV"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("start", data)
        self.assertIn("finish", data)
        self.assertIn("route", data)
        self.assertIn("vehicle", data)
        self.assertIn("fuel_stops", data)
        self.assertIn("summary", data)

        self.assertEqual(data["route"]["distance_miles"], 270.0)
        self.assertEqual(data["vehicle"]["max_range_miles"], 500.0)
        self.assertEqual(data["summary"]["total_distance_miles"], 270.0)
        self.assertEqual(data["summary"]["total_fuel_consumed_gallons"], 27.0)

    @patch("routes.services.geocoding_service.GeocodingService.geocode")
    def test_non_usa_location_returns_400(self, mock_geocode):
        from routes.exceptions import NonUSALocationError
        mock_geocode.side_effect = NonUSALocationError("Location is outside the USA.")

        response = self.client.post(
            self.optimize_url,
            data=json.dumps({"start": "Toronto, ON", "finish": "Las Vegas, NV"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "non_usa_location")

    @patch("routes.services.geocoding_service.GeocodingService.geocode")
    def test_location_not_found_returns_404(self, mock_geocode):
        from routes.exceptions import GeocodingNotFoundError
        mock_geocode.side_effect = GeocodingNotFoundError("Location not found.")

        response = self.client.post(
            self.optimize_url,
            data=json.dumps({"start": "UnknownPlace999", "finish": "Las Vegas, NV"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "location_not_found")
