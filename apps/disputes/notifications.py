from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import Dispute, DisputeMessage
import logging

logger = logging.getLogger(__name__)

class DisputeNotificationService:
    """Handle dispute notifications"""
    
    @classmethod
    def notify_dispute_filed(cls, dispute):
        """Notify admins of new dispute"""
        subject = f"New Dispute Filed: {dispute.dispute_number}"
        
        context = {
            'dispute': dispute,
            'user': dispute.user,
            'booking': dispute.booking
        }
        
        html_message = render_to_string('emails/dispute_filed.html', context)
        plain_message = render_to_string('emails/dispute_filed.txt', context)
        
        # Send to all admins
        from apps.accounts.models import User
        admin_emails = User.objects.filter(
            Q(is_staff=True) | Q(user_type='admin')
        ).values_list('email', flat=True)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            admin_emails,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"New dispute notification sent for {dispute.dispute_number}")
    
    @classmethod
    def notify_status_change(cls, dispute, old_status):
        """Notify user of status change"""
        subject = f"Dispute {dispute.dispute_number} Status Updated"
        
        context = {
            'dispute': dispute,
            'user': dispute.user,
            'old_status': old_status,
            'new_status': dispute.status
        }
        
        html_message = render_to_string('emails/dispute_status_change.html', context)
        plain_message = render_to_string('emails/dispute_status_change.txt', context)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [dispute.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Status change notification sent for {dispute.dispute_number}")
    
    @classmethod
    def notify_new_message(cls, message):
        """Notify recipient of new message"""
        dispute = message.dispute
        
        if message.is_staff:
            # Message from staff to customer
            recipient = dispute.user
            subject = f"New message on dispute {dispute.dispute_number}"
        else:
            # Message from customer to staff
            from apps.accounts.models import User
            recipients = User.objects.filter(
                Q(assigned_disputes=dispute) | Q(is_staff=True)
            ).distinct()
            subject = f"Customer replied to dispute {dispute.dispute_number}"
            recipient = None  # Will send to multiple
        
        context = {
            'dispute': dispute,
            'message': message,
            'sender': message.sender
        }
        
        html_message = render_to_string('emails/dispute_message.html', context)
        plain_message = render_to_string('emails/dispute_message.txt', context)
        
        if recipient:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient.email],
                html_message=html_message,
                fail_silently=False,
            )
        else:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [r.email for r in recipients],
                html_message=html_message,
                fail_silently=False,
            )
        
        logger.info(f"Message notification sent for dispute {dispute.dispute_number}")
    
    @classmethod
    def notify_resolution_proposed(cls, dispute, resolution):
        """Notify customer of proposed resolution"""
        subject = f"Resolution Proposed for Dispute {dispute.dispute_number}"
        
        context = {
            'dispute': dispute,
            'resolution': resolution,
            'user': dispute.user
        }
        
        html_message = render_to_string('emails/dispute_resolution_proposed.html', context)
        plain_message = render_to_string('emails/dispute_resolution_proposed.txt', context)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [dispute.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Resolution proposal notification sent for {dispute.dispute_number}")
    
    @classmethod
    def notify_resolution_accepted(cls, dispute):
        """Notify staff of accepted resolution"""
        subject = f"Resolution Accepted for Dispute {dispute.dispute_number}"
        
        context = {
            'dispute': dispute,
            'user': dispute.user
        }
        
        html_message = render_to_string('emails/dispute_resolution_accepted.html', context)
        plain_message = render_to_string('emails/dispute_resolution_accepted.txt', context)
        
        # Notify assigned agent and admins
        from apps.accounts.models import User
        recipients = []
        if dispute.assigned_to:
            recipients.append(dispute.assigned_to.email)
        recipients.extend(User.objects.filter(is_staff=True).values_list('email', flat=True))
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Resolution accepted notification sent for {dispute.dispute_number}")
    
    @classmethod
    def notify_deadline_approaching(cls, dispute):
        """Notify about approaching deadline"""
        hours_left = (dispute.response_deadline - timezone.now()).total_seconds() / 3600
        
        subject = f"Response Deadline Approaching - Dispute {dispute.dispute_number}"
        
        context = {
            'dispute': dispute,
            'hours_left': int(hours_left)
        }
        
        html_message = render_to_string('emails/dispute_deadline.html', context)
        plain_message = render_to_string('emails/dispute_deadline.txt', context)
        
        # Notify assigned agent
        if dispute.assigned_to:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [dispute.assigned_to.email],
                html_message=html_message,
                fail_silently=False,
            )
        
        logger.info(f"Deadline reminder sent for dispute {dispute.dispute_number}")
    
    @classmethod
    def notify_escalation(cls, dispute, reason):
        """Notify management of escalated dispute"""
        subject = f"ESCALATED: Dispute {dispute.dispute_number}"
        
        context = {
            'dispute': dispute,
            'reason': reason
        }
        
        html_message = render_to_string('emails/dispute_escalated.html', context)
        plain_message = render_to_string('emails/dispute_escalated.txt', context)
        
        # Send to management
        from apps.accounts.models import User
        manager_emails = User.objects.filter(
            user_type='admin'
        ).values_list('email', flat=True)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            manager_emails,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Escalation notification sent for dispute {dispute.dispute_number}")

class DisputeReminderService:
    """Send reminders for pending disputes"""
    
    @classmethod
    def send_daily_reminders(cls):
        """Send daily reminders for pending disputes"""
        pending = Dispute.objects.filter(
            status__in=['pending', 'investigating'],
            response_deadline__gt=timezone.now()
        )
        
        for dispute in pending:
            hours_left = (dispute.response_deadline - timezone.now()).total_seconds() / 3600
            
            if hours_left <= 24:
                # Urgent reminder
                DisputeNotificationService.notify_deadline_approaching(dispute)
            elif hours_left <= 48:
                # Warning reminder
                cls.send_reminder(dispute, hours_left)
    
    @classmethod
    def send_reminder(cls, dispute, hours_left):
        """Send reminder email"""
        from django.core.mail import send_mail
        
        subject = f"Reminder: Dispute {dispute.dispute_number} requires attention"
        message = f"""
        Dispute {dispute.dispute_number} requires attention.
        
        Status: {dispute.get_status_display()}
        Priority: {dispute.get_priority_display()}
        Time remaining: {int(hours_left)} hours
        Deadline: {dispute.response_deadline}
        
        Please review and take appropriate action.
        """
        
        if dispute.assigned_to:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [dispute.assigned_to.email],
                fail_silently=False,
            )
        
        logger.info(f"Reminder sent for dispute {dispute.dispute_number}")
    
    @classmethod
    def send_overdue_alerts(cls):
        """Send alerts for overdue disputes"""
        overdue = Dispute.objects.filter(
            response_deadline__lt=timezone.now(),
            status__in=['pending', 'investigating']
        )
        
        for dispute in overdue:
            subject = f"OVERDUE: Dispute {dispute.dispute_number}"
            message = f"""
            Dispute {dispute.dispute_number} is now overdue.
            
            Filed: {dispute.filed_at}
            Deadline was: {dispute.response_deadline}
            Current status: {dispute.get_status_display()}
            
            Immediate action required.
            """
            
            # Send to assigned agent and management
            recipients = []
            if dispute.assigned_to:
                recipients.append(dispute.assigned_to.email)
            
            from apps.accounts.models import User
            recipients.extend(User.objects.filter(
                user_type='admin'
            ).values_list('email', flat=True))
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                fail_silently=False,
            )
            
            logger.warning(f"Overdue alert sent for dispute {dispute.dispute_number}")