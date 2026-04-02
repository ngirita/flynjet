# apps/documents/views.py - COMPLETE FIXED VERSION

import json
from io import BytesIO
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, TemplateView, View
from django.contrib import messages
from django.http import FileResponse, Http404
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from weasyprint import HTML
from .models import GeneratedDocument, DocumentTemplate, DocumentSigning
from .generators import DocumentGenerator
from apps.bookings.models import Booking, Invoice


class DocumentListView(LoginRequiredMixin, ListView):
    """List user documents"""
    model = GeneratedDocument
    template_name = 'documents/list.html'
    context_object_name = 'documents'
    paginate_by = 20
    
    def get_queryset(self):
        return GeneratedDocument.objects.filter(user=self.request.user).order_by('-created_at')


class GenerateDocumentView(LoginRequiredMixin, View):
    """Generate a new document"""
    
    def get(self, request, booking_id, doc_type):
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        
        # Map document type to template file
        template_map = {
            'invoice': 'invoices/standard.html',
            'corporate': 'invoices/corporate.html',
            'proforma': 'invoices/proforma.html',
            'ticket': 'tickets/e_ticket.html',           # <-- FIXED: Use e_ticket template
            'boarding_pass': 'tickets/boarding_pass.html',  # <-- ADD THIS
        }
        
        template_name = template_map.get(doc_type)
        if not template_name:
            messages.error(request, f"Invalid document type: {doc_type}")
            return redirect('bookings:detail', pk=booking_id)
        
        # Prepare safe data for the template - NO MODEL OBJECTS, ONLY PRIMITIVES
        safe_booking = {
            'booking_reference': str(booking.booking_reference),
            'departure_airport': str(booking.departure_airport),
            'arrival_airport': str(booking.arrival_airport),
            'departure_datetime': booking.departure_datetime,
            'arrival_datetime': booking.arrival_datetime,
            'passenger_count': int(booking.passenger_count),
            'aircraft': {
                'model': str(booking.aircraft.model),
                'manufacturer': str(booking.aircraft.manufacturer.name) if hasattr(booking.aircraft, 'manufacturer') else '',
                'registration': str(booking.aircraft.registration_number) if hasattr(booking.aircraft, 'registration_number') else '',
            },
            'total_amount_usd': float(booking.total_amount_usd),
            'base_price_usd': float(booking.base_price_usd),
            'fuel_surcharge_usd': float(booking.fuel_surcharge_usd),
            'handling_fee_usd': float(booking.handling_fee_usd),
            'catering_cost_usd': float(booking.catering_cost_usd),
            'cleaning_charge_usd': float(booking.cleaning_charge_usd),
            'insurance_premium': float(booking.insurance_premium),
            'tax_amount_usd': float(booking.tax_amount_usd),
            'discount_amount_usd': float(booking.discount_amount_usd),
            'amount_paid': float(booking.amount_paid),
            'amount_due': float(booking.amount_due),
            'status': booking.status,
            'payment_status': booking.payment_status,
            'flight_type': booking.flight_type,
            'created_at': booking.created_at,
        }
        
        # Prepare user data
        safe_user = {
            'first_name': str(booking.user.first_name),
            'last_name': str(booking.user.last_name),
            'email': str(booking.user.email),
            'phone_number': str(getattr(booking.user, 'phone_number', '')),
            'address_line1': str(getattr(booking.user, 'address_line1', '')),
            'address_line2': str(getattr(booking.user, 'address_line2', '')),
            'city': str(getattr(booking.user, 'city', '')),
            'state': str(getattr(booking.user, 'state', '')),
            'postal_code': str(getattr(booking.user, 'postal_code', '')),
            'country': str(getattr(booking.user, 'country', '')),
            'company_name': str(getattr(booking.user, 'company_name', '')),
            'company_registration_number': str(getattr(booking.user, 'company_registration_number', '')),
            'company_vat_number': str(getattr(booking.user, 'company_vat_number', '')),
        }
        
        # Calculate subtotal
        subtotal = float(booking.base_price_usd + booking.fuel_surcharge_usd + 
                         booking.handling_fee_usd + booking.catering_cost_usd + 
                         booking.cleaning_charge_usd + booking.insurance_cost_usd)
        
        # Create items list
        items = [
            {'description': 'Base Price', 'unit_price_usd': float(booking.base_price_usd), 'quantity': 1, 'line_total_usd': float(booking.base_price_usd)},
        ]
        
        if booking.fuel_surcharge_usd > 0:
            items.append({'description': 'Fuel Surcharge', 'unit_price_usd': float(booking.fuel_surcharge_usd), 'quantity': 1, 'line_total_usd': float(booking.fuel_surcharge_usd)})
        
        if booking.handling_fee_usd > 0:
            items.append({'description': 'Handling Fee', 'unit_price_usd': float(booking.handling_fee_usd), 'quantity': 1, 'line_total_usd': float(booking.handling_fee_usd)})
        
        if booking.catering_cost_usd > 0:
            items.append({'description': 'Catering Service', 'unit_price_usd': float(booking.catering_cost_usd), 'quantity': 1, 'line_total_usd': float(booking.catering_cost_usd)})
        
        if booking.cleaning_charge_usd > 0:
            items.append({'description': 'Cleaning Fee', 'unit_price_usd': float(booking.cleaning_charge_usd), 'quantity': 1, 'line_total_usd': float(booking.cleaning_charge_usd)})
        
        if booking.insurance_purchased and booking.insurance_premium > 0:
            items.append({'description': 'Travel Insurance', 'unit_price_usd': float(booking.insurance_premium), 'quantity': 1, 'line_total_usd': float(booking.insurance_premium)})
        
        # Prepare document data for template
        document_data = {
            'document_number': f"INV-{booking.booking_reference}-{timezone.now().strftime('%Y%m')}",
            'created_at': timezone.now(),
            'due_date': timezone.now() + timezone.timedelta(days=30),
            'expires_at': timezone.now() + timezone.timedelta(days=7) if doc_type == 'proforma' else None,
            'subtotal_usd': subtotal,
            'tax_rate': 10,
            'tax_amount_usd': float(booking.tax_amount_usd),
            'discount_amount_usd': float(booking.discount_amount_usd),
            'total_usd': float(booking.total_amount_usd),
            'items': items,
            'status': 'draft',
            'payment_method': '',
            'payment_transaction_id': '',
            'notes': '',
            'currency': 'USD',
        }
        
        # Prepare context for template - NO MODEL OBJECTS!
        context = {
            'booking': safe_booking,
            'user': safe_user,
            'document': document_data,
            'doc_type': doc_type,
        }
        
        # Add company details
        context['company'] = {
            'name': 'FlynJet Air and Logistics.',
            'address': 'Jomo Kenyatta International Airport. Airport North Road, Embakasi Nairobi, Kenya',
            'city': 'Nairobi',
            'state': 'Nairobi',
            'postal_code': '19087-00501',
            'country': 'Kenya',
            'phone': '+254785651832',
            'whatsapp': '+447393700477',
            'email': 'info@flynjet.com',
            'tax_id': '12-3456789',
        }
        
        try:
            # Render the template with safe data
            html_content = render_to_string(template_name, context)
            
            # Generate PDF
            pdf_file = BytesIO()
            HTML(string=html_content).write_pdf(pdf_file)
            pdf_file.seek(0)
            
            # Prepare serializable data for JSON storage
            serializable_data = {
                'booking_reference': booking.booking_reference,
                'customer_name': booking.user.get_full_name(),
                'customer_email': booking.user.email,
                'departure_airport': booking.departure_airport,
                'arrival_airport': booking.arrival_airport,
                'departure_datetime': booking.departure_datetime.isoformat(),
                'arrival_datetime': booking.arrival_datetime.isoformat(),
                'passenger_count': booking.passenger_count,
                'aircraft': str(booking.aircraft),
                'total_amount_usd': float(booking.total_amount_usd),
                'document_type': doc_type,
            }
            
            # Create document record
            document = GeneratedDocument.objects.create(
                user=request.user,
                booking=booking,
                document_type=doc_type,
                title=f"{doc_type.title()} - {booking.booking_reference}",
                content_data=serializable_data,
                is_signed=False
            )
            
            # Save PDF file
            filename = f"{doc_type}_{booking.booking_reference}.pdf"
            document.pdf_file.save(filename, ContentFile(pdf_file.getvalue()))
            
            messages.success(request, f"{doc_type.title()} generated successfully!")
            return redirect('documents:view', pk=document.id)
            
        except Exception as e:
            print(f"Error generating document: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error generating document: {str(e)}")
            return redirect('bookings:detail', pk=booking_id)


