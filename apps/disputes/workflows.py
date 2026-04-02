from django.utils import timezone
from django.db.models import Q
from .models import Dispute, DisputeResolution, DisputeMessage
from apps.payments.models import Payment, RefundRequest
from django.db.models import Q, Sum
import logging

logger = logging.getLogger(__name__)

class DisputeWorkflow:
    """Manage dispute workflows"""
    
    @classmethod
    def create_dispute(cls, user, booking, dispute_type, subject, description, amount=None):
        """Create a new dispute"""
        dispute = Dispute.objects.create(
            user=user,
            booking=booking,
            dispute_type=dispute_type,
            subject=subject,
            description=description,
            disputed_amount=amount or booking.total_amount_usd,
            status='pending'
        )
        
        # Create initial message
        DisputeMessage.objects.create(
            dispute=dispute,
            sender=user,
            message=f"Dispute filed: {description}"
        )
        
        logger.info(f"Dispute {dispute.dispute_number} created by {user.email}")
        return dispute
    
    @classmethod
    def assign_dispute(cls, dispute_id, agent):
        """Assign dispute to agent"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            dispute.assign_to(agent)
            
            # Create notification message
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=agent,
                message=f"Dispute assigned to {agent.get_full_name()}",
                is_staff=True
            )
            
            logger.info(f"Dispute {dispute.dispute_number} assigned to {agent.email}")
            return dispute
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return None
    
    @classmethod
    def investigate_dispute(cls, dispute_id, investigator):
        """Start investigation"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            dispute.status = 'investigating'
            dispute.assigned_to = investigator
            dispute.assigned_at = timezone.now()
            dispute.save()
            
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=investigator,
                message="Investigation started",
                is_staff=True
            )
            
            logger.info(f"Investigation started for dispute {dispute.dispute_number}")
            return dispute
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return None
    
    @classmethod
    def propose_resolution(cls, dispute_id, proposer, resolution_type, description, 
                          refund_amount=0, credit_amount=0):
        """Propose resolution to customer"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            resolution = DisputeResolution.objects.create(
                dispute=dispute,
                resolution_type=resolution_type,
                description=description,
                refund_amount=refund_amount,
                credit_amount=credit_amount,
                proposed_by=proposer
            )
            
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=proposer,
                message=f"Resolution proposed: {description}",
                is_staff=True
            )
            
            logger.info(f"Resolution proposed for dispute {dispute.dispute_number}")
            return resolution
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return None
    
    @classmethod
    def accept_resolution(cls, dispute_id, customer):
        """Customer accepts resolution"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            resolution = dispute.resolution
            if resolution:
                resolution.accept(customer)
                
                DisputeMessage.objects.create(
                    dispute=dispute,
                    sender=customer,
                    message="Resolution accepted"
                )
                
                logger.info(f"Resolution accepted for dispute {dispute.dispute_number}")
                return True
            return False
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return False
    
    @classmethod
    def reject_resolution(cls, dispute_id, customer, reason):
        """Customer rejects resolution"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=customer,
                message=f"Resolution rejected: {reason}"
            )
            
            dispute.status = 'investigating'
            dispute.save()
            
            logger.info(f"Resolution rejected for dispute {dispute.dispute_number}")
            return True
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return False
    
    @classmethod
    def escalate_dispute(cls, dispute_id, reason):
        """Escalate dispute to management"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            dispute.escalate(reason)
            
            DisputeMessage.objects.create(
                dispute=dispute,
                message=f"Dispute escalated: {reason}",
                is_staff=True
            )
            
            logger.info(f"Dispute {dispute.dispute_number} escalated")
            return dispute
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return None
    
    @classmethod
    def process_refund(cls, dispute_id, amount=None):
        """Process refund for resolved dispute"""
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            if dispute.status != 'resolved':
                logger.error(f"Cannot process refund for unresolved dispute {dispute.dispute_number}")
                return False
            
            if not dispute.refund_issued and dispute.refund_amount > 0:
                # Create refund request
                refund = RefundRequest.objects.create(
                    user=dispute.user,
                    booking=dispute.booking,
                    reason='dispute_resolution',
                    requested_amount=dispute.refund_amount,
                    approved_amount=dispute.refund_amount,
                    status='approved'
                )
                
                # Process through payment system
                if dispute.payment:
                    dispute.payment.process_refund(dispute.refund_amount, 'Dispute resolution', None)
                
                dispute.refund_issued = True
                dispute.refund_transaction_id = f"REF-{dispute.dispute_number}"
                dispute.save()
                
                DisputeMessage.objects.create(
                    dispute=dispute,
                    message=f"Refund of ${dispute.refund_amount} processed",
                    is_staff=True
                )
                
                logger.info(f"Refund processed for dispute {dispute.dispute_number}")
                return True
            
            return False
        except Dispute.DoesNotExist:
            logger.error(f"Dispute {dispute_id} not found")
            return False

