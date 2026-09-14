from rest_framework import serializers


class RouteOptimizeRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=200,
        help_text="Starting location in the USA (e.g., 'Los Angeles, CA')",
    )
    finish = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=200,
        help_text="Destination location in the USA (e.g., 'Las Vegas, NV')",
    )
    corridor_radius_miles = serializers.FloatField(
        required=False,
        min_value=1.0,
        max_value=50.0,
        default=15.0,
        help_text="Search radius in miles along route corridor for fuel stations (default: 15.0)",
    )

    def validate(self, data):
        start = data.get("start", "").strip()
        finish = data.get("finish", "").strip()

        if not start:
            raise serializers.ValidationError({"start": "Start location cannot be empty."})
        if not finish:
            raise serializers.ValidationError({"finish": "Finish location cannot be empty."})

        if start.lower() == finish.lower():
            raise serializers.ValidationError(
                "Start and finish locations must be distinct."
            )

        data["start"] = start
        data["finish"] = finish
        return data


class LocationDetailSerializer(serializers.Serializer):
    name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    display_name = serializers.CharField(required=False)


class RouteDetailSerializer(serializers.Serializer):
    distance_miles = serializers.FloatField()
    duration_minutes = serializers.FloatField()
    geometry = serializers.DictField()


class VehicleDetailSerializer(serializers.Serializer):
    max_range_miles = serializers.FloatField()
    fuel_efficiency_mpg = serializers.FloatField()
    tank_capacity_gallons = serializers.FloatField()


class FuelStopDetailSerializer(serializers.Serializer):
    station_id = serializers.IntegerField(required=False, allow_null=True)
    opis_id = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    distance_from_start_miles = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    fuel_cost = serializers.FloatField()
    fuel_remaining_after_stop = serializers.FloatField()


class RouteSummarySerializer(serializers.Serializer):
    total_distance_miles = serializers.FloatField()
    total_fuel_consumed_gallons = serializers.FloatField()
    total_fuel_purchased_gallons = serializers.FloatField()
    total_fuel_cost = serializers.FloatField()
    number_of_stops = serializers.IntegerField()


class RouteOptimizationResponseSerializer(serializers.Serializer):
    start = LocationDetailSerializer()
    finish = LocationDetailSerializer()
    route = RouteDetailSerializer()
    vehicle = VehicleDetailSerializer()
    fuel_stops = serializers.ListSerializer(child=FuelStopDetailSerializer())
    summary = RouteSummarySerializer()
    meta = serializers.DictField(required=False)
