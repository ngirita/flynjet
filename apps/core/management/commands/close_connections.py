from django.core.management.base import BaseCommand
from django.db import connections
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Close all database connections'
    
    def handle(self, *args, **options):
        for conn in connections.all():
            conn.close()
        self.stdout.write(self.style.SUCCESS('Closed all database connections'))
        logger.info('Closed all database connections')