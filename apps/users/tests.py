from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from apps.users.forms import CustomSocialSignupForm

class RegistrationConsentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        
        # Setup for allauth
        site = Site.objects.get_current()
        provider_id = 'google'
        # Create SocialApp if it doesn't exist to avoid integrity errors in repeated runs if DB is not flushed
        SocialApp.objects.get_or_create(provider=provider_id, name='Google', client_id='123', secret='456', key='')
        # Note: In tests, DB is usually flushed, so get_or_create is safe. 
        # But we need to make sure we link it to site if created? 
        app, created = SocialApp.objects.get_or_create(provider=provider_id, defaults={'name': 'Google', 'client_id': '123', 'secret': '456', 'key': ''})
        app.sites.add(site)

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


from unittest.mock import MagicMock

class SocialRegistrationConsentTests(TestCase):
    def test_social_form_requires_consent(self):
        form_data = {
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.extra_data = {}
        form = CustomSocialSignupForm(data=form_data, sociallogin=mock_sociallogin)
        self.assertFalse(form.is_valid())
        self.assertIn('data_processing_consent', form.errors)

    def test_social_form_valid_with_consent(self):
        form_data = {
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'data_processing_consent': 'on'
        }
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.extra_data = {'given_name': 'Jan', 'family_name': 'Kowalski'}
        form = CustomSocialSignupForm(data=form_data, sociallogin=mock_sociallogin)
        self.assertTrue(form.is_valid())
