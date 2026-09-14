import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spotter_project.settings")
django.setup()

import json
from django.test import Client

client = Client()

# Health check
res_health = client.get("/api/v1/health/")
print("Health Check Status:", res_health.status_code)
print("Health Check Data:", res_health.json())

# Test Route 1: LA to Las Vegas (~270 miles)
print("\n--- Testing Route 1: Los Angeles, CA -> Las Vegas, NV ---")
res_la_lv = client.post(
    "/api/v1/routes/optimize/",
    data=json.dumps({"start": "Los Angeles, CA", "finish": "Las Vegas, NV"}),
    content_type="application/json",
)
print("Status:", res_la_lv.status_code)
data_la_lv = res_la_lv.json()
print("Distance:", data_la_lv.get("route", {}).get("distance_miles"), "mi")
print("Fuel consumed:", data_la_lv.get("summary", {}).get("total_fuel_consumed_gallons"), "gal")
print("Stops count:", data_la_lv.get("summary", {}).get("number_of_stops"))
print("Fuel cost: $", data_la_lv.get("summary", {}).get("total_fuel_cost"))

# Test Route 2: NYC to Chicago (~790 miles)
print("\n--- Testing Route 2: New York, NY -> Chicago, IL ---")
res_ny_chi = client.post(
    "/api/v1/routes/optimize/",
    data=json.dumps({"start": "New York, NY", "finish": "Chicago, IL"}),
    content_type="application/json",
)
print("Status:", res_ny_chi.status_code)
data_ny_chi = res_ny_chi.json()
print("Distance:", data_ny_chi.get("route", {}).get("distance_miles"), "mi")
print("Fuel consumed:", data_ny_chi.get("summary", {}).get("total_fuel_consumed_gallons"), "gal")
print("Stops count:", data_ny_chi.get("summary", {}).get("number_of_stops"))
print("Fuel cost: $", data_ny_chi.get("summary", {}).get("total_fuel_cost"))
for idx, stop in enumerate(data_ny_chi.get("fuel_stops", [])):
    print(f"  Stop {idx+1}: {stop['name']} ({stop['city']}, {stop['state']}) at mile {stop['distance_from_start_miles']}: {stop['gallons_purchased']} gal @ ${stop['price_per_gallon']}/gal (${stop['fuel_cost']})")