class DocumentViewerView(LoginRequiredMixin, DetailView):
    """View document"""
    model = GeneratedDocument
    template_name = 'documents/view.html'
    context_object_name = 'document'
    
    def get_queryset(self):
        return GeneratedDocument.objects.filter(user=self.request.user)
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        self.object.record_view(request)
        return response


def download_document(request, pk):
    """Download document PDF"""
    document = get_object_or_404(GeneratedDocument, pk=pk, user=request.user)
    document.record_download()
    
    if document.pdf_file:
        return FileResponse(
            document.pdf_file,
            as_attachment=True,
            filename=f"{document.document_number}.pdf"
        )
    raise Http404("File not found")


class SignDocumentView(LoginRequiredMixin, TemplateView):
    """Sign document electronically"""
    template_name = 'documents/sign.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = get_object_or_404(
            GeneratedDocument,
            pk=self.kwargs['pk'],
            user=self.request.user
        )
        
        # Get or create signing record
        signing, created = DocumentSigning.objects.get_or_create(
            document=document,
            signer=self.request.user,
            defaults={
                'signer_email': self.request.user.email,
                'signer_name': self.request.user.get_full_name(),
                'expires_at': timezone.now() + timezone.timedelta(days=7)
            }
        )
        
        context['document'] = document
        context['signing'] = signing
        return context
    
    def post(self, request, *args, **kwargs):
        document = get_object_or_404(
            GeneratedDocument,
            pk=self.kwargs['pk'],
            user=request.user
        )
        
        # Get signature data - it's 'signature_data' from the canvas, not 'signature'
        signature_data = request.POST.get('signature_data')
        
        if not signature_data:
            messages.error(request, "Please provide your signature before submitting.")
            return self.get(request, *args, **kwargs)
        
        # Get or create signing record
        signing, created = DocumentSigning.objects.get_or_create(
            document=document,
            signer=request.user,
            defaults={
                'signer_email': request.user.email,
                'signer_name': request.user.get_full_name(),
                'expires_at': timezone.now() + timezone.timedelta(days=7)
            }
        )
        
        # Save the signature
        signing.signature_data = signature_data
        signing.status = 'signed'
        signing.verified_at = timezone.now()
        signing.ip_address = self.get_client_ip(request)
        signing.user_agent = request.META.get('HTTP_USER_AGENT', '')
        signing.save()
        
        # Update document
        document.is_signed = True
        document.signed_at = timezone.now()
        document.save()
        
        messages.success(request, "Document signed successfully!")
        return redirect('documents:view', pk=document.id)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

class VerifyDocumentView(TemplateView):
    """Verify document authenticity"""
    template_name = 'documents/verify.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.kwargs.get('token')
        
        try:
            document = GeneratedDocument.objects.get(access_token=token)
            context['document'] = document
            context['is_valid'] = document.is_valid()
        except GeneratedDocument.DoesNotExist:
            context['error'] = "Document not found"
        
        return context