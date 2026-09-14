import csv
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from routes.models import FuelStation


class Command(BaseCommand):
    help = "Import and enrich fuel station dataset into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            nargs="?",
            type=str,
            default=None,
            help="Path to the fuel prices CSV file (raw or enriched)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing fuel station records before import",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for bulk database insertions (default: 1000)",
        )

    def handle(self, *args, **options):
        start_time = time.time()
        csv_file = options.get("csv_file")
        clear_existing = options.get("clear", False)
        batch_size = options.get("batch_size", 1000)

        # Default search path if no file is provided
        if not csv_file:
            enriched_path = Path("data/fuel_stations_enriched.csv")
            raw_path = Path("fuel-prices-for-be-assessment.csv")
            if enriched_path.exists():
                csv_file = str(enriched_path)
            elif raw_path.exists():
                csv_file = str(raw_path)
            else:
                raise CommandError("No fuel price CSV found. Please specify a file path.")

        target_path = Path(csv_file)
        if not target_path.exists():
            raise CommandError(f"CSV file '{csv_file}' does not exist.")

        self.stdout.write(self.style.NOTICE(f"Loading data from {csv_file}..."))

        # Load city coordinates cache if needed for raw CSV
        cache_path = Path("data/cities_coordinates_cache.json")
        city_coords = {}
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as cf:
                    city_coords = json.load(cf)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not load city coordinates cache: {e}"))

        # Read CSV
        with open(target_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_rows = len(rows)
        self.stdout.write(f"Read {total_rows} rows from CSV.")

        # Detect columns format
        first_row = rows[0] if rows else {}
        has_coords = "latitude" in first_row and "longitude" in first_row

        # Group and deduplicate:
        # If multiple records exist for the same OPIS Truckstop ID (or name+address+city+state),
        # keep the record with the LOWEST retail price.
        deduped = {}
        skipped_invalid = 0
        missing_coords = 0

        for r in rows:
            opis_id = (r.get("OPIS Truckstop ID") or r.get("opis_id") or "").strip()
            name = (r.get("Truckstop Name") or r.get("name") or "").strip()
            address = (r.get("Address") or r.get("address") or "").strip()
            city = (r.get("City") or r.get("city") or "").strip()
            state = (r.get("State") or r.get("state") or "").strip()
            rack_id = (r.get("Rack ID") or r.get("rack_id") or "").strip()

            price_raw = r.get("Retail Price") or r.get("retail_price") or ""
            try:
                price = float(price_raw)
            except (ValueError, TypeError):
                skipped_invalid += 1
                continue

            # Determine coordinates
            if has_coords:
                try:
                    lat = float(r["latitude"])
                    lon = float(r["longitude"])
                except (ValueError, TypeError, KeyError):
                    skipped_invalid += 1
                    continue
            else:
                city_key = f"{city.upper()}|{state.upper()}"
                coords = city_coords.get(city_key)
                if coords:
                    lat, lon = float(coords[0]), float(coords[1])
                else:
                    missing_coords += 1
                    continue

            key = opis_id if opis_id else f"{name}|{address}|{city}|{state}"

            if key not in deduped or price < deduped[key]["retail_price"]:
                deduped[key] = {
                    "opis_id": opis_id,
                    "name": name,
                    "address": address,
                    "city": city,
                    "state": state,
                    "rack_id": rack_id,
                    "retail_price": Decimal(str(round(price, 4))),
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                }

        self.stdout.write(
            f"Deduplicated to {len(deduped)} unique stations. "
            f"(Skipped invalid: {skipped_invalid}, Missing coords: {missing_coords})"
        )

        # Database population
        station_objects = [FuelStation(**data) for data in deduped.values()]

        with transaction.atomic():
            if clear_existing or FuelStation.objects.exists():
                self.stdout.write(self.style.WARNING("Clearing existing station records..."))
                FuelStation.objects.all().delete()

            self.stdout.write(f"Bulk inserting {len(station_objects)} stations (batch size: {batch_size})...")
            FuelStation.objects.bulk_create(station_objects, batch_size=batch_size)

        duration = round(time.time() - start_time, 2)
        count = FuelStation.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported {count} fuel stations in {duration} seconds."
            )
        )
