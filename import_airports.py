import os
import csv
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from apps.airports.models import Airport

csv_path = 'data/airports.csv'

print(f"📊 Importing airports from {csv_path}...")

with open(csv_path, 'r', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    created_count = 0
    
    for row in reader:
        # Detect column names (handles different CSV formats)
        iata = row.get('iata_code') or row.get('iata') or row.get('ident')
        name = row.get('name') or row.get('airport_name')
        city = row.get('city') or row.get('municipality')
        country = row.get('country') or row.get('iso_country')
        lat = row.get('latitude') or row.get('lat')
        lon = row.get('longitude') or row.get('lon')
        
        # Only import if we have a valid IATA code (3 letters)
        if iata and len(iata) == 3 and iata.isalpha():
            airport, created = Airport.objects.get_or_create(
                iata_code=iata.upper(),
                defaults={
                    'name': (name or '')[:200],
                    'city': (city or '')[:100],
                    'country': (country or '')[:100],
                    'latitude': float(lat) if lat and lat.strip() else None,
                    'longitude': float(lon) if lon and lon.strip() else None,
                    'is_active': True,
                }
            )
            if created:
                created_count += 1

print(f"✅ Imported {created_count} new airports")
print(f"📊 Total airports in database: {Airport.objects.count()}")