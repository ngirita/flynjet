from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Payment, Payout, RefundRequest
import csv
import io

class PaymentReconciler:
    """Reconcile payments with bank statements"""
    
    @classmethod
    def reconcile_payments(cls, start_date, end_date, bank_transactions):
        """Reconcile payments with bank transactions"""
        payments = Payment.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='completed'
        ).order_by('created_at')
        
        reconciled = []
        unmatched_payments = []
        unmatched_transactions = []
        
        # Match payments with bank transactions
        for payment in payments:
            matched = False
            for bank_txn in bank_transactions:
                if cls.matches_payment(payment, bank_txn):
                    reconciled.append({
                        'payment': payment,
                        'bank_transaction': bank_txn,
                        'matched_at': timezone.now()
                    })
                    matched = True
                    break
            
            if not matched:
                unmatched_payments.append(payment)
        
        # Find bank transactions without matching payments
        payment_refs = [p.transaction_id for p in payments]
        for bank_txn in bank_transactions:
            if bank_txn.get('reference') not in payment_refs:
                unmatched_transactions.append(bank_txn)
        
        return {
            'reconciled': reconciled,
            'unmatched_payments': unmatched_payments,
            'unmatched_transactions': unmatched_transactions,
            'total_reconciled': len(reconciled),
            'total_unmatched_payments': len(unmatched_payments),
            'total_unmatched_transactions': len(unmatched_transactions)
        }
    
    @classmethod
    def matches_payment(cls, payment, bank_transaction):
        """Check if payment matches bank transaction"""
        # Match by amount (within small tolerance)
        amount_tolerance = Decimal('0.01')
        amount_matches = abs(payment.amount_usd - Decimal(str(bank_transaction.get('amount', 0)))) <= amount_tolerance
        
        # Match by date (within 3 days)
        date_matches = abs((payment.created_at.date() - bank_transaction.get('date')).days) <= 3
        
        # Match by reference if available
        ref_matches = True
        if bank_transaction.get('reference'):
            ref_matches = payment.transaction_id in bank_transaction['reference']
        
        return amount_matches and date_matches and ref_matches
    
    @classmethod
    def generate_reconciliation_report(cls, start_date, end_date):
        """Generate reconciliation report"""
        payments = Payment.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Summary statistics
        total_payments = payments.count()
        total_amount = payments.aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0
        completed_payments = payments.filter(status='completed').count()
        failed_payments = payments.filter(status='failed').count()
        refunded_payments = payments.filter(status='refunded').count()
        
        # Payment method breakdown
        method_breakdown = payments.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount_usd')
        )
        
        # Daily totals
        daily_totals = payments.extra(
            {'day': "date(created_at)"}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount_usd')
        ).order_by('day')
        
        # Payouts
        payouts = Payout.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        report = {
            'period': f"{start_date} to {end_date}",
            'generated_at': timezone.now(),
            'summary': {
                'total_payments': total_payments,
                'total_amount': total_amount,
                'completed_payments': completed_payments,
                'failed_payments': failed_payments,
                'refunded_payments': refunded_payments,
                'total_payouts': payouts.count(),
                'total_payout_amount': payouts.aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0,
            },
            'method_breakdown': list(method_breakdown),
            'daily_totals': list(daily_totals),
        }
        
        return report
    
    @classmethod
    def export_to_csv(cls, payments):
        """Export payments to CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Transaction ID', 'Date', 'User', 'Amount', 'Currency',
            'Payment Method', 'Status', 'Booking Reference'
        ])
        
        # Write data
        for payment in payments:
            writer.writerow([
                payment.transaction_id,
                payment.created_at.strftime('%Y-%m-%d %H:%M'),
                payment.user.email,
                payment.amount_usd,
                payment.currency,
                payment.get_payment_method_display(),
                payment.get_status_display(),
                payment.booking.booking_reference if payment.booking else ''
            ])
        
        return output.getvalue()
    
    @classmethod
    def detect_anomalies(cls, days=30):
        """Detect anomalies in payment patterns"""
        start_date = timezone.now() - timedelta(days=days)
        payments = Payment.objects.filter(created_at__gte=start_date)
        
        anomalies = []
        
        # Calculate baseline statistics
        daily_counts = payments.extra(
            {'day': "date(created_at)"}
        ).values('day').annotate(count=Count('id'))
        
        if daily_counts:
            avg_count = sum(d['count'] for d in daily_counts) / len(daily_counts)
            std_count = (sum((d['count'] - avg_count) ** 2 for d in daily_counts) / len(daily_counts)) ** 0.5
            
            # Detect unusual volume
            for day in daily_counts:
                if abs(day['count'] - avg_count) > 2 * std_count:
                    anomalies.append({
                        'type': 'unusual_volume',
                        'date': day['day'],
                        'count': day['count'],
                        'expected': avg_count,
                        'deviation': abs(day['count'] - avg_count) / std_count
                    })
        
        # Detect unusual failure rates
        failure_rate = payments.filter(status='failed').count() / payments.count() if payments.count() > 0 else 0
        if failure_rate > 0.1:  # More than 10% failures
            anomalies.append({
                'type': 'high_failure_rate',
                'rate': failure_rate,
                'expected': 0.05
            })
        
        # Detect large refunds
        large_refunds = payments.filter(
            status='refunded',
            amount_usd__gt=10000
        ).count()
        if large_refunds > 3:
            anomalies.append({
                'type': 'large_refunds',
                'count': large_refunds,
                'threshold': 3
            })
        
        return anomalies

class PayoutReconciler:
    """Reconcile payouts to agents/partners"""
    
    @classmethod
    def calculate_commission(cls, booking, agent_rate=0.1):
        """Calculate commission for booking"""
        return booking.total_amount_usd * Decimal(str(agent_rate))
    
    @classmethod
    def generate_payout_report(cls, agent, start_date, end_date):
        """Generate payout report for agent"""
        from apps.bookings.models import Booking
        
        bookings = Booking.objects.filter(
            agent=agent,
            status='completed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        total_revenue = bookings.aggregate(Sum('total_amount_usd'))['total_amount_usd__sum'] or 0
        commission_rate = Decimal('0.1')  # 10%
        commission = total_revenue * commission_rate
        
        return {
            'agent': agent.email,
            'period': f"{start_date} to {end_date}",
            'total_bookings': bookings.count(),
            'total_revenue': total_revenue,
            'commission_rate': commission_rate,
            'commission_due': commission,
            'previous_payouts': Payout.objects.filter(
                recipient=agent,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0,
            'balance_due': commission
        }
    
    @classmethod
    def process_batch_payout(cls, payouts):
        """Process multiple payouts in batch"""
        results = []
        for payout in payouts:
            try:
                payout.mark_as_completed(f"BATCH{timezone.now().strftime('%Y%m%d')}")
                results.append({
                    'payout': payout.payout_number,
                    'status': 'success'
                })
            except Exception as e:
                results.append({
                    'payout': payout.payout_number,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return results