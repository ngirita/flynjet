#!/usr/bin/env python
import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from apps.fleet.models import Aircraft, AircraftMaintenance
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_upcoming_maintenance():
    """Check for upcoming maintenance"""
    today = timezone.now().date()
    next_week = today + timedelta(days=7)
    
    upcoming = AircraftMaintenance.objects.filter(
        scheduled_start__date__gte=today,
        scheduled_start__date__lte=next_week,
        status='scheduled'
    ).select_related('aircraft')
    
    alerts = []
    for maintenance in upcoming:
        days_until = (maintenance.scheduled_start.date() - today).days
        
        alert = {
            'aircraft': maintenance.aircraft.registration_number,
            'type': maintenance.maintenance_type,
            'title': maintenance.title,
            'scheduled_date': maintenance.scheduled_start,
            'days_until': days_until,
            'location': maintenance.maintenance_location
        }
        alerts.append(alert)
        
        logger.info(f"Upcoming maintenance: {alert}")
    
    return alerts

def check_overdue_maintenance():
    """Check for overdue maintenance"""
    today = timezone.now().date()
    
    overdue = AircraftMaintenance.objects.filter(
        scheduled_start__date__lt=today,
        status='scheduled'
    ).select_related('aircraft')
    
    alerts = []
    for maintenance in overdue:
        days_overdue = (today - maintenance.scheduled_start.date()).days
        
        alert = {
            'aircraft': maintenance.aircraft.registration_number,
            'type': maintenance.maintenance_type,
            'title': maintenance.title,
            'scheduled_date': maintenance.scheduled_start,
            'days_overdue': days_overdue,
            'location': maintenance.maintenance_location
        }
        alerts.append(alert)
        
        logger.warning(f"Overdue maintenance: {alert}")
    
    return alerts

def check_low_hours():
    """Check for aircraft approaching maintenance hours"""
    alerts = []
    
    for aircraft in Aircraft.objects.filter(is_active=True):
        if aircraft.total_flight_hours and aircraft.next_maintenance_due:
            hours_remaining = aircraft.next_maintenance_due - aircraft.total_flight_hours
            
            if 0 < hours_remaining <= 50:
                alert = {
                    'aircraft': aircraft.registration_number,
                    'hours_remaining': hours_remaining,
                    'next_maintenance': aircraft.next_maintenance_type or 'Unknown'
                }
                alerts.append(alert)
                
                logger.info(f"Low hours alert: {alert}")
    
    return alerts

def send_alerts(upcoming, overdue, low_hours):
    """Send alert emails"""
    if not (upcoming or overdue or low_hours):
        logger.info("No alerts to send")
        return
    
    subject = "Fleet Maintenance Alerts"
    
    message = "Maintenance Alert Summary\n\n"
    
    if upcoming:
        message += "UPCOMING MAINTENANCE:\n"
        for alert in upcoming:
            message += f"- {alert['aircraft']}: {alert['title']} in {alert['days_until']} days\n"
        message += "\n"
    
    if overdue:
        message += "OVERDUE MAINTENANCE:\n"
        for alert in overdue:
            message += f"- {alert['aircraft']}: {alert['title']} overdue by {alert['days_overdue']} days\n"
        message += "\n"
    
    if low_hours:
        message += "LOW HOURS ALERTS:\n"
        for alert in low_hours:
            message += f"- {alert['aircraft']}: {alert['hours_remaining']:.0f} hours until {alert['next_maintenance']}\n"
        message += "\n"
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.MAINTENANCE_TEAM_EMAIL],
        fail_silently=False,
    )
    
    logger.info(f"Sent maintenance alerts to {settings.MAINTENANCE_TEAM_EMAIL}")

def main():
    logger.info("Checking maintenance alerts...")
    
    upcoming = check_upcoming_maintenance()
    overdue = check_overdue_maintenance()
    low_hours = check_low_hours()
    
    logger.info(f"Found: {len(upcoming)} upcoming, {len(overdue)} overdue, {len(low_hours)} low hours")
    
    send_alerts(upcoming, overdue, low_hours)

if __name__ == '__main__':
    main()