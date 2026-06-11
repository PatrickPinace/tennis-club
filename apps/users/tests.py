from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.sites.models import Site

class RegistrationConsentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        
        self.user_data = {
            'login': 'newuser',
            'first_name': 'Jan',
            'last_name': 'Kowalski',
            'email': 'jan@example.com',
            'password_1': 'StrongPass123!',
            'password_2': 'StrongPass123!',
        }

    def test_registration_without_consent_fails(self):
        data = self.user_data.copy()
        if 'data_processing_consent' in data:
            del data['data_processing_consent']
        response = self.client.post(self.register_url, data)
        # Form should be invalid
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('data_processing_consent', form.errors)
        self.assertEqual(User.objects.count(), 0)

    def test_registration_with_consent_succeeds(self):
        data = self.user_data.copy()
        data['data_processing_consent'] = 'on'
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 1)

