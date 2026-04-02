from django.utils import timezone
from .models import Dispute, DisputeMessage, DisputeResolution
import logging

logger = logging.getLogger(__name__)

class MediationService:
    """Handle dispute mediation"""
    
    @classmethod
    def initiate_mediation(cls, dispute_id, mediator):
        """Start mediation process"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            dispute.status = 'investigating'
            dispute.priority = 'high'
            dispute.save(update_fields=['status', 'priority'])
            
            # Create system message
            DisputeMessage.objects.create(
                dispute=dispute,
                message=f"Mediation initiated by {mediator.get_full_name()}",
                is_staff=True
            )
            
            logger.info(f"Mediation initiated for dispute {dispute.dispute_number}")
            return dispute
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return None
    
    @classmethod
    def propose_compromise(cls, dispute_id, proposer, offer_amount, terms):
        """Propose compromise solution"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            resolution = DisputeResolution.objects.create(
                dispute=dispute,
                resolution_type='partial_refund',
                description=f"Compromise offer: {terms}",
                refund_amount=offer_amount,
                proposed_by=proposer
            )
            
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=proposer,
                message=f"Compromise offer: ${offer_amount} - {terms}",
                is_staff=True
            )
            
            logger.info(f"Compromise proposed for dispute {dispute.dispute_number}")
            return resolution
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return None
    
    @classmethod
    def schedule_mediation_call(cls, dispute_id, scheduled_time, participants):
        """Schedule mediation call"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            # Create calendar event (simplified)
            event_details = {
                'dispute': dispute.dispute_number,
                'time': scheduled_time.isoformat(),
                'participants': participants,
                'join_url': f"/mediation/join/{dispute.id}/"
            }
            
            dispute.metadata['mediation_call'] = event_details
            dispute.save(update_fields=['metadata'])
            
            # Notify participants
            for email in participants:
                # Send calendar invite
                pass
            
            DisputeMessage.objects.create(
                dispute=dispute,
                message=f"Mediation call scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')}",
                is_staff=True
            )
            
            logger.info(f"Mediation call scheduled for dispute {dispute.dispute_number}")
            return event_details
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return None

class MediationAnalytics:
    """Analyze mediation outcomes"""
    
    @classmethod
    def get_success_rate(cls, start_date=None, end_date=None):
        """Calculate mediation success rate"""
        disputes = Dispute.objects.filter(
            resolution__isnull=False
        )
        
        if start_date:
            disputes = disputes.filter(created_at__date__gte=start_date)
        if end_date:
            disputes = disputes.filter(created_at__date__lte=end_date)
        
        total = disputes.count()
        if total == 0:
            return 0
        
        accepted = disputes.filter(resolution__accepted_by_customer=True).count()
        return (accepted / total) * 100
    
    @classmethod
    def average_resolution_time(cls, dispute_type=None):
        """Calculate average time to resolution"""
        disputes = Dispute.objects.filter(
            status='resolved',
            resolved_at__isnull=False
        )
        
        if dispute_type:
            disputes = disputes.filter(dispute_type=dispute_type)
        
        if not disputes.exists():
            return None
        
        total_time = sum(
            (d.resolved_at - d.filed_at).total_seconds()
            for d in disputes
        )
        avg_seconds = total_time / disputes.count()
        
        return avg_seconds / 3600  # Return hours
    
    @classmethod
    def common_outcomes(cls, limit=5):
        """Get most common dispute outcomes"""
        from django.db.models import Count
        
        return DisputeResolution.objects.values(
            'resolution_type'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

class MediationTemplate:
    """Templates for mediation communications"""
    
    MEDIATION_INTRO = """
    Dear {customer_name},
    
    We understand you have a dispute regarding your booking {booking_reference}.
    To help resolve this matter fairly, we would like to initiate a mediation process.
    
    During mediation, an impartial mediator will work with both parties to find a
    mutually acceptable solution.
    
    Please let us know your availability for a mediation call.
    
    Best regards,
    FlynJet Mediation Team
    """
    
    COMPROMISE_OFFER = """
    Dear {customer_name},
    
    After reviewing your dispute {dispute_number}, we would like to propose the
    following compromise solution:
    
    {offer_details}
    
    Please let us know if this proposal is acceptable to you.
    
    Best regards,
    FlynJet Mediation Team
    """
    
    MEDIATION_SCHEDULED = """
    Dear {customer_name},
    
    A mediation session has been scheduled for:
    
    Date: {date}
    Time: {time}
    Duration: {duration}
    
    Join the session here: {join_url}
    
    Please have any relevant documentation ready for review.
    
    Best regards,
    FlynJet Mediation Team
    """
    
    MEDIATION_RESOLVED = """
    Dear {customer_name},
    
    We are pleased to inform you that a resolution has been reached in your
    dispute {dispute_number}.
    
    Resolution: {resolution_details}
    
    The agreed-upon actions will be processed within 2-3 business days.
    
    Thank you for working with us to resolve this matter.
    
    Best regards,
    FlynJet Mediation Team
    """
    
    @classmethod
    def render(cls, template_name, context):
        """Render mediation template"""
        template = getattr(cls, template_name, "")
        return template.format(**context)