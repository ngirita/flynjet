from rest_framework import serializers
from .models import Payment, PaymentMethod, RefundRequest, Payout, CryptoTransaction
from apps.bookings.serializers import BookingSerializer
from apps.accounts.serializers import UserSerializer

class PaymentSerializer(serializers.ModelSerializer):
    """Basic Payment serializer"""
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['transaction_id', 'status', 'payment_date', 'created_at', 'updated_at']


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""
    class Meta:
        model = Payment
        fields = [
            'booking', 'payment_method', 'payment_type',
            'amount_usd', 'currency'
        ]
    
    def validate(self, data):
        # Validate that booking exists and is not already paid
        if data.get('booking'):
            if data['booking'].payment_status == 'paid':
                raise serializers.ValidationError("This booking is already paid")
            
            # Check if amount matches booking amount
            if data['amount_usd'] != data['booking'].amount_due:
                raise serializers.ValidationError(
                    f"Payment amount must be {data['booking'].amount_due} USD"
                )
        
        return data
    
    def create(self, validated_data):
        # Generate transaction ID
        import uuid
        validated_data['transaction_id'] = f"TXN{uuid.uuid4().hex[:12].upper()}"
        
        # Set user from context
        validated_data['user'] = self.context['request'].user
        
        return super().create(validated_data)


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Detailed Payment serializer with related objects"""
    booking_details = BookingSerializer(source='booking', read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['transaction_id', 'status', 'payment_date', 'created_at', 'updated_at']


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for saved payment methods"""
    class Meta:
        model = PaymentMethod
        exclude = ['user']
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_used']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class RefundRequestSerializer(serializers.ModelSerializer):
    """Basic RefundRequest serializer"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    booking_reference = serializers.CharField(source='booking.booking_reference', read_only=True)
    
    class Meta:
        model = RefundRequest
        fields = '__all__'
        read_only_fields = ['request_number', 'status', 'created_at', 'updated_at']


class RefundRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating refund requests"""
    class Meta:
        model = RefundRequest
        fields = ['booking', 'reason', 'description', 'requested_amount', 'supporting_documents']
    
    def validate(self, data):
        # Check if user already has a pending refund for this booking
        user = self.context['request'].user
        booking = data.get('booking')
        
        if RefundRequest.objects.filter(
            user=user, 
            booking=booking, 
            status__in=['pending', 'approved']
        ).exists():
            raise serializers.ValidationError(
                "You already have a pending or approved refund request for this booking"
            )
        
        # Check if requested amount is valid
        if data['requested_amount'] > booking.amount_paid:
            raise serializers.ValidationError(
                f"Refund amount cannot exceed {booking.amount_paid} USD"
            )
        
        return data
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['status'] = 'pending'
        return super().create(validated_data)


class RefundRequestDetailSerializer(serializers.ModelSerializer):
    """Detailed RefundRequest serializer"""
    user_details = UserSerializer(source='user', read_only=True)
    booking_details = BookingSerializer(source='booking', read_only=True)
    reviewed_by_details = UserSerializer(source='reviewed_by', read_only=True)
    processed_by_details = UserSerializer(source='processed_by', read_only=True)
    
    class Meta:
        model = RefundRequest
        fields = '__all__'
        read_only_fields = ['request_number', 'status', 'created_at', 'updated_at']


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for payouts"""
    recipient_email = serializers.EmailField(source='recipient.email', read_only=True)
    recipient_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Payout
        fields = '__all__'
        read_only_fields = ['payout_number', 'status', 'created_at', 'updated_at']
    
    def get_recipient_name(self, obj):
        return obj.recipient.get_full_name() or obj.recipient.email
    
    def validate(self, data):
        # Only admin can create/update payouts
        request = self.context.get('request')
        if request and not request.user.is_staff:
            raise serializers.ValidationError("Only administrators can manage payouts")
        return data


class CryptoTransactionSerializer(serializers.ModelSerializer):
    """Serializer for crypto transactions"""
    payment_reference = serializers.CharField(source='payment.transaction_id', read_only=True)
    
    class Meta:
        model = CryptoTransaction
        fields = '__all__'
        read_only_fields = [
            'id', 'first_seen', 'last_checked', 'completed_at',
            'confirmations', 'confirmation_percentage'
        ]


class CryptoTransactionDetailSerializer(serializers.ModelSerializer):
    """Detailed crypto transaction serializer"""
    payment_details = PaymentSerializer(source='payment', read_only=True)
    
    class Meta:
        model = CryptoTransaction
        fields = '__all__'


class PaymentStatsSerializer(serializers.Serializer):
    """Serializer for payment statistics"""
    total_payments = serializers.IntegerField()
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_payments = serializers.IntegerField()
    completed_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    refunded_payments = serializers.IntegerField()
    method_breakdown = serializers.ListField(child=serializers.DictField())


class ExchangeRateSerializer(serializers.Serializer):
    """Serializer for exchange rates"""
    usdt_erc20 = serializers.FloatField()
    usdt_trc20 = serializers.FloatField()
    bitcoin = serializers.FloatField()
    ethereum = serializers.FloatField()