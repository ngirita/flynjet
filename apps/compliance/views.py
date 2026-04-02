import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from .models import ConsentRecord, DataSubjectRequest, BreachNotification, DataProcessingAgreement
from .forms import ConsentForm, DataSubjectRequestForm, DataProcessingAgreementForm, BreachNotificationForm
import logging

logger = logging.getLogger(__name__)



class ConsentManagementView(LoginRequiredMixin, TemplateView):
    """User consent management"""
    template_name = 'compliance/consent.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get current consents
        consents = {}
        for consent_type, _ in ConsentRecord.CONSENT_TYPES:
            latest = ConsentRecord.objects.filter(
                user=user,
                consent_type=consent_type
            ).order_by('-created_at').first()
            
            consents[consent_type] = {
                'granted': latest.granted if latest else False,
                'version': latest.version if latest else '1.0',
                'date': latest.created_at if latest else None
            }
        
        context['consents'] = consents
        context['form'] = ConsentForm()
        return context
    
    def post(self, request, *args, **kwargs):
        form = ConsentForm(request.POST)
        
        if form.is_valid():
            consent_type = form.cleaned_data['consent_type']
            granted = form.cleaned_data['granted']
            version = form.cleaned_data['version']
            
            # Record consent
            ConsentRecord.objects.create(
                user=request.user,
                consent_type=consent_type,
                version=version,
                granted=granted,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, "Consent preference saved successfully.")
            return redirect('compliance:consent')
        
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)


class DataSubjectRequestView(LoginRequiredMixin, CreateView):
    """Submit data subject request"""
    model = DataSubjectRequest
    form_class = DataSubjectRequestForm
    template_name = 'compliance/dsr_form.html'
    success_url = reverse_lazy('compliance:dsr_list')
    
    def form_valid(self, form):
        form.instance.requester_name = self.request.user.get_full_name() or self.request.user.email
        form.instance.requester_email = self.request.user.email
        form.instance.user = self.request.user
        return super().form_valid(form)


class DataSubjectRequestDetailView(LoginRequiredMixin, DetailView):
    """View data subject request details"""
    model = DataSubjectRequest
    template_name = 'compliance/dsr_detail.html'
    context_object_name = 'request_obj'
    
    def get_queryset(self):
        return DataSubjectRequest.objects.filter(user=self.request.user)


@csrf_exempt
def cookie_consent(request):
    """Handle cookie consent"""
    if request.method == 'POST':
        consent = request.POST.get('consent', 'false') == 'true'
        
        response = JsonResponse({'status': 'success'})
        
        # Set cookie
        max_age = 365 * 24 * 60 * 60  # 1 year
        response.set_cookie(
            'cookie_consent',
            'accepted' if consent else 'rejected',
            max_age=max_age,
            httponly=True,
            samesite='Lax'
        )
        
        # Record consent if user is authenticated
        if request.user.is_authenticated and consent:
            ConsentRecord.objects.create(
                user=request.user,
                consent_type='cookies',
                version='1.0',
                granted=True,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return response
    
    return JsonResponse({'status': 'error'}, status=400)


def request_data_export(request):
    """Request export of user data"""
    if not request.user.is_authenticated:
        messages.error(request, "Please login to request data export.")
        return redirect('accounts:login')
    
    # Create DSR
    dsr = DataSubjectRequest.objects.create(
        user=request.user,
        requester_name=request.user.get_full_name() or request.user.email,
        requester_email=request.user.email,
        request_type='access',
        description="Request for data export",
        status='pending'
    )
    
    messages.success(request, "Your data export request has been submitted. You will receive an email when your data is ready.")
    return redirect('compliance:dsr_detail', pk=dsr.id)


def request_account_deletion(request):
    """Request account deletion"""
    if not request.user.is_authenticated:
        messages.error(request, "Please login to request account deletion.")
        return redirect('accounts:login')
    
    # Create DSR
    dsr = DataSubjectRequest.objects.create(
        user=request.user,
        requester_name=request.user.get_full_name() or request.user.email,
        requester_email=request.user.email,
        request_type='erasure',
        description="Request for account deletion",
        status='pending'
    )
    
    messages.warning(request, "Your account deletion request has been submitted. This process may take up to 30 days.")
    return redirect('compliance:dsr_detail', pk=dsr.id)


@staff_member_required
def export_user_data(request, user_id):
    """Export all user data (admin only)"""
    from apps.accounts.models import User
    from apps.bookings.models import Booking
    from apps.payments.models import Payment
    
    user = get_object_or_404(User, id=user_id)
    
    # Collect all user data
    data = {
        'user': {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'user_type': user.user_type,
            'phone_number': str(user.phone_number) if user.phone_number else None,
        },
        'profile': {
            'nationality': user.profile.nationality if hasattr(user, 'profile') else None,
            'date_of_birth': user.profile.date_of_birth.isoformat() if hasattr(user, 'profile') and user.profile.date_of_birth else None,
        },
        'bookings': list(Booking.objects.filter(user=user).values()),
        'payments': list(Payment.objects.filter(user=user).values()),
        'consents': list(ConsentRecord.objects.filter(user=user).values()),
        'dsrs': list(DataSubjectRequest.objects.filter(user=user).values()),
    }
    
    # Create response
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="user_data_{user.id}.json"'
    json.dump(data, response, indent=2, default=str)
    
    return response