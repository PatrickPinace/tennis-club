from django import forms
from django.core.exceptions import ValidationError


class MessageForm(forms.Form):
    """
    Formularz do wysyłania wiadomości, obsługujący zarówno treść tekstową,
    jak i przesyłanie wielu obrazów jednocześnie.
    """
    content = forms.CharField(
        label="Treść wiadomości",
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Napisz wiadomość...',
            'class': 'form-control'
        })
    )
    images = forms.FileField(
        label="Dodaj zdjęcia",
        required=False,
        widget=forms.FileInput(attrs={
            'accept': 'image/*'  # Ogranicz do plików graficznych
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['images'].widget.attrs['multiple'] = True

    def clean(self):
        """
        Niestandardowa walidacja sprawdzająca, czy formularz nie jest pusty.
        Wiadomość musi zawierać treść tekstową lub co najmniej jeden obraz.
        """
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        images = self.files.getlist('images')  # Pobieramy listę plików

        if not content and not images:
            raise ValidationError(
                "Nie można wysłać pustej wiadomości. Dodaj treść lub wybierz obrazek.",
                code='empty_form'
            )

        return cleaned_data

    def clean_images(self):
        """
        Walidacja dla pola 'images', sprawdzająca typy plików.
        """
        images = self.files.getlist('images')
        for image in images:
            if image.content_type.split('/')[0] != 'image':
                raise ValidationError("Dozwolone są tylko pliki graficzne.", code='invalid_file_type')
        return images