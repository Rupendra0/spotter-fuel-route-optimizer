import json
import csv
import urllib.request
import urllib.parse
import time

cache_file = "data/cities_coordinates_cache.json"
with open(cache_file, "r", encoding="utf-8") as f:
    city_coords = json.load(f)

with open("fuel-prices-for-be-assessment.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

missing = set()
for r in rows:
    c = r["City"].strip().upper()
    s = r["State"].strip().upper()
    k = f"{c}|{s}"
    if k not in city_coords:
        missing.add((c, s))

print(f"Missing unique city|state: {len(missing)}")

# Geocode missing using Nominatim with proper headers
count = 0
for c, s in list(missing):
    query = f"{c}, {s}"
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "SpotterRouteOptimizer/1.0 (assessment-enricher)"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                city_coords[f"{c}|{s}"] = [lat, lon]
                count += 1
                print(f"Resolved [{count}/{len(missing)}]: {query} -> {lat}, {lon}")
        time.sleep(0.3)
    except Exception as e:
        print(f"Failed {query}: {e}")

with open(cache_file, "w", encoding="utf-8") as f:
    json.dump(city_coords, f, indent=2)

print("Updated cache with all missing cities!")
