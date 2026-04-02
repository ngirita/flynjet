# apps/payments/api.py - REPLACE WITH THIS

from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Sum, Count
from django.db import models
from .models import Payment, PaymentMethod, RefundRequest, Payout, CryptoTransaction
from .serializers import (
    PaymentSerializer, PaymentCreateSerializer, PaymentDetailSerializer,
    PaymentMethodSerializer, RefundRequestSerializer, RefundRequestCreateSerializer,
    PayoutSerializer, CryptoTransactionSerializer
)
from .permissions import IsPaymentOwnerOrReadOnly, CanProcessRefund
from .card_utils import CardPaymentHandler
from .crypto_utils import CryptoPaymentHandler
from .services.paystack_service import PaystackService
from apps.bookings.models import Booking
import logging
import uuid

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Payment operations using Paystack.
    """
    queryset = Payment.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated, IsPaymentOwnerOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentCreateSerializer
        elif self.action in ['retrieve']:
            return PaymentDetailSerializer
        return PaymentSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or getattr(user, 'user_type', '') == 'admin':
            return Payment.objects.all()
        return Payment.objects.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process a payment using Paystack or Crypto"""
        payment = self.get_object()
        
        if payment.status != 'pending':
            return Response(
                {'error': f'Cannot process payment with status {payment.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = request.data.get('payment_method', payment.payment_method)
        
        if payment_method in ['visa', 'mastercard', 'amex', 'card']:
            # Process card payment via Paystack
            result = CardPaymentHandler.create_payment_intent(
                float(payment.amount_usd),
                metadata={
                    'payment_id': str(payment.id),
                    'user_id': str(request.user.id),
                    'booking_id': str(payment.booking.id) if payment.booking else None
                },
                email=request.user.email
            )
            
            if result['success']:
                payment.provider = 'paystack'
                payment.provider_payment_id = result['intent_id']
                payment.status = 'processing'
                payment.save()
                
                return Response({
                    'client_secret': result['client_secret'],
                    'authorization_url': result.get('authorization_url'),
                    'payment_id': payment.id
                })
            else:
                payment.status = 'failed'
                payment.failure_reason = result['error']
                payment.save()
                
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif payment_method in ['usdt_erc20', 'usdt_trc20', 'bitcoin', 'ethereum', 'crypto']:
            # Process crypto payment
            crypto_handler = CryptoPaymentHandler()
            wallet_address = self.get_crypto_wallet_address(payment_method)
            
            crypto_txn = CryptoTransaction.objects.create(
                payment=payment,
                crypto_type=payment_method,
                from_address='',
                to_address=wallet_address,
                crypto_amount=float(payment.amount_currency),
                usd_amount=float(payment.amount_usd),
                exchange_rate=float(payment.exchange_rate) if payment.exchange_rate else 1.0,
                status='pending'
            )
            
            payment.status = 'processing'
            payment.save()
            
            return Response({
                'wallet_address': wallet_address,
                'crypto_amount': crypto_txn.crypto_amount,
                'crypto_type': payment_method,
                'transaction_id': crypto_txn.id
            })
        
        return Response(
            {'error': 'Unsupported payment method'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a payment (for crypto payments)."""
        payment = self.get_object()
        transaction_hash = request.data.get('transaction_hash')
        
        try:
            crypto_txn = payment.crypto_details
            crypto_txn.transaction_hash = transaction_hash
            crypto_txn.status = 'confirming'
            crypto_txn.save()
            
            return Response({'message': 'Transaction is being confirmed'})
            
        except CryptoTransaction.DoesNotExist:
            return Response(
                {'error': 'No crypto transaction found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Process a refund for this payment."""
        payment = self.get_object()
        amount = request.data.get('amount', payment.amount_usd)
        reason = request.data.get('reason', '')
        
        if payment.status not in ['completed', 'paid']:
            return Response(
                {'error': 'Cannot refund payment that is not completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use CardPaymentHandler for Paystack refunds
        result = CardPaymentHandler.create_refund(
            payment.provider_payment_id,
            float(amount)
        )
        
        if result['success']:
            payment.process_refund(amount, reason, request.user)
            return Response({'message': 'Refund processed successfully'})
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get payment statistics for current user."""
        payments = self.get_queryset()
        
        stats = {
            'total_payments': payments.count(),
            'total_spent': payments.filter(status='completed').aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0,
            'pending_payments': payments.filter(status='pending').count(),
            'completed_payments': payments.filter(status='completed').count(),
            'failed_payments': payments.filter(status='failed').count(),
            'refunded_payments': payments.filter(status='refunded').count(),
        }
        
        method_breakdown = payments.values('payment_method').annotate(
            count=models.Count('id'),
            total=models.Sum('amount_usd')
        )
        stats['method_breakdown'] = list(method_breakdown)
        
        return Response(stats)
    
    def get_crypto_wallet_address(self, crypto_type):
        """Get wallet address for crypto payments from settings."""
        addresses = {
            'usdt_erc20': getattr(settings, 'TRUST_WALLET_USDT_ERC20', ''),
            'usdt_trc20': getattr(settings, 'TRUST_WALLET_USDT_TRC20', ''),
            'bitcoin': getattr(settings, 'TRUST_WALLET_BTC', ''),
            'ethereum': getattr(settings, 'TRUST_WALLET_ETH', ''),
            'crypto': getattr(settings, 'TRUST_WALLET_BTC', ''),  # Default to BTC
        }
        return addresses.get(crypto_type, '')


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """ViewSet for saved payment methods."""
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user, is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        payment_method = self.get_object()
        payment_method.is_default = True
        payment_method.save()
        return Response({'message': 'Default payment method updated'})
    
    @action(detail=True, methods=['post'])
    def delete(self, request, pk=None):
        payment_method = self.get_object()
        payment_method.is_active = False
        payment_method.save()
        return Response({'message': 'Payment method removed'})


class RefundRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for refund requests."""
    queryset = RefundRequest.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return RefundRequestCreateSerializer
        return RefundRequestSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or getattr(user, 'user_type', '') == 'admin':
            return RefundRequest.objects.all()
        return RefundRequest.objects.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        refund = self.get_object()
        
        if refund.status != 'pending':
            return Response(
                {'error': f'Cannot cancel refund with status {refund.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund.status = 'cancelled'
        refund.save()
        
        return Response({'message': 'Refund request cancelled'})


class CryptoTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing crypto transactions."""
    serializer_class = CryptoTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or getattr(user, 'user_type', '') == 'admin':
            return CryptoTransaction.objects.all()
        return CryptoTransaction.objects.filter(payment__user=user)
    
    @action(detail=True, methods=['get'])
    def check_status(self, request, pk=None):
        crypto_txn = self.get_object()
        return Response({
            'status': crypto_txn.status,
            'confirmations': crypto_txn.confirmations,
            'required_confirmations': crypto_txn.required_confirmations,
            'confirmation_percentage': crypto_txn.confirmation_percentage
        })


class PayoutViewSet(viewsets.ModelViewSet):
    """ViewSet for payouts (admin only)."""
    serializer_class = PayoutSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Payout.objects.all().order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        payout = self.get_object()
        
        if payout.status != 'pending':
            return Response(
                {'error': f'Cannot process payout with status {payout.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if payout.payout_method in ['bank_transfer', 'wire_transfer']:
            payout.mark_as_completed(f"BANK-{payout.payout_number}")
        elif payout.payout_method in ['bitcoin', 'usdt_erc20', 'usdt_trc20']:
            payout.mark_as_completed(f"CRYPTO-{payout.payout_number}")
        else:
            return Response(
                {'error': 'Unsupported payout method'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({'message': 'Payout processed successfully'})


class ExchangeRateView(generics.GenericAPIView):
    """Get current exchange rates for cryptocurrencies."""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        from django.core.cache import cache
        
        rates = {
            'usdt_erc20': cache.get('exchange_rate_usdt_erc20_usd', 1.0),
            'usdt_trc20': cache.get('exchange_rate_usdt_trc20_usd', 1.0),
            'bitcoin': cache.get('exchange_rate_bitcoin_usd', 0),
            'ethereum': cache.get('exchange_rate_ethereum_usd', 0),
        }
        
        return Response(rates)


class UserPaymentMethodsView(generics.ListAPIView):
    """List payment methods for current user."""
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return PaymentMethod.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-is_default', '-last_used')