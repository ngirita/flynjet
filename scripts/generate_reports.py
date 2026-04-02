#!/usr/bin/env python
import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from apps.analytics.models import Report
from apps.analytics.reports import ReportGenerator
from django.utils import timezone

def generate_daily_reports():
    """Generate daily reports"""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    reports = [
        {
            'name': f'Revenue Report - {yesterday}',
            'type': 'revenue',
            'start': yesterday,
            'end': yesterday
        },
        {
            'name': f'Bookings Report - {yesterday}',
            'type': 'bookings',
            'start': yesterday,
            'end': yesterday
        },
        {
            'name': f'Customer Report - {yesterday}',
            'type': 'customer',
            'start': yesterday,
            'end': yesterday
        }
    ]
    
    for report_data in reports:
        report = Report.objects.create(
            name=report_data['name'],
            report_type=report_data['type'],
            parameters={
                'start_date': str(report_data['start']),
                'end_date': str(report_data['end'])
            },
            format='pdf'
        )
        
        report.generate()
        print(f"Generated: {report.name}")

def generate_weekly_reports():
    """Generate weekly reports"""
    end_date = timezone.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=7)
    
    report = Report.objects.create(
        name=f'Weekly Revenue Report - Week {end_date.isocalendar()[1]}',
        report_type='revenue',
        parameters={
            'start_date': str(start_date),
            'end_date': str(end_date)
        },
        format='pdf'
    )
    
    report.generate()
    print(f"Generated: {report.name}")

def generate_monthly_reports():
    """Generate monthly reports"""
    end_date = timezone.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=30)
    
    report = Report.objects.create(
        name=f'Monthly Analytics Report - {end_date.strftime("%B %Y")}',
        report_type='custom',
        parameters={
            'start_date': str(start_date),
            'end_date': str(end_date)
        },
        format='pdf'
    )
    
    report.generate()
    print(f"Generated: {report.name}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate reports')
    parser.add_argument('--period', choices=['daily', 'weekly', 'monthly', 'all'],
                       default='daily', help='Report period')
    
    args = parser.parse_args()
    
    if args.period == 'daily' or args.period == 'all':
        generate_daily_reports()
    
    if args.period == 'weekly' or args.period == 'all':
        generate_weekly_reports()
    
    if args.period == 'monthly' or args.period == 'all':
        generate_monthly_reports()

if __name__ == '__main__':
    main()