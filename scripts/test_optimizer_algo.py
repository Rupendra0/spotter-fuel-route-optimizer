def optimize_fuel(total_distance, stations, max_range=500.0, mpg=10.0, tank_capacity=50.0, initial_fuel=50.0):
    # Step 1: Destination reachable without stopping
    if total_distance <= initial_fuel * mpg:
        consumed = round(total_distance / mpg, 2)
        return {
            "fuel_stops": [],
            "total_distance_miles": total_distance,
            "total_fuel_consumed_gallons": consumed,
            "total_fuel_purchased_gallons": 0.0,
            "total_fuel_cost": 0.0,
            "number_of_stops": 0,
        }

    # Step 2: Backward reachability filter
    valid_stations = [s for s in stations if 0 < s["dist"] < total_distance]
    valid_stations.sort(key=lambda s: s["dist"])

    # Backward pass to check reachability to destination
    can_reach_dest = set()
    for i in reversed(range(len(valid_stations))):
        st = valid_stations[i]
        if total_distance - st["dist"] <= max_range:
            can_reach_dest.add(i)
        else:
            for j in range(i + 1, len(valid_stations)):
                if j in can_reach_dest and valid_stations[j]["dist"] - st["dist"] <= max_range:
                    can_reach_dest.add(i)
                    break

    feasible_stations = [valid_stations[i] for i in sorted(can_reach_dest)]
    if not feasible_stations:
        raise ValueError("Infeasible: no station can reach destination.")

    # Check if start can reach at least one feasible station
    start_reachable = [s for s in feasible_stations if s["dist"] <= initial_fuel * mpg]
    if not start_reachable:
        raise ValueError("Infeasible: start cannot reach any station that can reach destination.")

    # Step 3: Simulation loop
    curr_dist = 0.0
    curr_fuel = initial_fuel
    stops = []

    # First stop from start: pick cheapest feasible station within initial range
    first_stop = min(start_reachable, key=lambda s: (s["price"], -s["dist"]))
    burn = first_stop["dist"] / mpg
    curr_fuel -= burn
    curr_dist = first_stop["dist"]
    curr_station = first_stop

    while curr_dist + curr_fuel * mpg < total_distance:
        # We are at curr_station (curr_dist, price p_curr)
        p_curr = curr_station["price"]
        max_reach_dist = curr_dist + max_range

        # Check if destination is reachable with a full tank
        if total_distance <= max_reach_dist:
            # Check if any cheaper station exists before destination
            cheaper_ahead = [
                s for s in feasible_stations
                if curr_dist < s["dist"] < total_distance and s["price"] < p_curr
            ]
            if cheaper_ahead:
                # Go to the first cheaper station
                next_st = cheaper_ahead[0]
                needed = (next_st["dist"] - curr_dist) / mpg
                purchase = max(0.0, needed - curr_fuel)
                purchase = round(purchase, 2)
                cost = round(purchase * p_curr, 2)
                curr_fuel = round(curr_fuel + purchase, 2)
                stops.append({
                    "station": curr_station["name"],
                    "dist": curr_dist,
                    "price": p_curr,
                    "gallons_purchased": purchase,
                    "cost": cost,
                    "fuel_after": curr_fuel,
                })
                # Drive to next_st
                curr_fuel -= needed
                curr_dist = next_st["dist"]
                curr_station = next_st
                continue
            else:
                # No cheaper station before destination. Buy just enough to reach destination!
                needed = (total_distance - curr_dist) / mpg
                purchase = max(0.0, needed - curr_fuel)
                purchase = min(tank_capacity - curr_fuel, purchase)
                purchase = round(purchase, 2)
                cost = round(purchase * p_curr, 2)
                curr_fuel = round(curr_fuel + purchase, 2)
                stops.append({
                    "station": curr_station["name"],
                    "dist": curr_dist,
                    "price": p_curr,
                    "gallons_purchased": purchase,
                    "cost": cost,
                    "fuel_after": curr_fuel,
                })
                # Arrive at destination
                curr_fuel -= needed
                curr_dist = total_distance
                break

        # Destination is not reachable with full tank (> 500 mi away)
        # Look for cheaper stations within full tank range
        cheaper_within_range = [
            s for s in feasible_stations
            if curr_dist < s["dist"] <= max_reach_dist and s["price"] < p_curr
        ]
        if cheaper_within_range:
            # Drive to the first cheaper station
            next_st = cheaper_within_range[0]
            needed = (next_st["dist"] - curr_dist) / mpg
            purchase = max(0.0, needed - curr_fuel)
            purchase = min(tank_capacity - curr_fuel, purchase)
            purchase = round(purchase, 2)
            cost = round(purchase * p_curr, 2)
            curr_fuel = round(curr_fuel + purchase, 2)
            stops.append({
                "station": curr_station["name"],
                "dist": curr_dist,
                "price": p_curr,
                "gallons_purchased": purchase,
                "cost": cost,
                "fuel_after": curr_fuel,
            })
            curr_fuel -= needed
            curr_dist = next_st["dist"]
            curr_station = next_st
        else:
            # Current station is the cheapest within 500 miles. Fill up tank!
            purchase = round(tank_capacity - curr_fuel, 2)
            cost = round(purchase * p_curr, 2)
            curr_fuel = round(curr_fuel + purchase, 2)
            stops.append({
                "station": curr_station["name"],
                "dist": curr_dist,
                "price": p_curr,
                "gallons_purchased": purchase,
                "cost": cost,
                "fuel_after": curr_fuel,
            })
            # From full tank, pick the next best station within 500 miles
            forward_reach = [
                s for s in feasible_stations
                if curr_dist < s["dist"] <= curr_dist + max_range
            ]
            if not forward_reach:
                raise ValueError("Infeasible forward step.")
            # Pick cheapest forward station
            next_st = min(forward_reach, key=lambda s: (s["price"], -s["dist"]))
            needed = (next_st["dist"] - curr_dist) / mpg
            curr_fuel -= needed
            curr_dist = next_st["dist"]
            curr_station = next_st

    total_consumed = round(total_distance / mpg, 2)
    total_purchased = round(sum(s["gallons_purchased"] for s in stops), 2)
    total_cost = round(sum(s["cost"] for s in stops), 2)

    return {
        "fuel_stops": stops,
        "total_distance_miles": total_distance,
        "total_fuel_consumed_gallons": total_consumed,
        "total_fuel_purchased_gallons": total_purchased,
        "total_fuel_cost": total_cost,
        "number_of_stops": len(stops),
    }

# Test with 790 mile route
test_stations = [
    {"name": "Station A", "dist": 150.0, "price": 3.80},
    {"name": "Station B", "dist": 350.0, "price": 3.10},
    {"name": "Station C", "dist": 480.0, "price": 3.40},
    {"name": "Station D", "dist": 620.0, "price": 3.05},
    {"name": "Station E", "dist": 720.0, "price": 3.90},
]
result = optimize_fuel(790.0, test_stations)
print("Optimization result for 790 miles:")
import pprint
pprint.pprint(result)
