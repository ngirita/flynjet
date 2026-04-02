"""Gunicorn configuration file"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = "/app/logs/gunicorn_access.log"
errorlog = "/app/logs/gunicorn_error.log"
loglevel = "info"

# Process naming
proc_name = "flynjet"

# Server mechanics
daemon = False
pidfile = "/app/logs/gunicorn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if using gunicorn directly instead of nginx)
# keyfile = "/etc/ssl/private/flynjet.key"
# certfile = "/etc/ssl/certs/flynjet.crt"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Server hooks
def on_starting(server):
    """Log when server starts"""
    server.log.info("Starting FlynJet Gunicorn server")

def on_exit(server):
    """Log when server exits"""
    server.log.info("Stopping FlynJet Gunicorn server")

def worker_int(worker):
    """Log when worker receives INT signal"""
    worker.log.info("Worker received INT signal")

def worker_abort(worker):
    """Log when worker aborts"""
    worker.log.info("Worker aborted")