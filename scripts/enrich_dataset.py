import urllib.request
import urllib.parse
import json
import csv
import io
import os
import time

os.makedirs("data", exist_ok=True)
cache_file = "data/cities_coordinates_cache.json"

city_coords = {}
if os.path.exists(cache_file):
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            city_coords = json.load(f)
    except Exception:
        city_coords = {}

if len(city_coords) < 1000:
    print("Fetching base US cities dataset...")
    url = "https://raw.githubusercontent.com/kelvins/US-Cities-Database/main/csv/us_cities.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
    for row in csv.DictReader(io.StringIO(content)):
        city = row["CITY"].strip().upper()
        state = row["STATE_CODE"].strip().upper()
        k = f"{city}|{state}"
        city_coords[k] = [float(row["LATITUDE"]), float(row["LONGITUDE"])]

extras = {
    "EVERGREEN|AL": [31.4338, -86.9544],
    "HENRICO|VA": [37.5385, -77.3486],
    "ELIZABETHPORT|NJ": [40.6559, -74.1957],
    "PORT WENTWORTH|GA": [32.1494, -81.1637],
    "BROOKPARK|OH": [41.4017, -81.8218],
    "UNIVERSITY PARK|IL": [41.4442, -87.6867],
}
for k, v in extras.items():
    city_coords[k] = v

with open(cache_file, "w", encoding="utf-8") as f:
    json.dump(city_coords, f, indent=2)

print(f"Total cities in cache: {len(city_coords)}")
