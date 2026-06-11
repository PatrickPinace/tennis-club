from django.shortcuts import redirect
from django.contrib.auth import logout

def change_password(request):
    return redirect('/astro/profile')

def users_edit(request):
    return redirect('/astro/profile')

def users_login(request):
    return redirect('/astro/login')

def users_logout(request):
    logout(request)
    return redirect('/astro/login')

def users_register(request):
    return redirect('/astro/register')
