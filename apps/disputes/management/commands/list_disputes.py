from django.core.management.base import BaseCommand
from apps.disputes.models import Dispute

class Command(BaseCommand):
    help = 'List all disputes'

    def handle(self, *args, **options):
        disputes = Dispute.objects.all().order_by('-filed_at')
        
        self.stdout.write(f"Total disputes: {disputes.count()}")
        self.stdout.write("-" * 80)
        
        for dispute in disputes:
            self.stdout.write(
                f"ID: {dispute.id} | "
                f"Number: {dispute.dispute_number} | "
                f"User: {dispute.user.email} | "
                f"Booking: {dispute.booking.booking_reference} | "
                f"Status: {dispute.status} | "
                f"Type: {dispute.dispute_type}"
            )