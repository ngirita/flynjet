import csv
from django.core.management.base import BaseCommand
from apps.airports.models import Airport  # Fix: Change from airports.models to apps.airports.models

class Command(BaseCommand):
    help = 'Import airports from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to airports.csv file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        
        self.stdout.write(f'Importing airports from {csv_file}...')
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            count = 0
            
            for row in reader:
                # Get IATA code
                iata = row.get('iata_code', '').strip()
                
                # Skip if no IATA code
                if not iata or iata == '\\N':
                    continue
                
                # Create or update airport
                try:
                    airport, created = Airport.objects.update_or_create(
                        iata_code=iata,
                        defaults={
                            'icao_code': row.get('icao_code', '').strip() if row.get('icao_code', '').strip() != '\\N' else '',
                            'name': row.get('name', '').strip(),
                            'city': row.get('municipality', '').strip(),
                            'country': row.get('iso_country', '').strip(),
                            'country_code': row.get('iso_country', '').strip(),
                            'latitude': row.get('latitude_deg', None) if row.get('latitude_deg', '').strip() not in ['', '\\N'] else None,
                            'longitude': row.get('longitude_deg', None) if row.get('longitude_deg', '').strip() not in ['', '\\N'] else None,
                            'timezone': row.get('timezone', '').strip() if row.get('timezone', '').strip() != '\\N' else '',
                        }
                    )
                    
                    if created:
                        count += 1
                        if count % 100 == 0:
                            self.stdout.write(f'  Imported {count} airports...')
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error importing row: {e}'))
                    continue
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully imported {count} airports!'))