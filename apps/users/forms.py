from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

from .models import Profile

class ProfileUpdateForm(forms.ModelForm):
    """Formularz do aktualizacji profilu użytkownika."""
    
    garmin_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ''}, render_value=False)
    )

    class Meta:
        model = Profile
        fields = ['birth_date', 'city', 'start_date', 'image', 'garmin_login', 'garmin_sync_option']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'np. Warszawa'}),
            'image': forms.FileInput(attrs={'style': 'display: none;', 'id': 'id_image'}),
            'garmin_login': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ''}),
            'garmin_sync_option': forms.RadioSelect(attrs={'class': 'form-check-input'}),
        }
        # Używamy extra_kwargs, aby ustawić pola jako nieobowiązkowe
        extra_kwargs = {
            'birth_date': {'required': False},
            'start_date': {'required': False},
            'garmin_login': {'required': False},
            'garmin_sync_option': {'required': False},
        }
        error_messages = {
            'birth_date': {
                'invalid': 'Proszę podać poprawną datę w formacie RRRR-MM-DD.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pole jest zawsze zdefiniowane jako required=False w definicji pola,
        # więc dodatkowa logika w __init__ nie jest konieczna dla required,
        # ale zachowujemy spójność.

    def save(self, commit=True):
        # Najpierw stwórz instancję z pól ModelForm (bez garmin_password)
        instance = super().save(commit=False)
        
        # Pobierz hasło z formularza
        password = self.cleaned_data.get('garmin_password')

        # Logika aktualizacji hasła:
        # 1. Jeśli użytkownik wpisał hasło, zaktualizuj je.
        if password:
            instance.garmin_password = password
        # 2. Jeśli nie wpisał hasła (puste pole), NIE RÓB NIC z instance.garmin_password.
        #    Dzięki temu pozostanie stara wartość (jeśli była załadowana z bazy).

        if commit:
            instance.save()
        return instance


class UserUpdateForm(forms.ModelForm):
    """Formularz do aktualizacji danych użytkownika (imię, nazwisko, email)."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Twoje imię'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Twoje nazwisko'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'adres@email.com'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class PasswordChangeForm(forms.Form):
    """Formularz do zmiany hasła przez zalogowanego użytkownika."""
    current_password = forms.CharField(
        label="Obecne hasło",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    new_password1 = forms.CharField(
        label="Nowe hasło",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    new_password2 = forms.CharField(
        label="Powtórz nowe hasło",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise forms.ValidationError("Obecne hasło jest nieprawidłowe.")
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        if new_password1 and new_password2 and new_password1 != new_password2:
            self.add_error('new_password2', "Podane hasła nie są identyczne.")
        return cleaned_data


class UserRegisterForm(forms.Form):
    login = forms.CharField(label='Login', max_length=150, required=True)
    first_name = forms.CharField(label='Imię', max_length=150, required=True)
    last_name = forms.CharField(label='Nazwisko', max_length=150, required=True)
    email = forms.EmailField(label='E-mail', required=False)
    password_1 = forms.CharField(label='Hasło', widget=forms.PasswordInput, required=True)
    password_2 = forms.CharField(label='Powtórz hasło', widget=forms.PasswordInput, required=True)
    data_processing_consent = forms.BooleanField(
        label='Wyrażam zgodę na przetwarzanie moich danych osobowych w ramach funkcjonalności portalu.',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_login(self):
        login = self.cleaned_data.get('login')
        if User.objects.filter(username=login).exists():
            raise ValidationError("Użytkownik o tym loginie już istnieje.", code='username_exists')
        return login

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("Użytkownik o tym adresie e-mail już istnieje.", code='email_exists')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password_1 = cleaned_data.get("password_1")
        password_2 = cleaned_data.get("password_2")

        if password_1 and password_2 and password_1 != password_2:
            self.add_error('password_2', "Hasła muszą być takie same.")
        elif password_1:
            validate_password(password_1)
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'data_processing_consent':
                field.widget.attrs['class'] = 'form-control'

from allauth.utils import generate_unique_username
from allauth.socialaccount.forms import SignupForm as SocialSignupFormBase

class CustomSocialSignupForm(SocialSignupFormBase):
    """
    Niestandardowy formularz rejestracji przez media społecznościowe,
    wymuszający ustawienie hasła. Nazwa użytkownika jest generowana automatycznie.
    """
    password = forms.CharField(
        label="Hasło",
        widget=forms.PasswordInput(attrs={'placeholder': 'Wprowadź hasło', 'class': 'form-control'}),
        required=True
    )
    password2 = forms.CharField(
        label="Powtórz hasło",
        widget=forms.PasswordInput(attrs={'placeholder': 'Powtórz hasło', 'class': 'form-control'}),
        required=True
    )
    data_processing_consent = forms.BooleanField(
        label='Wyrażam zgodę na przetwarzanie moich danych osobowych w ramach funkcjonalności portalu.',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        self.sociallogin = kwargs.get('sociallogin')
        super().__init__(*args, **kwargs)
        # Ukryj pole email, ponieważ będzie wyświetlane w nagłówku, a nie jako pole do edycji.
        # Wartość jest już pobrana z konta społecznościowego.
        if 'email' in self.fields:
            self.fields['email'].widget = forms.HiddenInput()
        # Usuń pole username z formularza, ponieważ jest generowane automatycznie.
        if 'username' in self.fields:
            del self.fields['username']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")
        if password and password2 and password != password2:
            self.add_error('password2', "Podane hasła nie są identyczne.")
        return cleaned_data

    def save(self, request):
        # Wywołaj metodę save formularza bazowego, która utworzy użytkownika
        # i ustawi pola takie jak username i email.
        user = super().save(request)

        # Jeśli nazwa użytkownika nie została ustawiona, wygeneruj ją z adresu e-mail
        if not user.username and user.email:
            user.username = generate_unique_username([
                user.email.split('@')[0],
                'user'
            ])

        # Ustaw dodatkowe pola (imię, nazwisko) z danych konta społecznościowego
        if self.sociallogin:
            extra_data = self.sociallogin.account.extra_data
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')

        # Ustaw hasło
        user.set_password(self.cleaned_data['password'])
        user.save()
        return user
