import os
import csv
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from apps.airports.models import Airport
from django.db import transaction

csv_path = 'data/airports.csv'

print(f"📊 Importing airports from {csv_path}...")

# Use batch insertion for better performance
batch_size = 500
airports_to_create = []
created_count = 0

with open(csv_path, 'r', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    
    for row in reader:
        iata = row.get('iata_code') or row.get('iata') or row.get('ident')
        name = row.get('name') or row.get('airport_name')
        city = row.get('city') or row.get('municipality')
        country = row.get('country') or row.get('iso_country')
        lat = row.get('latitude') or row.get('lat')
        lon = row.get('longitude') or row.get('lon')
        
        if iata and len(iata) == 3 and iata.isalpha():
            airports_to_create.append(Airport(
                iata_code=iata.upper(),
                name=(name or '')[:200],
                city=(city or '')[:100],
                country=(country or '')[:100],
                latitude=float(lat) if lat and lat.strip() else None,
                longitude=float(lon) if lon and lon.strip() else None,
                is_active=True,
            ))
        
        # Insert in batches
        if len(airports_to_create) >= batch_size:
            with transaction.atomic():
                created = Airport.objects.bulk_create(airports_to_create, ignore_conflicts=True)
                created_count += len(created)
            airports_to_create = []
            print(f"   Imported {created_count} airports so far...")

# Insert remaining airports
if airports_to_create:
    with transaction.atomic():
        created = Airport.objects.bulk_create(airports_to_create, ignore_conflicts=True)
        created_count += len(created)

print(f"✅ Imported {created_count} new airports")
print(f"📊 Total airports in database: {Airport.objects.count()}")