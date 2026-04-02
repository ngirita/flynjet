from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import UserProfile, UserSecuritySettings

User = get_user_model()

class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_create_user(self):
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertTrue(self.user.check_password('testpass123'))
        self.assertEqual(self.user.get_full_name(), 'Test User')
    
    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='admin123'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
    
    def test_user_profile_created(self):
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, UserProfile)
    
    def test_security_settings_created(self):
        self.assertTrue(hasattr(self.user, 'security_settings'))
        self.assertIsInstance(self.user.security_settings, UserSecuritySettings)

class AuthenticationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_login_view(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after login
    
    def test_login_invalid_password(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'test@example.com',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)  # Stay on login page
        self.assertContains(response, 'Invalid email or password')
    
    def test_register_view(self):
        response = self.client.post(reverse('accounts:register'), {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'phone_number': '+1234567890',
            'password1': 'TestPass123!@#',
            'password2': 'TestPass123!@#'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after registration
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
    
    def test_logout_view(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)  # Redirect after logout