class DisputeEscalationMatrix:
    """Define escalation rules for disputes"""
    
    ESCALATION_RULES = {
        'cancellation': {
            'time_threshold': 48,  # hours
            'amount_threshold': 10000,
            'escalate_to': 'manager'
        },
        'refund': {
            'time_threshold': 72,
            'amount_threshold': 5000,
            'escalate_to': 'finance'
        },
        'chargeback': {
            'time_threshold': 24,
            'amount_threshold': 0,
            'escalate_to': 'legal'
        },
        'service': {
            'time_threshold': 48,
            'amount_threshold': 2000,
            'escalate_to': 'manager'
        },
        'billing': {
            'time_threshold': 48,
            'amount_threshold': 1000,
            'escalate_to': 'finance'
        },
        'damage': {
            'time_threshold': 24,
            'amount_threshold': 5000,
            'escalate_to': 'claims'
        }
    }
    
    @classmethod
    def should_escalate(cls, dispute):
        """Check if dispute should be escalated"""
        rule = cls.ESCALATION_RULES.get(dispute.dispute_type, {})
        
        # Check time threshold
        hours_passed = (timezone.now() - dispute.filed_at).total_seconds() / 3600
        if hours_passed > rule.get('time_threshold', 72):
            return True, f"Exceeded time threshold of {rule.get('time_threshold')} hours"
        
        # Check amount threshold
        if dispute.disputed_amount > rule.get('amount_threshold', 10000):
            return True, f"Amount exceeds threshold of ${rule.get('amount_threshold')}"
        
        # Check customer status
        if dispute.user.user_type == 'corporate':
            return True, "Corporate client - needs special handling"
        
        # Check repeat disputes
        previous_disputes = Dispute.objects.filter(
            user=dispute.user,
            status='resolved'
        ).count()
        if previous_disputes > 3:
            return True, f"Customer has {previous_disputes} previous disputes"
        
        return False, None
    
    @classmethod
    def get_escalation_level(cls, dispute):
        """Get escalation level for dispute"""
        rule = cls.ESCALATION_RULES.get(dispute.dispute_type, {})
        return rule.get('escalate_to', 'supervisor')

class DisputeMetrics:
    """Calculate dispute metrics"""
    
    @classmethod
    def calculate_resolution_time(cls, dispute):
        """Calculate time to resolution in hours"""
        if dispute.resolved_at and dispute.filed_at:
            delta = dispute.resolved_at - dispute.filed_at
            return delta.total_seconds() / 3600
        return None
    
    @classmethod
    def calculate_satisfaction_rate(cls, start_date, end_date):
        """Calculate customer satisfaction rate for resolved disputes"""
        resolved = Dispute.objects.filter(
            resolved_at__date__gte=start_date,
            resolved_at__date__lte=end_date
        )
        
        if not resolved.exists():
            return 0
        
        # Count resolutions that were accepted
        accepted = resolved.filter(
            resolution__accepted_by_customer=True
        ).count()
        
        return (accepted / resolved.count()) * 100
    
    @classmethod
    def calculate_refund_rate(cls, start_date, end_date):
        """Calculate refund rate for period"""
        disputes = Dispute.objects.filter(
            filed_at__date__gte=start_date,
            filed_at__date__lte=end_date
        )
        
        total_amount = disputes.aggregate(total=Sum('disputed_amount'))['total'] or 0
        refunded_amount = disputes.filter(
            refund_issued=True
        ).aggregate(total=Sum('refund_amount'))['total'] or 0
        
        if total_amount == 0:
            return 0
        
        return (refunded_amount / total_amount) * 100