# Celery configuration file

# Broker settings
broker_url = 'redis://localhost:6379/1'
result_backend = 'redis://localhost:6379/1'

# Task settings
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# Task routing
task_routes = {
    'apps.payments.tasks.*': {'queue': 'payments'},
    'apps.bookings.tasks.*': {'queue': 'bookings'},
    'apps.fleet.tasks.*': {'queue': 'fleet'},
    'apps.analytics.tasks.*': {'queue': 'analytics'},
}

# Task execution
task_acks_late = True
task_reject_on_worker_lost = True
task_track_started = True
task_time_limit = 30 * 60  # 30 minutes
task_soft_time_limit = 25 * 60  # 25 minutes

# Worker settings
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 100
worker_max_memory_per_child = 300000  # 300MB

# Beat schedule
beat_schedule = {
    'check-maintenance': {
        'task': 'apps.fleet.tasks.check_maintenance_schedules',
        'schedule': 3600.0,  # Every hour
    },
    'check-expired-bookings': {
        'task': 'apps.bookings.tasks.check_expired_bookings',
        'schedule': 900.0,  # Every 15 minutes
    },
    'process-pending-refunds': {
        'task': 'apps.payments.tasks.process_pending_refunds',
        'schedule': 7200.0,  # Every 2 hours
    },
    'update-exchange-rates': {
        'task': 'apps.integrations.tasks.update_exchange_rates',
        'schedule': 21600.0,  # Every 6 hours
    },
    'generate-daily-reports': {
        'task': 'apps.analytics.tasks.generate_daily_reports',
        'schedule': 86400.0,  # Daily
    },
}