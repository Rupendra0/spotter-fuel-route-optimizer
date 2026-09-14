import logging
from typing import List, Dict, Any, Optional
from routes.exceptions import InfeasibleRouteError

logger = logging.getLogger(__name__)


class FuelOptimizer:
    """
    Cost-aware, physically feasible fuel stop optimization engine.
    Constraints:
        - Maximum driving range on full tank (default: 500 miles)
        - Fuel economy (default: 10 MPG)
        - Maximum fuel capacity (default: 50 gallons)
        - Initial fuel level (default: 50 gallons)
    """

    def __init__(
        self,
        max_range_miles: float = 500.0,
        fuel_economy_mpg: float = 10.0,
        tank_capacity_gallons: float = 50.0,
        initial_fuel_gallons: Optional[float] = None,
    ):
        self.max_range = float(max_range_miles)
        self.mpg = float(fuel_economy_mpg)
        self.tank_capacity = float(tank_capacity_gallons)
        self.initial_fuel = (
            float(initial_fuel_gallons)
            if initial_fuel_gallons is not None
            else self.tank_capacity
        )

    def optimize(
        self,
        total_distance_miles: float,
        candidate_stations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculates optimal fuel stops along the route to minimize cost.
        Returns:
            dict: {
                "fuel_stops": list of fuel stop details,
                "summary": {
                    "total_distance_miles": float,
                    "total_fuel_consumed_gallons": float,
                    "total_fuel_purchased_gallons": float,
                    "total_fuel_cost": float,
                    "number_of_stops": int
                }
            }
        """
        dist = round(total_distance_miles, 2)
        total_fuel_consumed = round(dist / self.mpg, 2)

        # Case 1: Trip is zero or negative distance
        if dist <= 0:
            return {
                "fuel_stops": [],
                "summary": {
                    "total_distance_miles": 0.0,
                    "total_fuel_consumed_gallons": 0.0,
                    "total_fuel_purchased_gallons": 0.0,
                    "total_fuel_cost": 0.0,
                    "number_of_stops": 0,
                },
            }

        # Case 2: Destination is reachable without refueling on initial fuel
        initial_range = self.initial_fuel * self.mpg
        if dist <= initial_range:
            logger.info(
                f"Destination ({dist} mi) reachable with initial fuel ({initial_range} mi range). No stops needed."
            )
            return {
                "fuel_stops": [],
                "summary": {
                    "total_distance_miles": dist,
                    "total_fuel_consumed_gallons": total_fuel_consumed,
                    "total_fuel_purchased_gallons": 0.0,
                    "total_fuel_cost": 0.0,
                    "number_of_stops": 0,
                },
            }

        # Case 3: Refueling required
        # Filter valid candidate stations between 0 and destination
        valid_stations = [
            s for s in candidate_stations
            if 0 < s.get("distance_from_start_miles", 0) < dist
        ]
        valid_stations.sort(key=lambda s: s["distance_from_start_miles"])

        if not valid_stations:
            raise InfeasibleRouteError(
                f"Route distance of {dist} miles exceeds vehicle initial range "
                f"({initial_range} miles), but no fuel stations were found along the corridor."
            )

        # Backward reachability analysis:
        # Determine which stations can physically reach the destination
        # through valid hops <= max_range.
        can_reach_dest = set()
        n = len(valid_stations)
        for i in reversed(range(n)):
            st = valid_stations[i]
            st_dist = st["distance_from_start_miles"]
            if dist - st_dist <= self.max_range:
                can_reach_dest.add(i)
            else:
                for j in range(i + 1, n):
                    if j in can_reach_dest and (
                        valid_stations[j]["distance_from_start_miles"] - st_dist <= self.max_range
                    ):
                        can_reach_dest.add(i)
                        break

        feasible_stations = [valid_stations[i] for i in sorted(can_reach_dest)]
        if not feasible_stations:
            raise InfeasibleRouteError(
                "No continuous chain of reachable fuel stations exists between start and destination."
            )

        # Verify start can reach at least one station that leads to destination
        start_reachable = [
            s for s in feasible_stations
            if s["distance_from_start_miles"] <= initial_range
        ]
        if not start_reachable:
            raise InfeasibleRouteError(
                f"The vehicle cannot reach any feasible fuel station within its initial range of {initial_range} miles."
            )

        # Optimization Simulation
        stops = []
        curr_dist = 0.0
        curr_fuel = self.initial_fuel

        # Pick the initial stop: cheapest feasible station reachable on initial fuel.
        # Break ties by selecting the furthest station.
        first_stop = min(
            start_reachable,
            key=lambda s: (s["retail_price"], -s["distance_from_start_miles"]),
        )
        burn_to_first = first_stop["distance_from_start_miles"] / self.mpg
        curr_fuel -= burn_to_first
        curr_dist = first_stop["distance_from_start_miles"]
        curr_station = first_stop

        # Decision loop
        while curr_dist + (curr_fuel * self.mpg) < dist:
            p_curr = curr_station["retail_price"]
            max_reach = curr_dist + self.max_range

            # Check if destination is reachable from current station with a full tank
            if dist <= max_reach:
                # Look for any cheaper station before destination
                cheaper_ahead = [
                    s for s in feasible_stations
                    if curr_dist < s["distance_from_start_miles"] < dist
                    and s["retail_price"] < p_curr
                ]
                if cheaper_ahead:
                    # Hop to the first cheaper station
                    next_st = cheaper_ahead[0]
                    fuel_needed = (next_st["distance_from_start_miles"] - curr_dist) / self.mpg
                    purchase = max(0.0, fuel_needed - curr_fuel)
                    purchase = min(self.tank_capacity - curr_fuel, purchase)
                    purchase = round(purchase, 2)
                    cost = round(purchase * p_curr, 2)
                    curr_fuel = round(curr_fuel + purchase, 2)

                    stops.append(self._format_stop(curr_station, curr_dist, p_curr, purchase, cost, curr_fuel))

                    curr_fuel -= fuel_needed
                    curr_dist = next_st["distance_from_start_miles"]
                    curr_station = next_st
                    continue
                else:
                    # Current station is cheaper than all remaining stations before destination.
                    # Purchase just enough to reach destination!
                    fuel_needed = (dist - curr_dist) / self.mpg
                    purchase = max(0.0, fuel_needed - curr_fuel)
                    purchase = min(self.tank_capacity - curr_fuel, purchase)
                    purchase = round(purchase, 2)
                    cost = round(purchase * p_curr, 2)
                    curr_fuel = round(curr_fuel + purchase, 2)

                    stops.append(self._format_stop(curr_station, curr_dist, p_curr, purchase, cost, curr_fuel))

                    curr_fuel -= fuel_needed
                    curr_dist = dist
                    break

            # Destination is beyond 500 miles from current station
            cheaper_in_range = [
                s for s in feasible_stations
                if curr_dist < s["distance_from_start_miles"] <= max_reach
                and s["retail_price"] < p_curr
            ]
            if cheaper_in_range:
                # Drive to first cheaper station ahead
                next_st = cheaper_in_range[0]
                fuel_needed = (next_st["distance_from_start_miles"] - curr_dist) / self.mpg
                purchase = max(0.0, fuel_needed - curr_fuel)
                purchase = min(self.tank_capacity - curr_fuel, purchase)
                purchase = round(purchase, 2)
                cost = round(purchase * p_curr, 2)
                curr_fuel = round(curr_fuel + purchase, 2)

                stops.append(self._format_stop(curr_station, curr_dist, p_curr, purchase, cost, curr_fuel))

                curr_fuel -= fuel_needed
                curr_dist = next_st["distance_from_start_miles"]
                curr_station = next_st
            else:
                # Current station is the local minimum price within 500 miles.
                # Fill tank to capacity to maximize cheap fuel usage!
                purchase = round(self.tank_capacity - curr_fuel, 2)
                cost = round(purchase * p_curr, 2)
                curr_fuel = round(curr_fuel + purchase, 2)

                stops.append(self._format_stop(curr_station, curr_dist, p_curr, purchase, cost, curr_fuel))

                # From full tank, advance to the best reachable station
                forward_stations = [
                    s for s in feasible_stations
                    if curr_dist < s["distance_from_start_miles"] <= curr_dist + self.max_range
                ]
                if not forward_stations:
                    raise InfeasibleRouteError("Unable to advance past current fuel stop.")

                next_st = min(
                    forward_stations,
                    key=lambda s: (s["retail_price"], -s["distance_from_start_miles"]),
                )
                fuel_needed = (next_st["distance_from_start_miles"] - curr_dist) / self.mpg
                curr_fuel -= fuel_needed
                curr_dist = next_st["distance_from_start_miles"]
                curr_station = next_st

        # Aggregation
        total_purchased = round(sum(s["gallons_purchased"] for s in stops), 2)
        total_cost = round(sum(s["fuel_cost"] for s in stops), 2)

        return {
            "fuel_stops": stops,
            "summary": {
                "total_distance_miles": dist,
                "total_fuel_consumed_gallons": total_fuel_consumed,
                "total_fuel_purchased_gallons": total_purchased,
                "total_fuel_cost": total_cost,
                "number_of_stops": len(stops),
            },
        }

    def _format_stop(
        self,
        station: Dict[str, Any],
        dist_from_start: float,
        price: float,
        purchased: float,
        cost: float,
        fuel_after: float,
    ) -> Dict[str, Any]:
        return {
            "station_id": station.get("station_id"),
            "opis_id": station.get("opis_id", ""),
            "name": station.get("name", ""),
            "address": station.get("address", ""),
            "city": station.get("city", ""),
            "state": station.get("state", ""),
            "latitude": station.get("latitude"),
            "longitude": station.get("longitude"),
            "distance_from_start_miles": round(dist_from_start, 2),
            "price_per_gallon": round(price, 3),
            "gallons_purchased": round(purchased, 2),
            "fuel_cost": round(cost, 2),
            "fuel_remaining_after_stop": round(fuel_after, 2),
        }
