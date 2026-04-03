from django import forms
from .models import Feedback

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['subject', 'message', 'email', 'url']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Np. Błąd w wyświetlaniu wyników'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Opisz dokładnie problem...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'jan.kowalski@example.com'}),
            'url': forms.HiddenInput(),
        }
        labels = {
            'subject': 'Temat zgłoszenia',
            'message': 'Treść wiadomości',
            'email': 'Adres e-mail (opcjonalnie)',
        }