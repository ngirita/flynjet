from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import ConsentRecord, DataSubjectRequest, BreachNotification

User = get_user_model()

class ComplianceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_consent(self):
        consent = ConsentRecord.objects.create(
            user=self.user,
            consent_type='marketing',
            version='1.0',
            granted=True,
            ip_address='127.0.0.1'
        )
        
        self.assertEqual(consent.consent_type, 'marketing')
        self.assertTrue(consent.granted)
    
    def test_create_dsr(self):
        dsr = DataSubjectRequest.objects.create(
            user=self.user,
            requester_name='Test User',
            requester_email='test@example.com',
            request_type='access',
            description='Request my data'
        )
        
        self.assertEqual(dsr.request_number[:3], 'DSR')
        self.assertEqual(dsr.status, 'pending')
    
    def test_create_breach(self):
        breach = BreachNotification.objects.create(
            severity='high',
            description='Test breach',
            affected_data=['email', 'name'],
            affected_users_count=100
        )
        
        self.assertEqual(breach.breach_number[:2], 'BR')
        self.assertEqual(breach.status, 'detected')

class ComplianceViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_consent_view(self):
        response = self.client.get(reverse('compliance:consent'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'compliance/consent.html')
    
    def test_dsr_form_view(self):
        response = self.client.get(reverse('compliance:dsr'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'compliance/dsr_form.html')
    
    def test_cookie_consent_api(self):
        response = self.client.post('/compliance/cookie-consent/', 
                                   {'consent': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')