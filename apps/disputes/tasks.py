from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
from .models import Dispute, DisputeAnalytics
from .notifications import DisputeReminderService
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_dispute_deadlines():
    """Check for approaching and missed deadlines"""
    # Send reminders for approaching deadlines
    DisputeReminderService.send_daily_reminders()
    
    # Send alerts for overdue disputes
    DisputeReminderService.send_overdue_alerts()
    
    logger.info("Dispute deadline checks completed")
    return True

@shared_task
def auto_close_inactive_disputes(days=30):
    """Auto-close disputes with no activity"""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    inactive = Dispute.objects.filter(
        updated_at__lt=cutoff,
        status__in=['pending', 'investigating']
    )
    
    for dispute in inactive:
        dispute.status = 'closed'
        dispute.resolution_notes = "Auto-closed due to inactivity"
        dispute.save(update_fields=['status', 'resolution_notes'])
        
        # Notify user
        send_mail(
            f"Dispute {dispute.dispute_number} Closed",
            f"Your dispute has been closed due to {days} days of inactivity.",
            settings.DEFAULT_FROM_EMAIL,
            [dispute.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Dispute {dispute.dispute_number} auto-closed due to inactivity")
    
    return inactive.count()

@shared_task
def generate_daily_dispute_report():
    """Generate daily dispute statistics"""
    today = timezone.now().date()
    
    disputes = Dispute.objects.filter(filed_at__date=today)
    
    report = {
        'date': today,
        'new_disputes': disputes.count(),
        'by_type': dict(disputes.values_list('dispute_type').annotate(count=models.Count('id'))),
        'by_status': dict(disputes.values_list('status').annotate(count=models.Count('id'))),
        'total_amount': disputes.aggregate(total=models.Sum('disputed_amount'))['total'] or 0,
        'resolved_today': Dispute.objects.filter(resolved_at__date=today).count(),
        'escalated': Dispute.objects.filter(status='escalated').count(),
    }
    
    # Send report to management
    from apps.accounts.models import User
    manager_emails = User.objects.filter(
        user_type='admin'
    ).values_list('email', flat=True)
    
    send_mail(
        f"Daily Dispute Report - {today}",
        f"New disputes: {report['new_disputes']}\n"
        f"Resolved: {report['resolved_today']}\n"
        f"Total amount: ${report['total_amount']}",
        settings.DEFAULT_FROM_EMAIL,
        manager_emails,
        fail_silently=False,
    )
    
    logger.info(f"Daily dispute report generated for {today}")
    return report

@shared_task
def generate_weekly_analytics():
    """Generate weekly dispute analytics"""
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=7)
    
    disputes = Dispute.objects.filter(
        filed_at__date__gte=start_date,
        filed_at__date__lte=end_date
    )
    
    analytics = {
        'period': f"{start_date} to {end_date}",
        'total_disputes': disputes.count(),
        'avg_resolution_time': disputes.filter(
            resolved_at__isnull=False
        ).aggregate(
            avg=models.Avg(models.F('resolved_at') - models.F('filed_at'))
        )['avg'],
        'resolution_rate': (disputes.filter(status='resolved').count() / disputes.count() * 100) if disputes.count() > 0 else 0,
        'by_priority': dict(disputes.values_list('priority').annotate(count=models.Count('id'))),
        'total_refunded': disputes.filter(refund_issued=True).aggregate(total=models.Sum('refund_amount'))['total'] or 0,
    }
    
    # Save to database
    DisputeAnalytics.objects.create(
        date=end_date,
        total_disputes=analytics['total_disputes'],
        open_disputes=disputes.filter(status__in=['pending', 'investigating']).count(),
        resolved_disputes=disputes.filter(status='resolved').count(),
        escalated_disputes=disputes.filter(status='escalated').count(),
        total_disputed_amount=disputes.aggregate(total=models.Sum('disputed_amount'))['total'] or 0,
        total_refunded_amount=analytics['total_refunded'],
        avg_resolution_time_hours=analytics['avg_resolution_time'].total_seconds() / 3600 if analytics['avg_resolution_time'] else 0,
        disputes_by_type=dict(disputes.values_list('dispute_type').annotate(count=models.Count('id'))),
        disputes_by_status=dict(disputes.values_list('status').annotate(count=models.Count('id'))),
    )
    
    logger.info(f"Weekly dispute analytics generated for {end_date}")
    return analytics

@shared_task
def sync_with_payment_system():
    """Sync dispute status with payment system"""
    from apps.payments.models import Payment
    
    # Find disputes related to chargebacks
    chargeback_disputes = Dispute.objects.filter(
        dispute_type='chargeback',
        status='investigating'
    )
    
    for dispute in chargeback_disputes:
        if dispute.payment:
            # Check payment status
            payment = dispute.payment
            if payment.status == 'disputed':
                # Update dispute
                dispute.status = 'escalated'
                dispute.save(update_fields=['status'])
                
                logger.info(f"Dispute {dispute.dispute_number} escalated based on payment status")
    
    return chargeback_disputes.count()

@shared_task
def send_dispute_summary_to_customer(dispute_id):
    """Send summary email to customer"""
    try:
        dispute = Dispute.objects.get(id=dispute_id)
        
        subject = f"Dispute Summary - {dispute.dispute_number}"
        
        messages = dispute.messages.all().order_by('created_at')
        
        summary = f"Dispute Summary\n"
        summary += f"Number: {dispute.dispute_number}\n"
        summary += f"Filed: {dispute.filed_at}\n"
        summary += f"Status: {dispute.get_status_display()}\n"
        summary += f"Subject: {dispute.subject}\n\n"
        summary += "Message History:\n"
        
        for msg in messages:
            sender = "You" if msg.sender == dispute.user else "Support"
            summary += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {sender}: {msg.message}\n"
        
        send_mail(
            subject,
            summary,
            settings.DEFAULT_FROM_EMAIL,
            [dispute.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Dispute summary sent for {dispute.dispute_number}")
        return True
    except Dispute.DoesNotExist:
        logger.error(f"Dispute {dispute_id} not found")
        return False