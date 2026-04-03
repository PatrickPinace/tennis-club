from datetime import date, datetime
from django import forms
from .models import Reservation, TennisFacility, Court

class CourtChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # Zwraca tylko numer kortu i informację, czy jest kryty
        indoor_info = " - kryty" if obj.is_indoor else ""
        return f"Kort nr {obj.court_number}{indoor_info}"

class ReservationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        facility = kwargs.pop('facility', None)
        super().__init__(*args, **kwargs)
        if facility:
            self.fields['court'].queryset = Court.objects.filter(facility=facility)
        self.fields['court'].empty_label = "Wybierz Kort"

    court = CourtChoiceField(
        queryset=Court.objects.none(), # Pusty queryset, zostanie nadpisany w __init__
        label="Kort",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    reservation_date = forms.DateField( # [1]
        label='Data rezerwacji',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=date.today
    )
    start_time = forms.TimeField(
        label='Godzina rozpoczęcia',
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        initial='00:00'
    )
    end_time = forms.TimeField(
        label='Godzina zakończenia',
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        initial='00:00'
    )

    class Meta:
        model = Reservation
        fields = ['court']

    def clean_court(self):
        court = self.cleaned_data.get('court')
        if not court:
            raise forms.ValidationError("Musisz wybrać kort.")
        return court

    def clean(self):
        cleaned_data = super().clean()
        court = cleaned_data.get("court")
        reservation_date = cleaned_data.get("reservation_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if court and reservation_date and start_time and end_time:
            start_datetime = datetime.combine(reservation_date, start_time)
            end_datetime = datetime.combine(reservation_date, end_time)

            if start_datetime >= end_datetime:
                raise forms.ValidationError("Godzina zakończenia musi być późniejsza niż godzina rozpoczęcia.")

            # Sprawdź, czy istnieją potwierdzone rezerwacje w tym samym czasie
            conflicting_reservations = Reservation.objects.filter(
                court=court,
                start_time__lt=end_datetime,
                end_time__gt=start_datetime
            ).exclude(status__in=['REJECTED', 'CHANGED'])

            if self.instance and self.instance.pk:
                conflicting_reservations = conflicting_reservations.exclude(pk=self.instance.pk)

            if conflicting_reservations.exists():
                raise forms.ValidationError("Wybrany kort jest już zajęty w tym terminie. Proszę wybrać inny termin lub kort.")

        return cleaned_data

class TennisFacilityForm(forms.ModelForm):
    class Meta:
        model = TennisFacility
        fields = ['name', 'address', 'description', 'contact_phone', 'surface', 'image', 'reservation']
        widgets = { # [1]
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'surface': forms.Select(attrs={'class': 'form-select'}), # [2]
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'reservation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CourtForm(forms.ModelForm):
    class Meta:
        model = Court
        fields = ['court_number', 'surface', 'is_indoor']
        widgets = { # [1]
            'court_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'surface': forms.Select(attrs={'class': 'form-select'}),
            'is_indoor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }