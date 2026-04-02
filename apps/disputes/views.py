import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import Dispute, DisputeMessage, DisputeEvidence, DisputeResolution
from .forms import DisputeForm, DisputeMessageForm, DisputeEvidenceForm
from apps.bookings.models import Booking
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings

class DisputeListView(LoginRequiredMixin, ListView):
    """User's disputes"""
    model = Dispute
    template_name = 'disputes/list.html'
    context_object_name = 'disputes'
    paginate_by = 10
    
    def get_queryset(self):
        return Dispute.objects.filter(user=self.request.user).order_by('-filed_at')

class CreateDisputeView(LoginRequiredMixin, CreateView):
    """Create a new dispute"""
    model = Dispute
    form_class = DisputeForm
    template_name = 'disputes/create.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(Booking, id=kwargs['booking_id'], user=request.user)
        
        # Check if already disputed
        existing_dispute = Dispute.objects.filter(booking=self.booking).first()
        if existing_dispute:
            messages.error(request, f"A dispute already exists for this booking: {existing_dispute.dispute_number}")
            return redirect('bookings:detail', pk=self.booking.id)
        
        return super().dispatch(request, *args, **kwargs)

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['booking'] = self.booking
        return context
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.booking = self.booking
        form.instance.disputed_amount = self.booking.total_amount_usd
        
        # 1. Save the dispute to the database first
        response = super().form_valid(form)
        dispute = self.object

        # 2. Prepare the email content
        context = {
            'dispute': dispute,
            'user': self.request.user,
        }
        html_content = render_to_string('emails/dispute_filed.html', context)

        # 3. Send the email
        email = EmailMessage(
            subject=f"Dispute Filed: {dispute.subject}",
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[self.request.user.email],
        )
        email.content_subtype = "html"  # This ensures the HTML is rendered
        
        try:
            email.send(fail_silently=False)
        except Exception as e:
            # Log the error if the mail server is down
            print(f"Email failed: {e}")

        return response
    
    def get_success_url(self):
        return reverse_lazy('disputes:detail', kwargs={'pk': self.object.pk})


class DisputeDetailView(LoginRequiredMixin, DetailView):
    """Dispute detail page"""
    model = Dispute
    template_name = 'disputes/detail.html'
    context_object_name = 'dispute'
    
    def get_queryset(self):
        return Dispute.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages'] = self.object.messages.all().order_by('created_at')
        context['evidence'] = self.object.evidence_items.all()
        context['message_form'] = DisputeMessageForm()
        context['evidence_form'] = DisputeEvidenceForm()
        return context


class AdminDisputeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin dispute management"""
    model = Dispute
    template_name = 'disputes/admin_list.html'
    context_object_name = 'disputes'
    paginate_by = 20
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.user_type in ['admin', 'agent']
    
    def get_queryset(self):
        status = self.request.GET.get('status', 'pending')
        return Dispute.objects.filter(status=status).order_by('-filed_at')


class AdminDisputeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Admin dispute detail"""
    model = Dispute
    template_name = 'disputes/admin_detail.html'
    context_object_name = 'dispute'
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.user_type in ['admin', 'agent']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages'] = self.object.messages.all().order_by('created_at')
        context['evidence'] = self.object.evidence_items.all()
        context['resolution_options'] = DisputeResolution.RESOLUTION_TYPES
        return context


@csrf_exempt
def add_message(request, pk):
    """Add message to dispute"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    dispute = get_object_or_404(Dispute, pk=pk)
    
    # Check permission
    if not (request.user == dispute.user or request.user.is_staff):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    form = DisputeMessageForm(request.POST, request.FILES)
    if form.is_valid():
        message = form.save(commit=False)
        message.dispute = dispute
        message.sender = request.user
        message.is_staff = request.user.is_staff
        message.save()
        
        return JsonResponse({
            'status': 'success',
            'message': {
                'id': message.id,
                'text': message.message,
                'sender': message.sender.email,
                'timestamp': message.created_at.isoformat(),
                'attachment': message.attachment.url if message.attachment else None
            }
        })
    
    return JsonResponse({'errors': form.errors}, status=400)


@csrf_exempt
def upload_evidence(request, pk):
    """Upload evidence for dispute"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    dispute = get_object_or_404(Dispute, pk=pk, user=request.user)
    
    form = DisputeEvidenceForm(request.POST, request.FILES)
    if form.is_valid():
        evidence = form.save(commit=False)
        evidence.dispute = dispute
        evidence.uploaded_by = request.user
        evidence.save()
        
        return JsonResponse({
            'status': 'success',
            'evidence': {
                'id': evidence.id,
                'file': evidence.file.url,
                'description': evidence.description,
                'type': evidence.evidence_type
            }
        })
    
    return JsonResponse({'errors': form.errors}, status=400)


@csrf_exempt
def assign_dispute(request, pk):
    """Assign dispute to agent/admin"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not (request.user.is_staff or request.user.user_type == 'admin'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    dispute = get_object_or_404(Dispute, pk=pk)
    agent_id = request.POST.get('agent_id')
    
    from apps.accounts.models import User
    agent = get_object_or_404(User, id=agent_id)
    
    dispute.assign_to(agent)
    
    return JsonResponse({'status': 'assigned', 'agent': agent.email})


@csrf_exempt
def resolve_dispute(request, pk):
    """Resolve dispute with resolution"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not (request.user.is_staff or request.user.user_type == 'admin'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    dispute = get_object_or_404(Dispute, pk=pk)
    
    resolution_type = request.POST.get('resolution_type')
    description = request.POST.get('description')
    refund_amount = request.POST.get('refund_amount', 0)
    
    # Create resolution
    resolution = DisputeResolution.objects.create(
        dispute=dispute,
        resolution_type=resolution_type,
        description=description,
        refund_amount=refund_amount,
        proposed_by=request.user
    )
    
    # Update dispute
    dispute.resolve(
        resolution=description,
        outcome=f"Resolved with {resolution.get_resolution_type_display()}",
        resolved_by=request.user,
        refund_amount=refund_amount
    )
    
    messages.success(request, f"Dispute {dispute.dispute_number} resolved")
    
    return redirect('disputes:admin_detail', pk=dispute.pk)