from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import IntegrityError
import logging

from .models import Profile
from .forms import ProfileUpdateForm, UserUpdateForm, PasswordChangeForm, UserRegisterForm

logger = logging.getLogger(__name__)
from notifications.views import add_notification


@login_required
def change_password(request):
    """
    Handles user password changes.
    """
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            try:
                user = request.user
                new_password = form.cleaned_data['new_password1']
                user.set_password(new_password)
                user.save()
                logger.info(f"User {user.username} successfully changed their password.")
                
                # Automatycznie zaloguj użytkownika ponownie po zmianie hasła
                update_session_auth_hash(request, user) # Ważne, aby sesja nie wygasła
                
                messages.success(request, "Hasło zostało pomyślnie zmienione.")
                return redirect("users_edit")
            except Exception as e:
                messages.error(request, "Wystąpił błąd podczas zmiany hasła.")
                logger.error(f"Error changing password for user {request.user}: {e}")
    else:
        form = PasswordChangeForm(user=request.user)
    
    context = {'form': form}
    return render(request, "users/change_password.html", context)


@login_required
def users_edit(request):
    """
    Handles user profile edits.
    """
    # Upewnij się, że profil użytkownika istnieje. Jeśli nie, utwórz go.
    profile, created = Profile.objects.get_or_create(user=request.user)
    if created:
        logger.info(f"Created a default profile for user {request.user.username} upon accessing edit page.")

    if request.method == "POST":
        # Create instances of the forms with the request data and files
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        try:
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, "Twój profil został pomyślnie zaktualizowany!")
                logger.info(f"User {request.user.username} updated their profile.")
                return redirect("users_edit")
            else:
                messages.error(request, "Please correct the errors below.")
                logger.warning(f"Validation error for user {request.user.username}: {user_form.errors} and {profile_form.errors}")
        except Exception as e:
            messages.error(request, "An error occurred while updating your profile.")
            logger.error(f"Error editing profile for {request.user}: {e}")
            return redirect("users_edit")
    else:
        # Create instances of the forms and pass them to the template
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }

    return render(request, "users/edit.html", context)


def users_login(request):
    """
    Handles user login.
    """
    if request.method == "POST":
        login_name = request.POST.get("login")
        password = request.POST.get("password")


        # Spróbuj znaleźć użytkownika po nazwie użytkownika lub e-mailu
        user_candidate = None
        try:
            user_candidate = User.objects.get(username=login_name)
        except User.DoesNotExist:
            try:
                user_candidate = User.objects.get(email=login_name)
            except User.DoesNotExist:
                messages.error(request, "Użytkownik o podanym loginie/e-mailu nie istnieje.")
                logger.warning(f"Failed login attempt for username: {login_name} (user not found)")

        if user_candidate:
            # Jeśli użytkownik został znaleziony, spróbuj go uwierzytelnić z podanym hasłem
            user_auth = authenticate(request, username=user_candidate.username, password=password, backend='django.contrib.auth.backends.ModelBackend')
            if user_auth is not None:
                # Uwierzytelnienie powiodło się
            # Check if user has a profile, and if not, create one with default values.
                try:
                    user_auth.profile
                except Profile.DoesNotExist:
                    Profile.objects.create(user=user_auth)
                    logger.info(f"Created a default profile for user {login_name}.")

                # Get user IP address
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0]
                else:
                    ip = request.META.get('REMOTE_ADDR')
                login(request, user_auth, backend='django.contrib.auth.backends.ModelBackend')
                logger.info(f"User {login_name} logged in from IP: {ip}.")
                return redirect("/")
            else:
                # Użytkownik istnieje, ale hasło jest nieprawidłowe
                messages.error(request, "Nieprawidłowe hasło.")
                logger.warning(f"Failed login attempt for username: {login_name} (incorrect password)")

        return render(request, "users/login.html", {'login_name_value': login_name})

    elif request.user.is_authenticated:
        # If a logged-in user tries to access the login page, redirect them to the dashboard.
        return redirect("/")
        
    return render(request, "users/login.html")

def users_logout(request):
    """
    Handles user logout.
    """
    logger.info(f"User {request.user.username} logged out.")
    logout(request)
    return redirect("login")

def users_register(request):
    """
    Handles new user registration.
    """
    form = UserRegisterForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            login_name = data['login']
            try:
                user = User.objects.create_user(
                    username=login_name,
                    password=data['password_1'],
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    email=data['email']
                )
                
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, "Rejestracja przebiegła pomyślnie! Jesteś teraz zalogowany.")
                logger.info(f"User {login_name} successfully registered and logged in.")
                return redirect("/")
                
            except IntegrityError as e:
                messages.error(request, "Błąd bazy danych podczas rejestracji.")
                logger.error(f"IntegrityError during user registration for {login_name}: {e}")
            except Exception as e:
                messages.error(request, "Wystąpił nieoczekiwany błąd podczas rejestracji.")
                logger.error(f"Error registering user {login_name}: {e}")
        else:
            # Formularz jest nieprawidłowy, błędy zostaną automatycznie przekazane do szablonu
            logger.warning(f"Registration form validation failed: {form.errors.as_json()}")

    context = {'form': form}
    return render(request, "users/register.html", context)
