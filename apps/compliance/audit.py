from django.utils import timezone
from django.db import models
from .models import DataSubjectRequest, BreachNotification, ConsentRecord
import logging

logger = logging.getLogger(__name__)

class ComplianceAuditor:
    """Audit compliance activities"""
    
    @classmethod
    def run_compliance_audit(cls):
        """Run comprehensive compliance audit"""
        issues = []
        
        # Check pending DSRs
        pending_dsrs = DataSubjectRequest.objects.filter(
            status='pending',
            deadline__lt=timezone.now() + timezone.timedelta(days=7)
        )
        
        for dsr in pending_dsrs:
            issues.append({
                'type': 'dsr_deadline_approaching',
                'severity': 'warning',
                'message': f"DSR {dsr.request_number} deadline approaching: {dsr.deadline}",
                'item': dsr
            })
        
        # Check overdue DSRs
        overdue_dsrs = DataSubjectRequest.objects.filter(
            status__in=['pending', 'processing'],
            deadline__lt=timezone.now()
        )
        
        for dsr in overdue_dsrs:
            issues.append({
                'type': 'dsr_overdue',
                'severity': 'critical',
                'message': f"DSR {dsr.request_number} is overdue",
                'item': dsr
            })
        
        # Check open breaches
        open_breaches = BreachNotification.objects.filter(
            status__in=['detected', 'investigating']
        )
        
        for breach in open_breaches:
            issues.append({
                'type': 'open_breach',
                'severity': 'critical' if breach.severity in ['high', 'critical'] else 'warning',
                'message': f"Breach {breach.breach_number} is still open",
                'item': breach
            })
        
        return issues
    
    @classmethod
    def generate_audit_report(cls, start_date, end_date):
        """Generate compliance audit report"""
        from django.db.models import Count, Avg, F, Sum
        
        dsrs = DataSubjectRequest.objects.filter(
            submitted_at__date__gte=start_date,
            submitted_at__date__lte=end_date
        )
        
        breaches = BreachNotification.objects.filter(
            detected_at__date__gte=start_date,
            detected_at__date__lte=end_date
        )
        
        # Calculate average completion time
        completed_dsrs = dsrs.filter(
            status='completed',
            completed_at__isnull=False
        )
        
        avg_completion = None
        if completed_dsrs.exists():
            # Calculate average time difference
            time_diff = completed_dsrs.aggregate(
                avg_seconds=Avg(
                    models.ExpressionWrapper(
                        models.F('completed_at') - models.F('submitted_at'),
                        output_field=models.DurationField()
                    )
                )
            )['avg_seconds']
            
            if time_diff:
                avg_completion = time_diff.total_seconds() / 86400  # Convert to days
        
        report = {
            'period': f"{start_date} to {end_date}",
            'dsr_stats': {
                'total': dsrs.count(),
                'by_type': dict(dsrs.values_list('request_type').annotate(count=Count('id'))),
                'by_status': dict(dsrs.values_list('status').annotate(count=Count('id'))),
                'avg_completion_time_days': avg_completion,
            },
            'breach_stats': {
                'total': breaches.count(),
                'by_severity': dict(breaches.values_list('severity').annotate(count=Count('id'))),
                'by_status': dict(breaches.values_list('status').annotate(count=Count('id'))),
                'users_affected': breaches.aggregate(total=Sum('affected_users_count'))['total'] or 0,
            },
            'consent_stats': {
                'total_consents': ConsentRecord.objects.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                ).count(),
            }
        }
        
        return report

class DataProtectionImpact:
    """Data Protection Impact Assessment"""
    
    @classmethod
    def assess_risk(cls, project_description, data_categories, processing_purpose):
        """Assess risk level of processing activity"""
        risk_score = 0
        
        # High risk data categories
        high_risk_data = ['biometric', 'health', 'political', 'religious', 'genetic']
        for category in data_categories:
            if category in high_risk_data:
                risk_score += 30
        
        # Large scale processing
        if 'large_scale' in processing_purpose:
            risk_score += 20
        
        # Sensitive purpose
        sensitive_purposes = ['profiling', 'automated_decision', 'credit_scoring']
        for purpose in sensitive_purposes:
            if purpose in processing_purpose:
                risk_score += 25
        
        # Determine risk level
        if risk_score >= 50:
            return 'HIGH'
        elif risk_score >= 20:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    @classmethod
    def generate_dpia(cls, processing_activity):
        """Generate Data Protection Impact Assessment"""
        dpia = {
            'activity_name': processing_activity.name,
            'date': timezone.now().date(),
            'assessor': processing_activity.assessor,
            'risk_level': cls.assess_risk(
                processing_activity.description,
                processing_activity.data_categories,
                processing_activity.purpose
            ),
            'measures': {
                'technical': processing_activity.technical_measures,
                'organizational': processing_activity.organizational_measures,
            },
            'recommendations': cls.generate_recommendations(processing_activity),
            'approval_status': 'pending'
        }
        
        return dpia
    
    @classmethod
    def generate_recommendations(cls, processing_activity):
        """Generate recommendations based on risk assessment"""
        recommendations = []
        
        risk_level = cls.assess_risk(
            processing_activity.description,
            processing_activity.data_categories,
            processing_activity.purpose
        )
        
        if risk_level == 'HIGH':
            recommendations.extend([
                "Implement pseudonymization",
                "Conduct regular security audits",
                "Appoint a data protection officer",
                "Document all processing activities"
            ])
        elif risk_level == 'MEDIUM':
            recommendations.extend([
                "Review access controls",
                "Update privacy notices",
                "Implement data minimization"
            ])
        
        return recommendations