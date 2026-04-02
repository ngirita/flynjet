import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')

app = Celery('flynjet')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    # Check for expired bookings
    'check-expired-bookings': {
        'task': 'apps.bookings.tasks.check_expired_bookings',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    
    # Send booking reminders
    'send-booking-reminders': {
        'task': 'apps.bookings.tasks.send_booking_reminders',
        'schedule': crontab(hour='8', minute='0'),  # Daily at 8 AM
    },
    
    # Process pending refunds
    'process-pending-refunds': {
        'task': 'apps.payments.tasks.process_pending_refunds',
        'schedule': crontab(hour='*/2', minute='0'),  # Every 2 hours
    },
    
    # Update cryptocurrency confirmations
    'update-crypto-confirmations': {
        'task': 'apps.payments.tasks.update_crypto_confirmations',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    
    # Check document expirations
    'check-document-expirations': {
        'task': 'apps.fleet.tasks.check_document_expirations',
        'schedule': crontab(hour='9', minute='0'),  # Daily at 9 AM
    },
    
    # Generate daily reports
    'generate-daily-reports': {
        'task': 'apps.core.tasks.generate_daily_reports',
        'schedule': crontab(hour='23', minute='55'),  # Daily at 11:55 PM
    },
    
    # Clean up expired sessions
    'cleanup-expired-sessions': {
        'task': 'apps.accounts.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour='3', minute='0'),  # Daily at 3 AM
    },
    
    # Update exchange rates
    'update-exchange-rates': {
        'task': 'apps.payments.tasks.update_exchange_rates',
        'schedule': crontab(hour='*/6', minute='0'),  # Every 6 hours
    },
    
    # Send invoice reminders
    'send-invoice-reminders': {
        'task': 'apps.bookings.tasks.send_invoice_reminders',
        'schedule': crontab(hour='10', minute='0'),  # Daily at 10 AM
    },
    
    # Backup database
    'backup-database': {
        'task': 'apps.core.tasks.backup_database',
        'schedule': crontab(hour='2', minute='0'),  # Daily at 2 AM
    },
}

# Task routing
app.conf.task_routes = {
    'apps.payments.tasks.*': {'queue': 'payments'},
    'apps.bookings.tasks.*': {'queue': 'bookings'},
    'apps.fleet.tasks.*': {'queue': 'fleet'},
    'apps.accounts.tasks.*': {'queue': 'accounts'},
    'apps.core.tasks.*': {'queue': 'core'},
}

# Task execution settings
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
app.conf.task_track_started = True
app.conf.task_time_limit = 30 * 60  # 30 minutes
app.conf.task_soft_time_limit = 25 * 60  # 25 minutes

# Result backend settings
app.conf.result_expires = 3600  # 1 hour
app.conf.result_backend = 'django-db'

# Worker settings
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_max_tasks_per_child = 100
app.conf.worker_max_memory_per_child = 300000  # 300MB