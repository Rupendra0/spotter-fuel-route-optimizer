import json
import csv
import os

cache_file = "data/cities_coordinates_cache.json"
with open(cache_file, "r", encoding="utf-8") as f:
    city_coords = json.load(f)

# Canadian cities mapping
ca_coords = {
    "CALGARY|AB": [51.0447, -114.0719],
    "EDMONTON|AB": [53.5461, -113.4938],
    "RED DEER|AB": [52.2681, -113.8112],
    "LETHBRIDGE|AB": [49.6956, -112.8451],
    "MEDICINE HAT|AB": [50.0417, -110.6775],
    "AIRDRIE|AB": [51.2917, -114.0144],
    "FORT MCMURRAY|AB": [56.7264, -111.3803],
    "FORT SASKATCHEWAN|AB": [53.7128, -113.2133],
    "NISKU|AB": [53.3378, -113.5358],
    "SHERWOOD PARK|AB": [53.5398, -113.3134],
    "WHITECOURT|AB": [54.1417, -115.6833],
    "EDSON|AB": [53.5828, -116.4356],
    "VALLEYVIEW|AB": [55.0711, -117.2792],
    "HANNA|AB": [51.6444, -111.9056],
    "NANTON|AB": [50.3508, -113.7744],
    "PRINCE GEORGE|BC": [53.9171, -122.7497],
    "KAMLOOPS|BC": [50.6745, -120.3273],
    "CHILLIWACK|BC": [49.1579, -121.9514],
    "ABBOTSFORD|BC": [49.0504, -122.3045],
    "COQUITLAM|BC": [49.2838, -122.7932],
    "FORT ST JOHN|BC": [56.2524, -120.8464],
    "FORT NELSON|BC": [58.8050, -122.6972],
    "KITWANGA|BC": [55.1000, -128.0000],
    "CRESTON|BC": [49.0955, -116.5135],
    "JAFFRAY|BC": [49.3667, -115.3000],
    "QUESNEL|BC": [52.9784, -122.4929],
    "WINNIPEG|MB": [49.8951, -97.1384],
    "HEADINGLEY|MB": [49.8731, -97.4069],
    "PORTAGE LA PRAIRIE|MB": [49.9728, -98.2919],
    "STE AGATHE|MB": [49.5636, -97.1772],
    "DUGALD|MB": [49.8917, -96.8417],
    "DARTMOUTH|NS": [44.6652, -63.5677],
    "BRAMPTON|ON": [43.7315, -79.7624],
    "HAMILTON|ON": [43.2557, -79.8711],
    "LONDON|ON": [42.9849, -81.2453],
    "KITCHENER|ON": [43.4516, -80.4925],
    "WINDSOR|ON": [42.3149, -83.0364],
    "BURLINGTON|ON": [43.3255, -79.7990],
    "BRANTFORD|ON": [43.1394, -80.2644],
    "SARNIA|ON": [42.9745, -82.4066],
    "KINGSTON|ON": [44.2312, -76.4860],
    "PICKERING|ON": [43.8384, -79.0868],
    "MILTON|ON": [43.5183, -79.8774],
    "ETOBICOKE|ON": [43.6205, -79.5132],
    "SAULT STE MARIE|ON": [46.5136, -84.3358],
    "FORT ERIE|ON": [42.9034, -78.9328],
    "COCHRANE|ON": [49.0667, -81.0167],
    "ORONO|ON": [43.9742, -78.6189],
    "TILBURY|ON": [42.2606, -82.4319],
    "OLDCASTLE|ON": [42.2333, -82.9333],
    "GLOUCESTER|ON": [45.4333, -75.6000],
    "HORNBY|ON": [43.5500, -79.9167],
    "INGLEWOOD|ON": [43.7833, -79.9333],
    "PASS LAKE|ON": [48.5500, -88.7500],
    "LANCASTER|ON": [45.1436, -74.4967],
    "AYR|ON": [43.2833, -80.4500],
    "COOKSTOWN|ON": [44.1833, -79.7000],
    "WYOMING|ON": [42.9500, -82.1167],
    "SAINT-LIBOIRE|QC": [45.6500, -72.7667],
    "MOOSE JAW|SK": [50.3933, -105.5519],
    "YORKTON|SK": [51.2139, -102.4628],
    "BALGONIE|SK": [50.5000, -104.2667],
    "DAVIDSON|SK": [51.2667, -105.9833],
    "WHITEHORSE|YT": [60.7212, -135.0568],
    "WATSON LAKE|YT": [60.0639, -128.7083]
}

city_coords.update(ca_coords)

with open(cache_file, "w", encoding="utf-8") as f:
    json.dump(city_coords, f, indent=2)

print("Coordinates cache updated with Canadian and US cities.")

# Read source CSV
with open("fuel-prices-for-be-assessment.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    raw_rows = list(reader)

print(f"Total raw CSV rows: {len(raw_rows)}")

# Deduplicate by OPIS Truckstop ID (or (name, address, city, state))
# For duplicates, select the entry with the LOWEST retail price.
deduped_stations = {}
for r in raw_rows:
    opis_id = r["OPIS Truckstop ID"].strip()
    name = r["Truckstop Name"].strip()
    address = r["Address"].strip()
    city = r["City"].strip()
    state = r["State"].strip()
    rack_id = r["Rack ID"].strip()
    try:
        price = float(r["Retail Price"].strip())
    except (ValueError, TypeError):
        continue

    # Station unique key
    key = opis_id if opis_id else f"{name}|{address}|{city}|{state}"

    if key not in deduped_stations or price < deduped_stations[key]["retail_price"]:
        # Find coordinates
        c_key = f"{city.upper()}|{state.upper()}"
        coords = city_coords.get(c_key)
        if not coords:
            # Fallback: try just state center or approximate
            print(f"Warning: No coords for {c_key}")
            continue

        deduped_stations[key] = {
            "opis_id": opis_id,
            "name": name,
            "address": address,
            "city": city,
            "state": state,
            "rack_id": rack_id,
            "retail_price": round(price, 4),
            "latitude": round(coords[0], 6),
            "longitude": round(coords[1], 6)
        }

stations_list = list(deduped_stations.values())
print(f"Deduplicated stations count: {len(stations_list)}")

# Write enriched CSV
enriched_csv_path = "data/fuel_stations_enriched.csv"
fieldnames = ["opis_id", "name", "address", "city", "state", "rack_id", "retail_price", "latitude", "longitude"]
with open(enriched_csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(stations_list)

print(f"Written enriched CSV to {enriched_csv_path}")

# Write enriched JSON seed
enriched_json_path = "data/fuel_stations_seed.json"
with open(enriched_json_path, "w", encoding="utf-8") as f:
    json.dump(stations_list, f, indent=2)

print(f"Written enriched JSON seed to {enriched_json_path}")
