from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import DataSubjectRequest, BreachNotification, DataProcessingAgreement
from .gdpr import GDPRService
from .audit import ComplianceAuditor
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_dsr_deadlines():
    """Check for approaching and missed DSR deadlines"""
    # Approaching deadlines (7 days)
    approaching = DataSubjectRequest.objects.filter(
        status__in=['pending', 'processing'],
        deadline__lte=timezone.now() + timezone.timedelta(days=7),
        deadline__gt=timezone.now()
    )
    
    for dsr in approaching:
        send_dsr_reminder.delay(dsr.id, days_left=(dsr.deadline - timezone.now()).days)
    
    # Missed deadlines
    missed = DataSubjectRequest.objects.filter(
        status__in=['pending', 'processing'],
        deadline__lt=timezone.now()
    )
    
    for dsr in missed:
        send_dsr_escalation.delay(dsr.id)
    
    logger.info(f"Checked DSR deadlines: {approaching.count()} approaching, {missed.count()} missed")
    return {'approaching': approaching.count(), 'missed': missed.count()}

@shared_task
def send_dsr_reminder(dsr_id, days_left):
    """Send reminder about approaching DSR deadline"""
    try:
        dsr = DataSubjectRequest.objects.get(id=dsr_id)
        
        send_mail(
            f"DSR Deadline Approaching - {dsr.request_number}",
            f"""
            DSR {dsr.request_number} deadline is in {days_left} days.
            
            Type: {dsr.get_request_type_display()}
            Requester: {dsr.requester_name} ({dsr.requester_email})
            Deadline: {dsr.deadline}
            
            Please ensure this request is processed on time.
            """,
            settings.DEFAULT_FROM_EMAIL,
            [settings.COMPLIANCE_EMAIL],
            fail_silently=False,
        )
        
        logger.info(f"Reminder sent for DSR {dsr.request_number}")
    except DataSubjectRequest.DoesNotExist:
        logger.error(f"DSR {dsr_id} not found")

@shared_task
def send_dsr_escalation(dsr_id):
    """Escalate missed DSR deadline"""
    try:
        dsr = DataSubjectRequest.objects.get(id=dsr_id)
        
        send_mail(
            f"URGENT: DSR Deadline Missed - {dsr.request_number}",
            f"""
            DSR {dsr.request_number} has missed its deadline.
            
            Type: {dsr.get_request_type_display()}
            Requester: {dsr.requester_name} ({dsr.requester_email})
            Deadline was: {dsr.deadline}
            
            Immediate action required. This may constitute a compliance violation.
            """,
            settings.DEFAULT_FROM_EMAIL,
            [settings.COMPLIANCE_EMAIL, settings.ADMIN_EMAIL],
            fail_silently=False,
        )
        
        logger.warning(f"Escalation sent for missed DSR {dsr.request_number}")
    except DataSubjectRequest.DoesNotExist:
        logger.error(f"DSR {dsr_id} not found")

@shared_task
def check_dpa_expirations():
    """Check for expiring data processing agreements"""
    thirty_days = timezone.now() + timezone.timedelta(days=30)
    
    expiring = DataProcessingAgreement.objects.filter(
        is_active=True,
        expiry_date__lte=thirty_days,
        expiry_date__gt=timezone.now()
    )
    
    for dpa in expiring:
        send_dpa_reminder.delay(dpa.id, (dpa.expiry_date - timezone.now()).days)
    
    expired = DataProcessingAgreement.objects.filter(
        is_active=True,
        expiry_date__lt=timezone.now()
    )
    
    for dpa in expired:
        dpa.is_active = False
        dpa.save()
        
        send_dpa_expired_alert.delay(dpa.id)
    
    logger.info(f"Checked DPA expirations: {expiring.count()} expiring, {expired.count()} expired")
    return {'expiring': expiring.count(), 'expired': expired.count()}

@shared_task
def send_dpa_reminder(dpa_id, days_left):
    """Send reminder about expiring DPA"""
    try:
        dpa = DataProcessingAgreement.objects.get(id=dpa_id)
        
        send_mail(
            f"DPA Expiring Soon - {dpa.company_name}",
            f"""
            Data Processing Agreement with {dpa.company_name} expires in {days_left} days.
            
            Agreement Number: {dpa.agreement_number}
            Effective Date: {dpa.effective_date}
            Expiry Date: {dpa.expiry_date}
            
            Please review and renew if necessary.
            """,
            settings.DEFAULT_FROM_EMAIL,
            [settings.COMPLIANCE_EMAIL, dpa.contact_email],
            fail_silently=False,
        )
        
        logger.info(f"DPA reminder sent for {dpa.company_name}")
    except DataProcessingAgreement.DoesNotExist:
        logger.error(f"DPA {dpa_id} not found")

@shared_task
def send_dpa_expired_alert(dpa_id):
    """Send alert about expired DPA"""
    try:
        dpa = DataProcessingAgreement.objects.get(id=dpa_id)
        
        send_mail(
            f"DPA EXPIRED - {dpa.company_name}",
            f"""
            Data Processing Agreement with {dpa.company_name} has EXPIRED.
            
            Agreement Number: {dpa.agreement_number}
            Expiry Date: {dpa.expiry_date}
            
            This agreement is no longer valid. Immediate action required.
            """,
            settings.DEFAULT_FROM_EMAIL,
            [settings.COMPLIANCE_EMAIL, settings.ADMIN_EMAIL],
            fail_silently=False,
        )
        
        logger.warning(f"DPA expired alert sent for {dpa.company_name}")
    except DataProcessingAgreement.DoesNotExist:
        logger.error(f"DPA {dpa_id} not found")

@shared_task
def generate_compliance_report():
    """Generate monthly compliance report"""
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=30)
    
    report = ComplianceAuditor.generate_audit_report(start_date, end_date)
    
    # Send report to compliance team
    send_mail(
        f"Monthly Compliance Report - {end_date.strftime('%B %Y')}",
        f"""
        Compliance Report for {start_date} to {end_date}
        
        DSR Statistics:
        - Total DSRs: {report['dsr_stats']['total']}
        - By Status: {report['dsr_stats']['by_status']}
        - Average Completion Time: {report['dsr_stats']['avg_completion_time']}
        
        Breach Statistics:
        - Total Breaches: {report['breach_stats']['total']}
        - By Severity: {report['breach_stats']['by_severity']}
        - Users Affected: {report['breach_stats']['users_affected']}
        
        Full report attached.
        """,
        settings.DEFAULT_FROM_EMAIL,
        [settings.COMPLIANCE_EMAIL],
        fail_silently=False,
    )
    
    logger.info("Monthly compliance report generated")
    return report

@shared_task
def anonymize_old_data(days=365):
    """Anonymize data older than specified days"""
    from apps.accounts.models import User
    from apps.bookings.models import Booking
    
    cutoff = timezone.now() - timezone.timedelta(days=days)
    
    # Anonymize old bookings
    old_bookings = Booking.objects.filter(
        created_at__lt=cutoff,
        status='completed'
    )
    
    for booking in old_bookings:
        # Keep reference but remove personal data
        booking.passengers = []  # Clear passenger data
        booking.save(update_fields=['passengers'])
    
    logger.info(f"Anonymized {old_bookings.count()} old bookings")
    return old_bookings.count()