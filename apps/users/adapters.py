from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class CustomAccountAdapter(DefaultAccountAdapter):

    def is_open_for_signup(self, request):
        # Disable registration via the allauth registration form
        return False