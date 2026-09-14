from django.db import models


class FuelStation(models.Model):
    """
    Represents a commercial truck stop / fuel station with retail fuel pricing
    and geographical coordinates.
    """
    opis_id = models.CharField(max_length=64, db_index=True, help_text="OPIS Truckstop ID")
    name = models.CharField(max_length=255, help_text="Truckstop / Station Name")
    address = models.CharField(max_length=255, help_text="Street / Highway Exit Address")
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=10, db_index=True)
    rack_id = models.CharField(max_length=50, blank=True, default="", help_text="Rack ID")
    retail_price = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        db_index=True,
        help_text="Retail fuel price per gallon (USD)"
    )
    latitude = models.FloatField(db_index=True, help_text="Latitude in decimal degrees")
    longitude = models.FloatField(db_index=True, help_text="Longitude in decimal degrees")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fuel_stations"
        ordering = ["retail_price"]
        indexes = [
            models.Index(fields=["latitude", "longitude"], name="station_lat_lon_idx"),
            models.Index(fields=["state", "city"], name="station_state_city_idx"),
            models.Index(fields=["opis_id"], name="station_opis_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.city}, {self.state} (${self.retail_price}/gal)"

