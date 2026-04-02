from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import FAQ, Testimonial, SupportTicket

User = get_user_model()

class CoreModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_faq_creation(self):
        faq = FAQ.objects.create(
            question='What is FlynJet?',
            answer='FlynJet is a private jet charter platform.',
            category='general'
        )
        self.assertEqual(str(faq), 'What is FlynJet?')
    
    def test_testimonial_creation(self):
        testimonial = Testimonial.objects.create(
            customer_name='John Doe',
            content='Great service!',
            rating=5
        )
        self.assertEqual(str(testimonial), 'Testimonial by John Doe')
    
    def test_support_ticket_creation(self):
        ticket = SupportTicket.objects.create(
            user=self.user,
            subject='Test Ticket',
            description='This is a test',
            category='booking'
        )
        self.assertEqual(ticket.ticket_number[:3], 'TKT')
        self.assertEqual(ticket.status, 'new')

class CoreViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_home_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
    
    def test_about_view(self):
        response = self.client.get(reverse('core:about'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/about.html')
    
    def test_services_view(self):
        response = self.client.get(reverse('core:services'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/services.html')
    
    def test_contact_view(self):
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/contact.html')
    
    def test_faq_view(self):
        response = self.client.get(reverse('core:faq'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/faq.html')