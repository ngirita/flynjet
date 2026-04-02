import uuid
import hmac
import hashlib
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, TemplateView, View
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.conf import settings
from django.http import HttpResponse, JsonResponse  # ADD JsonResponse HERE
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import Payment, RefundRequest, CryptoTransaction
from .forms import PaymentForm, RefundRequestForm
from .services.paystack_service import PaystackService
from apps.bookings.models import Booking, BookingHistory, Contract  # ADD Contract HERE
from apps.accounts.models import User  # ADD User HERE
from apps.documents.models import GeneratedDocument

import logging
logger = logging.getLogger(__name__)


class PaymentCreateView(LoginRequiredMixin, CreateView):
    """Create and initialize payment"""
    model = Payment
    form_class = PaymentForm
    template_name = 'payments/payment_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_id = self.kwargs.get('booking_id')
        if booking_id:
            booking = get_object_or_404(Booking, id=booking_id, user=self.request.user)
            context['booking'] = booking
            context['paystack_public_key'] = settings.PAYSTACK_PUBLIC_KEY
        return context
    
    def get_initial(self):
        initial = super().get_initial()
        booking_id = self.kwargs.get('booking_id')
        if booking_id:
            booking = get_object_or_404(Booking, id=booking_id, user=self.request.user)
            initial['amount_usd'] = booking.amount_due
        return initial
    
    def post(self, request, *args, **kwargs):
        terms_agreed = request.POST.get('terms')
        if not terms_agreed:
            messages.error(request, 'You must agree to the Terms and Conditions to proceed.')
            booking_id = self.kwargs.get('booking_id')
            return redirect('bookings:review', pk=booking_id)
        
        # Get payment method from POST - try both possible field names
        payment_method = request.POST.get('selected_payment_method')
        if not payment_method:
            payment_method = request.POST.get('payment_method')
        
        # Handle case where payment_method might be a list (if multiple inputs with same name)
        if isinstance(payment_method, list):
            payment_method = payment_method[-1]
        
        # For all payment methods, bypass form validation since the form expects card details
        # that aren't present in the booking review template
        form = self.get_form()
        form.instance.user = request.user
        
        # Set the amount from the booking
        booking_id = self.kwargs.get('booking_id')
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        form.instance.amount_usd = booking.amount_due
        
        # Call form_valid directly
        return self.form_valid(form)
    
    def form_valid(self, form):
        booking_id = self.kwargs.get('booking_id')
        booking = get_object_or_404(Booking, id=booking_id, user=self.request.user)
        
        payment_method = self.request.POST.get('payment_method', 'paystack')
        
        # ========== CHECK IF PAYMENT METHOD IS ENABLED IN DATABASE ==========
        from apps.core.models import PaymentMethodConfig, BankDetail, CryptoWallet
        
        try:
            method_config = PaymentMethodConfig.objects.get(method_key=payment_method)
            if not method_config.is_enabled:
                messages.error(self.request, f'Payment method "{method_config.display_name}" is currently disabled.')
                return redirect('bookings:review', pk=booking_id)
            if method_config.is_maintenance:
                messages.error(self.request, method_config.maintenance_message or f'Payment method "{method_config.display_name}" is under maintenance. Please use another method.')
                return redirect('bookings:review', pk=booking_id)
        except PaymentMethodConfig.DoesNotExist:
            # If method not found in config, still allow but log warning
            logger.warning(f"Payment method '{payment_method}' not found in PaymentMethodConfig")
        # ==========================================================
        
        transaction_id = f"PAY{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
        
        # Create payment record
        payment = Payment.objects.create(
            user=self.request.user,
            booking=booking,
            transaction_id=transaction_id,
            amount_usd=booking.amount_due,
            amount_currency=booking.amount_due,
            currency='USD',
            payment_method=payment_method,
            payment_type='booking',
            status='pending',
            metadata={
                'booking_reference': booking.booking_reference,
                'payment_method': payment_method
            }
        )
        
        # Handle different payment methods
        if payment_method in ['crypto', 'crypto_all', 'usdt_erc20', 'usdt_trc20', 'bitcoin', 'ethereum']:
            payment.provider = 'crypto'
            payment.save(update_fields=['provider'])
            
            # Get crypto wallets from database
            crypto_wallets = CryptoWallet.objects.filter(is_active=True).order_by('sort_order')
            
            # ========== ADD DEBUG HERE ==========
            import sys
            print("\n" + "="*60, file=sys.stderr)
            print("CRYPTO PAYMENT SELECTED", file=sys.stderr)
            print(f"Payment Method: {payment_method}", file=sys.stderr)
            print(f"Total crypto wallets found: {crypto_wallets.count()}", file=sys.stderr)
            for w in crypto_wallets:
                print(f"  - {w.crypto_type} ({w.network}): active={w.is_active}", file=sys.stderr)
                print(f"    Address: {w.wallet_address[:30]}...", file=sys.stderr)
            print("="*60 + "\n", file=sys.stderr)
            
            # Check if wallets exist
            if not crypto_wallets.exists():
                print("ERROR: No active crypto wallets found!", file=sys.stderr)
                messages.error(self.request, 'No active cryptocurrency wallets available. Please contact support or try another payment method.')
                return redirect('bookings:review', pk=booking_id)
            
            # Send email with crypto instructions using database wallets
            try:
                self.send_crypto_instructions_email_db(payment, booking, crypto_wallets)
                print("Crypto email sent successfully", file=sys.stderr)
            except Exception as e:
                print(f"ERROR sending crypto email: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                messages.error(self.request, f'Error sending crypto instructions: {str(e)}')
                return redirect('bookings:review', pk=booking_id)
            
            messages.info(self.request, 'Please check your email for cryptocurrency payment instructions.')
            return redirect('payments:payment_instructions', pk=payment.id)
        
        elif payment_method in ['bank_transfer', 'wire_transfer']:
            payment.provider = 'manual'
            payment.save(update_fields=['provider'])
            
            # Get bank details from database
            default_bank = BankDetail.objects.filter(is_active=True, is_default=True).first()
            if not default_bank:
                default_bank = BankDetail.objects.filter(is_active=True).first()
            
            # Send email with bank transfer instructions using database bank details
            self.send_bank_transfer_instructions_email_db(payment, booking, default_bank)
            messages.info(self.request, 'Please check your email for bank transfer instructions.')
            return redirect('payments:payment_instructions', pk=payment.id)
        
        else:
            # Card payment via Paystack
            # Check if Paystack is enabled in database
            try:
                paystack_config = PaymentMethodConfig.objects.get(method_key='paystack')
                if not paystack_config.is_enabled or paystack_config.is_maintenance:
                    messages.error(self.request, 'Card payments are currently unavailable. Please use another payment method.')
                    return redirect('bookings:review', pk=booking_id)
            except PaymentMethodConfig.DoesNotExist:
                pass
            
            payment.provider = 'paystack'
            payment.save(update_fields=['provider'])
            
            paystack = PaystackService()
            result = paystack.initialize_transaction(
                email=self.request.user.email,
                amount=booking.amount_due,
                currency='USD',
                reference=transaction_id,
                metadata={
                    'booking_id': str(booking.id),
                    'user_id': str(self.request.user.id),
                    'payment_id': str(payment.id),
                    'booking_reference': booking.booking_reference
                }
            )
            
            if result['success']:
                payment.provider_payment_id = result.get('reference', transaction_id)
                payment.save(update_fields=['provider_payment_id'])
                
                self.request.session['pending_payment_id'] = str(payment.id)
                return redirect(result['authorization_url'])
            else:
                payment.mark_as_failed(result['message'])
                messages.error(self.request, f"Payment initialization failed: {result['message']}")
                return redirect('bookings:review', pk=booking_id)
                
    def send_crypto_instructions_email_db(self, payment, booking, crypto_wallets):
        """Send crypto payment instructions using database wallets"""
        try:
            subject = f"Crypto Payment Instructions - Booking {booking.booking_reference}"
            
            # Build crypto addresses from database
            crypto_addresses = {}
            for wallet in crypto_wallets:
                crypto_addresses[wallet.crypto_type] = {
                    'address': wallet.wallet_address,
                    'network': wallet.get_network_display(),
                    'min_deposit': float(wallet.min_deposit),
                    'notes': wallet.notes
                }
            
            context = {
                'payment': payment,
                'booking': booking,
                'user': self.request.user,
                'crypto_addresses': crypto_addresses,
                'crypto_wallets': crypto_wallets,
            }
            
            html_message = render_to_string('emails/crypto_payment_instructions.html', context)
            plain_message = render_to_string('emails/crypto_payment_instructions.txt', context)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [self.request.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Crypto instructions email sent for payment {payment.transaction_id}")
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to send crypto email: {e}")
            logger.error(traceback.format_exc())
            # Re-raise to see the error in the form
            raise
    
    def send_bank_transfer_instructions_email_db(self, payment, booking, bank_detail):
        """Send bank transfer instructions using database bank details"""
        
        # DEBUG: Print to console
        import sys
        print("\n" + "="*60, file=sys.stderr)
        print("📧 SENDING BANK TRANSFER EMAIL", file=sys.stderr)
        print(f"Bank detail object: {bank_detail}", file=sys.stderr)
        if bank_detail:
            print(f"✓ Bank detail exists!", file=sys.stderr)
            print(f"  - Bank Name: {bank_detail.bank_name}", file=sys.stderr)
            print(f"  - Account Name: {bank_detail.account_name}", file=sys.stderr)
            print(f"  - Account Number: {bank_detail.account_number}", file=sys.stderr)
            print(f"  - Swift Code: {bank_detail.swift_code}", file=sys.stderr)
            print(f"  - Active: {bank_detail.is_active}", file=sys.stderr)
        else:
            print("❌ ERROR: bank_detail is None or empty!", file=sys.stderr)
            print("Check if there are any BankDetail records with is_active=True", file=sys.stderr)
        print("="*60 + "\n", file=sys.stderr)
        
        subject = f"Bank Transfer Instructions - Booking {booking.booking_reference}"
        
        context = {
            'payment': payment,
            'booking': booking,
            'user': self.request.user,
            'bank_detail': bank_detail,
        }
        
        html_message = render_to_string('emails/bank_transfer_instructions.html', context)
        plain_message = render_to_string('emails/bank_transfer_instructions.txt', context)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [self.request.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Bank transfer instructions email sent for payment {payment.transaction_id}")

    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        booking_id = self.kwargs.get('booking_id')
        return redirect('bookings:review', pk=booking_id)


class PaymentVerifyView(LoginRequiredMixin, View):
    """Verify Paystack payment after callback"""
    
    def get(self, request, *args, **kwargs):
        reference = request.GET.get('reference')
        transaction_id = request.GET.get('trxref')
        
        ref = reference or transaction_id
        
        if not ref:
            messages.error(request, 'No payment reference found.')
            return redirect('payments:list')
        
        try:
            payment = Payment.objects.get(provider_payment_id=ref)
            
            # ========== ADD THIS CHECK ==========
            # Verify payment method is still enabled (security check)
            from apps.core.models import PaymentMethodConfig
            try:
                method_config = PaymentMethodConfig.objects.get(method_key=payment.payment_method)
                if not method_config.is_enabled or method_config.is_maintenance:
                    payment.mark_as_failed(f"Payment method {method_config.display_name} is no longer available")
                    messages.error(request, f'Payment method is no longer available. Please contact support.')
                    if payment.booking:
                        return redirect('bookings:review', pk=payment.booking.id)
                    return redirect('payments:list')
            except PaymentMethodConfig.DoesNotExist:
                pass
            # ==================================
            
            paystack = PaystackService()
            result = paystack.verify_transaction(ref)
            
            if result['success']:
                payment.mark_as_completed()
                messages.success(request, f'Payment of ${payment.amount_usd:,.2f} was successful!')
                return redirect('payments:success', payment_id=payment.id)
            else:
                payment.mark_as_failed(result['message'])
                messages.error(request, f'Payment verification failed: {result["message"]}')
                
                if payment.booking:
                    return redirect('bookings:review', pk=payment.booking.id)
                
        except Payment.DoesNotExist:
            messages.error(request, 'Payment record not found.')
        
        return redirect('payments:list')


class PaymentInstructionsView(LoginRequiredMixin, DetailView):
    """Show confirmation page with message that instructions were emailed"""
    model = Payment
    template_name = 'payments/payment_instructions.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.get_object()
        
        context['payment_method'] = payment.payment_method
        context['transaction_id'] = payment.transaction_id
        context['booking'] = payment.booking
        
        return context


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """Payment success page with links to invoice and ticket"""
    template_name = 'payments/payment_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment_id = self.kwargs.get('payment_id')
        payment = get_object_or_404(Payment, id=payment_id, user=self.request.user)
        
        context['payment'] = payment
        context['booking'] = payment.booking
        
        # Get existing documents (generated by signal)
        context['invoice'] = GeneratedDocument.objects.filter(
            booking=payment.booking,
            document_type='invoice'
        ).first()
        
        context['ticket'] = GeneratedDocument.objects.filter(
            booking=payment.booking,
            document_type='ticket'
        ).first()
        
        # Add download URLs for the documents
        if context['invoice']:
            context['invoice_url'] = reverse('documents:download', args=[context['invoice'].id])
        if context['ticket']:
            context['ticket_url'] = reverse('documents:download', args=[context['ticket'].id])
        
        return context


class PaymentListView(LoginRequiredMixin, ListView):
    """List user payments"""
    model = Payment
    template_name = 'payments/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')


class PaymentDetailView(LoginRequiredMixin, DetailView):
    """Payment details view"""
    model = Payment
    template_name = 'payments/payment_detail.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


class RefundRequestView(LoginRequiredMixin, CreateView):
    """Request refund for a booking"""
    model = RefundRequest
    form_class = RefundRequestForm
    template_name = 'payments/refund_request.html'
    success_url = reverse_lazy('payments:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_id = self.kwargs.get('booking_id')
        context['booking'] = get_object_or_404(Booking, id=booking_id, user=self.request.user)
        return context
    
    def form_valid(self, form):
        booking_id = self.kwargs.get('booking_id')
        booking = get_object_or_404(Booking, id=booking_id, user=self.request.user)
        
        form.instance.user = self.request.user
        form.instance.booking = booking
        form.instance.requested_amount = booking.amount_paid
        
        messages.success(self.request, 'Refund request submitted successfully!')
        return super().form_valid(form)


@method_decorator(csrf_exempt, name='dispatch')
class PaystackWebhookView(View):
    """Handle Paystack webhook events"""
    
    def post(self, request, *args, **kwargs):
        signature = request.headers.get('x-paystack-signature')
        
        if not signature:
            return HttpResponse(status=400)
        
        expected_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return HttpResponse(status=401)
        
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)
        
        event = payload.get('event')
        data = payload.get('data')
        
        if event == 'charge.success':
            reference = data.get('reference')
            try:
                payment = Payment.objects.get(provider_payment_id=reference)
                if payment.status != 'completed':
                    payment.mark_as_completed()
                    logger.info(f"Payment {payment.id} completed via webhook")
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for reference: {reference}")
        
        elif event == 'charge.failed':
            reference = data.get('reference')
            error_message = data.get('gateway_response', 'Payment failed')
            try:
                payment = Payment.objects.get(provider_payment_id=reference)
                payment.mark_as_failed(error_message)
            except Payment.DoesNotExist:
                pass
        
        return HttpResponse(status=200)
    

# apps/payments/views.py - REPLACE THE ENTIRE ContractPaymentView class

class ContractPaymentView(View):
    """Payment page accessed via contract link - handles authentication first"""
    
    def get(self, request, token):
        from apps.bookings.models import Contract
        from apps.bookings.models import Booking
        from apps.accounts.models import User
        from apps.payments.models import Payment
        from apps.airports.models import Airport
        from django.shortcuts import redirect
        from django.utils import timezone
        from decimal import Decimal
        from math import radians, sin, cos, sqrt, atan2
        import uuid
        
        def calculate_distance(lat1, lon1, lat2, lon2):
            """Calculate great-circle distance between two points in km"""
            R = 6371
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        try:
            contract = Contract.objects.get(payment_link_token=token)
            
            # Check if expired
            if contract.payment_link_expiry and contract.payment_link_expiry < timezone.now():
                messages.error(request, 'This payment link has expired.')
                return redirect('core:home')
            
            # Check if booking already exists
            if contract.booking:
                # If booking exists but user is not logged in, redirect to login
                if not request.user.is_authenticated:
                    request.session['pending_contract_token'] = token
                    messages.info(request, 'Please log in to view your booking.')
                    return redirect('accounts:login')
                return redirect('bookings:review', pk=contract.booking.id)
            
            # ========== HANDLE AUTHENTICATION ==========
            
            # Case 1: User is already logged in
            if request.user.is_authenticated:
                user = request.user
                
                # Optional: Warn if email mismatch
                if user.email.lower() != contract.client_email.lower():
                    messages.warning(
                        request, 
                        f'Note: This contract was created for {contract.client_email}. '
                        f'You are logged in as {user.email}. The booking will be associated with your account.'
                    )
                
                # Create booking with logged-in user
                booking = self.create_booking_from_contract(contract, user, token, request)
                
                # Clear pending session data
                self.clear_pending_session(request)
                
                messages.success(request, f'Booking {booking.booking_reference} created! Please complete your payment.')
                return redirect('bookings:review', pk=booking.id)
            
            # Case 2: Not logged in - check if user exists by email
            try:
                existing_user = User.objects.get(email=contract.client_email)
                
                # User exists but not logged in - store token and redirect to login
                request.session['pending_contract_token'] = token
                request.session['pending_action'] = 'create_booking'
                request.session['pending_contract_email'] = contract.client_email
                
                messages.info(request, f'Please log in to complete your booking for {contract.client_email}')
                return redirect('accounts:login')
                
            except User.DoesNotExist:
                # Case 3: New user - redirect to signup with pre-filled data
                request.session['pending_contract_token'] = token
                request.session['pending_action'] = 'create_booking'
                
                # Pre-fill signup form with contract data
                name_parts = contract.client_name.split()
                request.session['signup_prefill'] = {
                    'email': contract.client_email,
                    'first_name': name_parts[0] if name_parts else '',
                    'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                }
                
                messages.info(request, 'Please create an account to complete your booking.')
                return redirect('accounts:register')
            
        except Contract.DoesNotExist:
            messages.error(request, 'Contract not found.')
            return redirect('core:home')
        except Exception as e:
            logger.error(f"Contract payment error: {e}")
            messages.error(request, f'Error processing payment: {str(e)}')
            return redirect('core:home')
    
    def create_booking_from_contract(self, contract, user, token, request):
        """Helper method to create booking from contract"""
        from apps.bookings.models import Booking
        from apps.payments.models import Payment
        from apps.airports.models import Airport
        from django.utils import timezone
        from decimal import Decimal
        from math import radians, sin, cos, sqrt, atan2
        import uuid
        
        def calculate_distance(lat1, lon1, lat2, lon2):
            R = 6371
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        # Calculate flight details
        duration = contract.arrival_datetime - contract.departure_datetime
        flight_duration_hours = Decimal(str(duration.total_seconds() / 3600))
        
        # Calculate flight distance
        flight_distance_km = 0
        flight_distance_nm = 0
        
        try:
            dep_airport = Airport.objects.get(iata_code=contract.departure_airport)
            arr_airport = Airport.objects.get(iata_code=contract.arrival_airport)
            
            if dep_airport.latitude and dep_airport.longitude and arr_airport.latitude and arr_airport.longitude:
                flight_distance_km = calculate_distance(
                    dep_airport.latitude, dep_airport.longitude,
                    arr_airport.latitude, arr_airport.longitude
                )
                flight_distance_nm = flight_distance_km * 0.539957
                
        except Airport.DoesNotExist:
            if contract.aircraft and contract.aircraft.max_range_nm:
                flight_distance_nm = contract.aircraft.max_range_nm * 0.5
                flight_distance_km = flight_distance_nm * 1.852
        
        flight_distance_nm = int(flight_distance_nm)
        flight_distance_km = int(flight_distance_km)
        
        # Calculate tax amount
        subtotal = (contract.base_price_usd + contract.fuel_surcharge_usd + 
                   contract.handling_fee_usd + contract.catering_cost_usd + 
                   contract.insurance_cost_usd - contract.discount_amount_usd)
        tax_amount = subtotal * Decimal('0.10')
        
        # Create booking
        booking = Booking.objects.create(
            user=user,
            aircraft=contract.aircraft,
            flight_type='one_way',
            departure_airport=contract.departure_airport,
            arrival_airport=contract.arrival_airport,
            departure_datetime=contract.departure_datetime,
            arrival_datetime=contract.arrival_datetime,
            passenger_count=contract.passenger_count,
            source='contract',
            
            flight_duration_hours=flight_duration_hours,
            flight_distance_nm=flight_distance_nm,
            flight_distance_km=flight_distance_km,
            
            base_price_usd=contract.base_price_usd,
            fuel_surcharge_usd=contract.fuel_surcharge_usd,
            handling_fee_usd=contract.handling_fee_usd,
            catering_cost_usd=contract.catering_cost_usd,
            insurance_cost_usd=contract.insurance_cost_usd,
            discount_amount_usd=contract.discount_amount_usd,
            tax_amount_usd=tax_amount,
            total_amount_usd=contract.total_amount_usd,
            
            amount_paid=Decimal('0.00'),
            amount_due=contract.total_amount_usd,
            payment_due_date=contract.payment_link_expiry or (timezone.now() + timezone.timedelta(days=7)),
            
            preferred_currency='USD',
            exchange_rate=Decimal('1.000000'),
            total_amount_preferred=contract.total_amount_usd,
            
            status='pending',
            payment_status='pending',
            
            crew_count=2,
            cargo_weight_kg=Decimal('0.00'),
            baggage_weight_kg=Decimal('0.00'),
            passengers=[],
            catering_options=[],
            ground_transportation_required=False,
            ground_transportation_details={},
            hotel_required=False,
            hotel_details={},
            insurance_purchased=False,
            insurance_premium=Decimal('0.00'),
            cancellation_policy='standard',
            terms_accepted=False,
        )
        
        # Copy enquiry data
        enquiry = contract.enquiry
        if enquiry:
            if enquiry.special_requests:
                booking.special_requests = enquiry.special_requests
            
            if enquiry.catering_requirements:
                booking.dietary_requirements = enquiry.catering_requirements
            
            if enquiry.amenities:
                booking.catering_options = enquiry.amenities
            
            if enquiry.ground_transportation:
                booking.ground_transportation_required = True
            
            if enquiry.hotel_accommodation:
                booking.hotel_required = True
            
            booking.save()
        
        # Link booking to contract
        contract.booking = booking
        contract.status = 'payment_initiated'
        contract.save()
        
        # Create pending payment record
        transaction_id = f"PAY{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
        
        Payment.objects.create(
            user=user,
            booking=booking,
            transaction_id=transaction_id,
            amount_usd=contract.total_amount_usd,
            amount_currency=contract.total_amount_usd,
            currency='USD',
            payment_method='pending',
            payment_type='booking',
            status='pending',
            provider='pending',
            metadata={
                'contract_number': contract.contract_number,
                'contract_token': token,
                'from_contract': True,
                'enquiry_id': str(contract.enquiry.id) if contract.enquiry else None
            }
        )
        
        return booking
    
    def clear_pending_session(self, request):
        """Clear pending contract session data"""
        keys = ['pending_contract_token', 'pending_action', 'pending_contract_email', 'signup_prefill']
        for key in keys:
            if key in request.session:
                del request.session[key]
    
    def post(self, request, token):
        # POST not needed - redirect to GET which handles everything
        return self.get(request, token)