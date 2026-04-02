from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import DocumentTemplate, GeneratedDocument, DocumentSigning
from .generators import DocumentGenerator
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft, AircraftManufacturer

User = get_user_model()

class DocumentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create template
        self.template = DocumentTemplate.objects.create(
            name='Test Invoice',
            document_type='invoice',
            version='1.0'
        )
    
    def test_create_document(self):
        document = GeneratedDocument.objects.create(
            user=self.user,
            template=self.template,
            document_type='invoice',
            title='Test Document'
        )
        
        self.assertEqual(document.document_number[:3], 'INV')
        self.assertEqual(document.status, 'generated')
        self.assertIsNotNone(document.access_token)
    
    def test_document_signing(self):
        document = GeneratedDocument.objects.create(
            user=self.user,
            template=self.template,
            document_type='contract',
            title='Test Contract'
        )
        
        signing = DocumentSigning.objects.create(
            document=document,
            signer=self.user,
            signer_email=self.user.email,
            signer_name='Test User',
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        
        self.assertEqual(signing.status, 'pending')
        self.assertIsNotNone(signing.verification_code)

class DocumentGeneratorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        manufacturer = AircraftManufacturer.objects.create(
            name='Boeing',
            country='USA'
        )
        
        self.aircraft = Aircraft.objects.create(
            registration_number='N12345',
            manufacturer=manufacturer,
            model='737-800',
            passenger_capacity=180,
            year_of_manufacture=2020,
            hourly_rate_usd=5000
        )
        
        self.booking = Booking.objects.create(
            user=self.user,
            aircraft=self.aircraft,
            departure_airport='JFK',
            arrival_airport='LAX',
            departure_datetime=timezone.now() + timezone.timedelta(days=1),
            arrival_datetime=timezone.now() + timezone.timedelta(days=1, hours=5),
            passenger_count=2,
            total_amount_usd=25000
        )
        
        self.template = DocumentTemplate.objects.create(
            name='Test Template',
            document_type='invoice',
            version='1.0'
        )
        
        self.document = GeneratedDocument.objects.create(
            user=self.user,
            booking=self.booking,
            template=self.template,
            document_type='invoice',
            title='Test Invoice',
            content_data={
                'booking_reference': self.booking.booking_reference,
                'customer_name': self.user.get_full_name(),
                'total': float(self.booking.total_amount_usd)
            }
        )
    
    def test_generate_invoice_pdf(self):
        generator = DocumentGenerator(self.document)
        pdf_file = generator.generate_invoice_pdf()
        
        self.assertIsNotNone(pdf_file)
        self.assertTrue(pdf_file.size > 0)

class DocumentViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_document_list_view(self):
        response = self.client.get(reverse('documents:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/list.html')