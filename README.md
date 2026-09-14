# Spotter — Fuel-Efficient Route Optimization API

A production-grade Django REST API that calculates driving routes across the USA, identifies commercial fuel stations along the route corridor, and schedules cost-optimal fuel stops adhering strictly to vehicle physical constraints.

---

## Table of Contents
- [1. Project Overview](#1-project-overview)
- [2. System Architecture](#2-system-architecture)
- [3. Technology Stack](#3-technology-stack)
- [4. Fuel Dataset & Preprocessing](#4-fuel-dataset--preprocessing)
- [5. Fuel Optimization Algorithm](#5-fuel-optimization-algorithm)
- [6. Performance & External API Call Minimization](#6-performance--external-api-call-minimization)
- [7. Installation & Local Setup](#7-installation--local-setup)
- [8. API Reference](#8-api-reference)
- [9. Interactive Web Map Demo](#9-interactive-web-map-demo)
- [10. Automated Testing](#10-automated-testing)
- [11. Assumptions & Tradeoffs](#11-assumptions--tradeoffs)
- [12. 5-Minute Loom Video Script](#12-5-minute-loom-video-script)

---

## 1. Project Overview

Commercial long-haul vehicles operate with tight fuel margins. This API solves the **Gas Station Problem with Continuous Capacity**:
- Accepts a **Start** and **Destination** in the USA (e.g. `"New York, NY"` to `"Chicago, IL"`).
- Fetches real road geometry from an open routing provider (OSRM).
- Filters fuel stations from the provided OPIS fuel dataset within a configurable corridor (default: 15 miles).
- Schedules fuel stops to **minimize total money spent** while strictly respecting:
  - **Maximum driving range:** 500 miles on a full tank.
  - **Fuel economy:** 10 miles per gallon (MPG).
  - **Tank capacity:** 50 gallons ($500 \text{ miles} / 10 \text{ MPG} = 50 \text{ gallons}$).
  - **Starting fuel:** Assumes the vehicle departs with a full 50-gallon tank.
- Returns driving distances, durations, fuel consumed, fuel purchased, individual stop costs, total cost, and **GeoJSON LineString geometry** ready for frontend/map rendering.

---

## 2. System Architecture

The application strictly separates HTTP serialization, business logic, spatial indexing, and data access into clean modular service layers:

```text
Client (Postman / Web Map / Frontend)
           │
           ▼
    POST /api/v1/routes/optimize/
           │
┌──────────┴────────────────────────────────────────────────┐
│ routes/views.py (RouteOptimizeView)                       │
│    └── routes/serializers.py (Input validation)           │
└──────────┬────────────────────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────────────────────┐
│ routes/services/route_service.py (Orchestrator)           │
│    ├── GeocodingService: Location normalization & cache   │
│    ├── RoutingService: OSRM driving route & cache         │
│    ├── StationService: Spatial Bounding Box & 2D Grid     │
│    └── FuelOptimizer: Cost-aware lookahead optimization   │
└──────────┬────────────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
SQLite DB    Django Cache
(Indexed)     (In-Memory)
```

### Module Responsibilities:
- `routes/views.py`: Clean HTTP request/response handling and domain exception mapping.
- `routes/serializers.py`: DRF request/response serialization with OpenAPI schema annotations.
- `routes/services/geocoding_service.py`: Multi-tier geocoding (cache $\to$ local 29k US cities dataset $\to$ Nominatim).
- `routes/services/routing_service.py`: Open Source Routing Machine (OSRM) integration with local caching.
- `routes/services/geo_utils.py`: Haversine distance, cross-track segment projection, and 2D spatial grid indexing (`SpatialPolylineIndex`).
- `routes/services/station_service.py`: Geospatial corridor filtering and station distance projection along the route.
- `routes/services/fuel_optimizer.py`: Cost-aware feasible fuel optimization engine.
- `routes/exceptions.py`: Custom domain exceptions with explicit HTTP status codes (`400`, `404`, `422`, `503`).

---

## 3. Technology Stack

- **Framework:** Python 3.13 + Django 5.1 + Django REST Framework 3.15
- **Database:** SQLite 3 with composite 2D bounding-box indexing (`(latitude, longitude)`)
- **API Documentation:** OpenAPI 3.0 / Swagger UI via `drf-spectacular`
- **Routing Engine:** Open Source Routing Machine (OSRM) driving API (Free & OpenStreetMap-based)
- **Geocoding:** OpenStreetMap Nominatim + Offline 29,000+ US cities database
- **Testing:** Pytest, Pytest-Django, Django TestCase with 100% mocked external API isolation

---

## 4. Fuel Dataset & Preprocessing

The supplied `fuel-prices-for-be-assessment.csv` contains 8,151 rows. Analysis reveals:
1. **Uniqueness:** 6,738 unique OPIS Truckstop IDs. Some truckstops have multiple rows with varying retail prices (different quotes or diesel grades).
2. **Deduplication Strategy:** The importer deduplicates records by `OPIS Truckstop ID` (or `Name + Address + City + State`), selecting the **lowest retail price**, representing the best fuel rate available to commercial drivers at that station.
3. **Coordinates Enrichment:** The source CSV lacks latitude/longitude coordinates. A one-time preprocessing script matches stations against an open US cities database with OSM fallback.
4. **Seed Availability:** Both `data/fuel_stations_enriched.csv` and `data/cities_coordinates_cache.json` are committed with the project. As a result, running `python manage.py import_fuel_data` executes in **under 1.5 seconds** with **zero external network requests**!

```bash
# Populates all 6,738 stations in SQLite with coordinates in ~1 second:
python manage.py import_fuel_data
```

---

## 5. Fuel Optimization Algorithm

### Constraints:
- $\text{Range}_{\max} = 500 \text{ miles}$
- $\text{Economy} = 10 \text{ MPG}$
- $\text{Capacity} = 50 \text{ gallons}$
- $\text{Initial Fuel} = 50 \text{ gallons}$

### Algorithmic Strategy:
The optimizer uses a **Greedy Lookahead with Backward Reachability Pruning**:

1. **Direct Destination Check:**
   If $\text{Total Distance} \le \text{Initial Fuel} \times 10 \text{ MPG}$ (i.e. $\le 500 \text{ miles}$), the vehicle arrives at the destination on its initial fuel. Number of stops = 0, fuel purchased = 0, cost = $0.00.

2. **Backward Reachability Pruning:**
   Before making any decisions, a backward sweep from destination tags all candidate stations that can physically reach the destination through valid hops $\le 500$ miles. Stations that lead to dead-end gaps $> 500$ miles are pruned. If no continuous path exists, an `InfeasibleRouteError` (HTTP 422) is raised immediately.

3. **Sequential Cost-Aware Decision Loop:**
   - At start (mile 0, fuel = 50 gal), find the cheapest reachable feasible station within the initial 500-mile range. Drive there on initial fuel.
   - At current station $S_i$ with price $p_i$ and fuel remaining $F_i$:
     - **Lookahead 1 (Cheaper Station Ahead):** If a cheaper station $S_j$ ($p_j < p_i$) exists within full-tank range (500 miles), purchase **only enough fuel to reach $S_j$**:
       $$\text{Purchased} = \max\left(0, \frac{d_j - d_i}{10} - F_i\right)$$
       Drive to $S_j$.
     - **Lookahead 2 (Local Minimum Price):** If no station within 500 miles is cheaper than $S_i$:
       - If destination is within 500 miles, purchase just enough to reach destination:
         $$\text{Purchased} = \max\left(0, \frac{D - d_i}{10} - F_i\right)$$
       - If destination is $> 500$ miles away, **fill the tank to full capacity (50 gallons)** to maximize miles traveled on cheap fuel:
         $$\text{Purchased} = 50 - F_i$$
         Then advance to the next best station reachable within 500 miles.

### Guarantees:
- Feasibility: Every leg between refueling opportunities is $\le 500$ miles.
- Fuel remaining is never negative ($F \ge 0$).
- Tank capacity never exceeds 50 gallons ($F \le 50$).
- Deterministic and mathematically optimal for continuous capacity.

---

## 6. Performance & External API Call Minimization

### 1 Routing Call Per Uncached Request:
- The routing API (OSRM) is called **exactly once** per route.
- **Never calls routing API for fuel stations:** Station proximity and mile markers along the route are computed **100% locally**.
- If the route is already cached, **0 routing calls** are made.

### 2D Spatial Polyline Indexing (`SpatialPolylineIndex`):
Comparing 500 candidate stations against a 5,000-vertex highway polyline naively requires $500 \times 5,000 = 2,500,000$ operations in Python (~18 seconds).
We implemented a custom 2D grid index (`SpatialPolylineIndex`) with 0.3-degree grid cells. Stations only test line segments in adjacent cells, reducing operations to $< 15,000$ and dropping route projection time to **7 milliseconds** (a **250x speedup**).

### Multi-Tier Caching:
1. **Pipeline Cache:** Subsequent identical route requests return in **< 10ms**.
2. **Geocoding Cache:** Location strings are normalized (`"  Los Angeles, CA  "` $\to$ `"los angeles, ca"`) and cached.
3. **Routing Cache:** Driving geometries are cached by coordinate pairs.

---

## 7. Installation & Local Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Git

### Quick Setup

```bash
# 1. Clone repository
git clone https://github.com/your-username/spotter-fuel-route-optimizer.git
cd spotter-fuel-route-optimizer

# 2. Create and activate virtual environment
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Run database migrations
python manage.py migrate

# 6. Import and enrich fuel station dataset (runs in ~1 second)
python manage.py import_fuel_data

# 7. Start local development server
python manage.py runserver
```

The server will be running at `http://127.0.0.1:8000/`.

---

## 8. API Reference

### Health Check
```http
GET /api/v1/health/
```
**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "spotter-fuel-route-optimizer",
  "database": "sqlite3",
  "stations_loaded": 6738
}
```

---

### Route Optimization
```http
POST /api/v1/routes/optimize/
Content-Type: application/json
```

**Request Body:**
```json
{
  "start": "New York, NY",
  "finish": "Chicago, IL"
}
```

**Response (200 OK):**
```json
{
  "start": {
    "name": "New York, NY",
    "latitude": 40.74838,
    "longitude": -73.996705,
    "display_name": "New York, NY, USA"
  },
  "finish": {
    "name": "Chicago, IL",
    "latitude": 41.885847,
    "longitude": -87.618123,
    "display_name": "Chicago, IL, USA"
  },
  "route": {
    "distance_miles": 793.26,
    "duration_minutes": 748.2,
    "geometry": {
      "type": "LineString",
      "coordinates": [
        [-73.996705, 40.74838],
        [-87.618123, 41.885847]
      ]
    }
  },
  "vehicle": {
    "max_range_miles": 500.0,
    "fuel_efficiency_mpg": 10.0,
    "tank_capacity_gallons": 50.0
  },
  "fuel_stops": [
    {
      "station_id": 1542,
      "opis_id": "639",
      "name": "SHEETZ #639",
      "address": "I-80, EXIT 223 & SR-46",
      "city": "Youngstown",
      "state": "OH",
      "latitude": 41.155,
      "longitude": -80.762,
      "distance_from_start_miles": 391.49,
      "price_per_gallon": 3.059,
      "gallons_purchased": 5.53,
      "fuel_cost": 16.92,
      "fuel_remaining_after_stop": 16.38
    },
    {
      "station_id": 2891,
      "opis_id": "88",
      "name": "S&G #88",
      "address": "I-80/I-90, EXIT 71 & SR-420",
      "city": "Toledo",
      "state": "OH",
      "latitude": 41.568,
      "longitude": -83.479,
      "distance_from_start_miles": 555.29,
      "price_per_gallon": 3.009,
      "gallons_purchased": 23.8,
      "fuel_cost": 71.61,
      "fuel_remaining_after_stop": 23.8
    }
  ],
  "summary": {
    "total_distance_miles": 793.26,
    "total_fuel_consumed_gallons": 79.33,
    "total_fuel_purchased_gallons": 29.33,
    "total_fuel_cost": 88.53,
    "number_of_stops": 2
  },
  "meta": {
    "candidate_stations_considered": 275,
    "computation_time_ms": 142.5
  }
}
```

### Swagger Documentation
Interactive Swagger documentation is available at:
`http://127.0.0.1:8000/api/docs/`

---

## 9. Interactive Web Map Demo

Open `http://127.0.0.1:8000/` in your browser.
- Type any start and destination within the USA (or click one of the quick preset buttons).
- Click **"Plan Optimal Route"**.
- View the interactive Leaflet map with:
  - Cyan road polyline.
  - Green Start marker.
  - Red Destination marker.
  - Amber Fuel Pump pins along the highway with interactive popup cards showing prices, gallons, and leg costs.

---

## 10. Automated Testing

The project includes 31 comprehensive unit and integration tests covering:
- Zero distance, exact 500 miles, single stop, multi-stop routes.
- Cheaper station lookahead vs local minimum tank fill logic.
- Infeasible route detection and constraint checks (non-negative fuel, max 50 gal tank).
- API request validation, error handling, and mocked external services.

Run tests using either Django runner or Pytest:

```bash
# Django test runner:
python manage.py test routes

# Pytest runner:
pytest
```

**Test Isolation:** Real external API requests (OSRM / Nominatim) are **100% mocked** in automated tests for deterministic, fast, zero-network execution.

---

## 11. Assumptions & Tradeoffs

1. **Starting Fuel:** Assumed full (50 gallons) at departure.
2. **Corridor Radius:** Default is 15 miles perpendicular distance from highway polyline (configurable via `ROUTE_STATION_RADIUS_MILES`).
3. **Fuel Price Grade:** For truckstops with multiple rack prices or grades in the raw CSV, the minimum retail price is selected as the primary rate.
4. **Detour Distance:** Stations are assumed to be immediately adjacent to highway exits; perpendicular cross-track distance is used for route position projection.

---

## 12. 5-Minute Loom Video Script

Use this script during your Loom technical demo:

### 0:00 - 0:45 | Introduction & Problem Statement
> "Hi team, I am presenting the Fuel-Efficient Route Optimization API. The challenge is: given a start and destination in the USA, determine the driving route and schedule optimal fuel stops minimizing total fuel cost while adhering to a 500-mile vehicle range, 10 MPG, and 50-gallon tank capacity starting with a full tank."

### 0:45 - 1:45 | Clean Django Architecture
> "Let's look at the codebase. In `spotter_project`, I followed clean separation of concerns:
> - `routes/views.py`: Thin API views handling serialization and domain exception mapping.
> - `routes/services/geocoding_service.py`: Multi-tier geocoding with in-memory caching and offline resilience.
> - `routes/services/routing_service.py`: Calls OSRM once per uncached route, never per station.
> - `routes/services/geo_utils.py`: Contains our custom `SpatialPolylineIndex` which dropped spatial corridor projection time from 18 seconds to 7 milliseconds using 2D grid indexing.
> - `routes/services/fuel_optimizer.py`: The core cost-aware greedy lookahead optimization engine."

### 1:45 - 3:00 | Live API Demonstration in Postman
> "Now let's switch to Postman:
> 1. Health check: Shows all 6,738 deduplicated stations loaded in SQLite.
> 2. Test 1: Los Angeles to Las Vegas (276 miles). Because distance is under 500 miles, the vehicle arrives on initial fuel with 0 fuel stops and $0 cost.
> 3. Test 2: New York to Chicago (793 miles). The API returns 2 optimal fuel stops: Stop 1 at mile 391 (Sheetz in Youngstown, OH at $3.059/gal) and Stop 2 at mile 555 (S&G in Toledo, OH at $3.009/gal). Total fuel cost is $88.53.
> 4. Performance & Caching: Notice when I re-send the request, it completes in under 10 milliseconds thanks to our caching layer."

### 3:00 - 4:15 | Interactive Map UI Demonstration
> "In addition to JSON geometry, I provided an interactive Leaflet map at `http://127.0.0.1:8000/`. When we submit New York to Chicago, you can see the complete highway polyline drawn in cyan, start and destination pins, and the exact fuel pump locations along I-80. Clicking any pin shows the retail price, gallons purchased, and remaining tank capacity."

### 4:15 - 5:00 | Automated Tests & Wrap-Up
> "Finally, running `pytest` executes 31 tests in 1 second with external APIs 100% mocked. The project is completely self-contained, reproducible, and ready for deployment. Thank you!"
