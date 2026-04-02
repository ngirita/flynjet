from django.shortcuts import render, redirect
from django.views.generic import TemplateView, ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from .models import FAQ, Testimonial, SupportTicket, SupportMessage, NewsletterSubscriber
from .forms import ContactForm, SupportTicketForm
import logging

logger = logging.getLogger(__name__)

# ===== HEALTH CHECK VIEW =====

def health_check(request):
    """Health check endpoint for monitoring"""
    health_data = {
        'status': 'healthy',
        'checks': {}
    }
    all_healthy = True
    
    # Check database
    try:
        connections['default'].cursor()
        health_data['checks']['database'] = 'connected'
    except OperationalError as e:
        health_data['checks']['database'] = f'error: {str(e)}'
        all_healthy = False
        logger.error(f"Database health check failed: {e}")
    
    # Check cache (if configured)
    try:
        cache.set('health_check_test', 'ok', timeout=1)
        test_value = cache.get('health_check_test')
        if test_value == 'ok':
            health_data['checks']['cache'] = 'working'
        else:
            health_data['checks']['cache'] = 'failed: cache write/read mismatch'
            all_healthy = False
    except Exception as e:
        health_data['checks']['cache'] = f'error: {str(e)}'
        all_healthy = False
        logger.error(f"Cache health check failed: {e}")
    
    # Overall status
    if not all_healthy:
        health_data['status'] = 'unhealthy'
    
    status_code = 200 if all_healthy else 503
    return JsonResponse(health_data, status=status_code)

# ===== MAIN VIEWS =====

class HomeView(TemplateView):
    template_name = 'index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['testimonials'] = Testimonial.objects.filter(is_published=True, is_verified=True)[:5]
        
        # Add reviews
        from apps.reviews.models import Review, Testimonial as ReviewTestimonial
        context['featured_reviews'] = Review.objects.filter(
            status__in=['approved', 'featured']
        ).order_by('-created_at')[:6]
        context['featured_testimonials'] = ReviewTestimonial.objects.filter(
            is_featured=True, is_verified=True
        ).order_by('display_order')[:3]
        
        return context

class AboutView(TemplateView):
    template_name = 'core/about.html'

class ServicesView(TemplateView):
    template_name = 'core/services.html'

class ContactView(TemplateView):
    template_name = 'core/contact.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ContactForm()
        return context
    
    def post(self, request, *args, **kwargs):
        form = ContactForm(request.POST)
        if form.is_valid():
            # Send email
            form.send_email()
            messages.success(request, 'Thank you for your message. We will get back to you soon!')
            return redirect('core:contact')
        return self.render_to_response({'form': form})

class FAQView(ListView):
    model = FAQ
    template_name = 'core/faq.html'
    context_object_name = 'faqs'
    
    def get_queryset(self):
        return FAQ.objects.filter(is_published=True).order_by('category', 'sort_order')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Group FAQs by category
        faqs_by_category = {}
        for faq in context['faqs']:
            category = faq.get_category_display()
            if category not in faqs_by_category:
                faqs_by_category[category] = []
            faqs_by_category[category].append(faq)
        context['faqs_by_category'] = faqs_by_category
        return context

class SupportTicketCreateView(LoginRequiredMixin, CreateView):
    model = SupportTicket
    form_class = SupportTicketForm
    template_name = 'core/support_ticket_form.html'
    success_url = reverse_lazy('core:support_tickets')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Support ticket created successfully!')
        return super().form_valid(form)

class SupportTicketListView(LoginRequiredMixin, ListView):
    model = SupportTicket
    template_name = 'core/support_ticket_list.html'
    context_object_name = 'tickets'
    
    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user).order_by('-created_at')

class SupportTicketDetailView(LoginRequiredMixin, DetailView):
    model = SupportTicket
    template_name = 'core/support_ticket_detail.html'
    context_object_name = 'ticket'
    
    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages'] = SupportMessage.objects.filter(ticket=self.object).order_by('created_at')
        return context
    
    def post(self, request, *args, **kwargs):
        ticket = self.get_object()
        message = request.POST.get('message')
        
        if message:
            SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=message
            )
            
            # Update ticket status
            if ticket.status != 'open':
                ticket.status = 'open'
                ticket.save()
            
            messages.success(request, 'Message sent successfully!')
        
        return redirect('core:support_ticket_detail', pk=ticket.pk)

class TermsView(TemplateView):
    template_name = 'core/terms.html'

class PrivacyView(TemplateView):
    template_name = 'core/privacy.html'

# ===== NEWSLETTER VIEW =====

def newsletter_signup(request):
    """
    Handle newsletter signup form submissions.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if email:
            # Save to database
            subscriber, created = NewsletterSubscriber.objects.get_or_create(
                email=email,
                defaults={'is_active': True}
            )
            
            if not created and not subscriber.is_active:
                subscriber.is_active = True
                subscriber.unsubscribed_at = None
                subscriber.save()
                messages.success(request, 'Welcome back! You have been re-subscribed to our newsletter.')
            elif created:
                messages.success(request, 'Thank you for subscribing to our newsletter!')
            else:
                messages.info(request, 'You are already subscribed to our newsletter.')
        else:
            messages.error(request, 'Please provide a valid email address.')
    
    return redirect(request.META.get('HTTP_REFERER', 'core:home'))

# ===== ERROR HANDLERS =====

def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, '404.html', status=404)

def handler500(request):
    """Custom 500 error handler"""
    return render(request, '500.html', status=500)

def handler403(request, exception):
    """Custom 403 error handler"""
    return render(request, '403.html', status=403)

def handler400(request, exception):
    """Custom 400 error handler"""
    return render(request, '400.html', status=400)