import unittest
from routes.exceptions import InfeasibleRouteError
from routes.services.fuel_optimizer import FuelOptimizer


class FuelOptimizerTestCase(unittest.TestCase):
    def setUp(self):
        self.optimizer = FuelOptimizer(
            max_range_miles=500.0,
            fuel_economy_mpg=10.0,
            tank_capacity_gallons=50.0,
            initial_fuel_gallons=50.0,
        )

    def test_zero_distance_route(self):
        result = self.optimizer.optimize(0.0, [])
        self.assertEqual(result["summary"]["number_of_stops"], 0)
        self.assertEqual(result["summary"]["total_fuel_consumed_gallons"], 0.0)
        self.assertEqual(result["summary"]["total_fuel_purchased_gallons"], 0.0)
        self.assertEqual(result["summary"]["total_fuel_cost"], 0.0)
        self.assertEqual(len(result["fuel_stops"]), 0)

    def test_route_under_500_miles_no_stops(self):
        # 350 miles with full tank needs 35 gallons, 0 stops
        stations = [
            {"station_id": 1, "name": "Stop A", "distance_from_start_miles": 150.0, "retail_price": 3.50},
            {"station_id": 2, "name": "Stop B", "distance_from_start_miles": 280.0, "retail_price": 3.20},
        ]
        result = self.optimizer.optimize(350.0, stations)
        self.assertEqual(result["summary"]["number_of_stops"], 0)
        self.assertEqual(result["summary"]["total_fuel_consumed_gallons"], 35.0)
        self.assertEqual(result["summary"]["total_fuel_purchased_gallons"], 0.0)
        self.assertEqual(result["summary"]["total_fuel_cost"], 0.0)

    def test_route_exact_500_miles_no_stops(self):
        stations = [
            {"station_id": 1, "name": "Stop A", "distance_from_start_miles": 250.0, "retail_price": 3.50},
        ]
        result = self.optimizer.optimize(500.0, stations)
        self.assertEqual(result["summary"]["number_of_stops"], 0)
        self.assertEqual(result["summary"]["total_fuel_consumed_gallons"], 50.0)
        self.assertEqual(result["summary"]["total_fuel_cost"], 0.0)

    def test_route_over_500_miles_single_stop(self):
        # 700 miles, stop at mile 350 with price 3.20
        stations = [
            {"station_id": 1, "name": "Stop A", "distance_from_start_miles": 350.0, "retail_price": 3.20},
        ]
        result = self.optimizer.optimize(700.0, stations)
        self.assertEqual(result["summary"]["number_of_stops"], 1)
        self.assertEqual(result["summary"]["total_distance_miles"], 700.0)
        self.assertEqual(result["summary"]["total_fuel_consumed_gallons"], 70.0)
        # Vehicle arrived at mile 350 with 15 gal (50 - 35).
        # To reach destination at 700 mi (350 mi away = 35 gal), it purchases 20 gal (35 - 15).
        stop = result["fuel_stops"][0]
        self.assertEqual(stop["gallons_purchased"], 20.0)
        self.assertEqual(stop["fuel_cost"], 64.0)  # 20 * 3.20
        self.assertEqual(stop["fuel_remaining_after_stop"], 35.0)

    def test_cheaper_station_ahead_purchases_only_needed(self):
        # Stop 1 at 300 mi ($3.80), Stop 2 at 450 mi ($3.10), Dest at 750 mi
        stations = [
            {"station_id": 1, "name": "Expensive Stop", "distance_from_start_miles": 300.0, "retail_price": 3.80},
            {"station_id": 2, "name": "Cheap Stop", "distance_from_start_miles": 450.0, "retail_price": 3.10},
        ]
        result = self.optimizer.optimize(750.0, stations)
        # At start: cheapest station within 500 mi is Cheap Stop at 450 mi ($3.10)!
        # Vehicle skips Expensive Stop and fuels at Cheap Stop directly!
        self.assertEqual(result["summary"]["number_of_stops"], 1)
        stop = result["fuel_stops"][0]
        self.assertEqual(stop["name"], "Cheap Stop")
        self.assertEqual(stop["distance_from_start_miles"], 450.0)

    def test_multi_stop_long_route(self):
        # 1400 miles route
        stations = [
            {"station_id": 1, "name": "Stop 1", "distance_from_start_miles": 400.0, "retail_price": 3.40},
            {"station_id": 2, "name": "Stop 2", "distance_from_start_miles": 800.0, "retail_price": 3.20},
            {"station_id": 3, "name": "Stop 3", "distance_from_start_miles": 1200.0, "retail_price": 3.50},
        ]
        result = self.optimizer.optimize(1400.0, stations)
        self.assertGreaterEqual(result["summary"]["number_of_stops"], 2)
        self.assertEqual(result["summary"]["total_fuel_consumed_gallons"], 140.0)
        # Verify physical constraints
        for stop in result["fuel_stops"]:
            self.assertLessEqual(stop["fuel_remaining_after_stop"], 50.0)
            self.assertGreaterEqual(stop["fuel_remaining_after_stop"], 0.0)
            self.assertGreaterEqual(stop["gallons_purchased"], 0.0)

    def test_infeasible_gap_between_stations_raises_error(self):
        # Gap of 600 miles between Stop 1 (300) and Stop 2 (900)
        stations = [
            {"station_id": 1, "name": "Stop 1", "distance_from_start_miles": 300.0, "retail_price": 3.00},
            {"station_id": 2, "name": "Stop 2", "distance_from_start_miles": 900.0, "retail_price": 3.00},
        ]
        with self.assertRaises(InfeasibleRouteError):
            self.optimizer.optimize(1000.0, stations)

    def test_infeasible_start_gap_raises_error(self):
        # First station at 550 miles (unreachable on 50 gal / 500 mi range)
        stations = [
            {"station_id": 1, "name": "Stop 1", "distance_from_start_miles": 550.0, "retail_price": 3.00},
        ]
        with self.assertRaises(InfeasibleRouteError):
            self.optimizer.optimize(800.0, stations)

    def test_infeasible_empty_stations_raises_error(self):
        with self.assertRaises(InfeasibleRouteError):
            self.optimizer.optimize(800.0, [])
