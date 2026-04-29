from django import forms
from .models import Match
from datetime import date
from django.contrib.auth.models import User
from apps.utils import tennis
from apps.friends.models import Friend
from django.db.models import Q, Count, Case, When, IntegerField
from django.db.models import Value
from apps.matches.models import Match

import logging
logger = logging.getLogger(__name__)

class MatchCreateForm(forms.ModelForm): 

    # Jawne zdefiniowanie pól, aby ustawić 'required=False'
    p1_set1 = forms.IntegerField(required=False, widget=forms.NumberInput())
    p1_set2 = forms.IntegerField(required=False, widget=forms.NumberInput())
    p1_set3 = forms.IntegerField(required=False, widget=forms.NumberInput())
    p2_set1 = forms.IntegerField(required=False, widget=forms.NumberInput())
    p2_set2 = forms.IntegerField(required=False, widget=forms.NumberInput())
    p2_set3 = forms.IntegerField(required=False, widget=forms.NumberInput())

    class Meta:
        model = Match
        fields = [
            'p1', 'p2', 'p3', 'p4',
            'p1_set1', 'p1_set2', 'p1_set3',
            'p2_set1', 'p2_set2', 'p2_set3', 'match_double', 'match_date'
        ]
        widgets = {
            'match_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-date text-center'}),
            'p1': forms.Select(attrs={'class': 'form-select-player player-list form-select font-2'}),
            'match_double': forms.CheckboxInput(attrs={'form':"form_add_match", 'class': 'form-check-input'}),
            'p2': forms.Select(attrs={'class': 'form-select-player player-list form-select font-2'}),
            'p3': forms.Select(attrs={'class': 'form-select-player player-list form-select font-2 d-none'}),
            'p4': forms.Select(attrs={'class': 'form-select-player player-list form-select font-2 d-none'}),
        }

        labels = {
            'match_double': 'Debel',
        }
    
    def __init__(self, *args,  user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Ustawienie auto_id na %s w celu usunięcia prefiksu id_
        self.auto_id = "%s"

        is_edit = self.instance and self.instance.pk

        if is_edit:
            # W trybie edycji, wszystkie pola graczy powinny być listami wyboru
            # zawierającymi wszystkich użytkowników, aby umożliwić zmianę.
            all_users_qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
            for field_name in ['p1', 'p2', 'p3', 'p4']:
                self.fields[field_name] = forms.ModelChoiceField(
                    queryset=all_users_qs,
                    widget=forms.Select(attrs={'class': 'form-select-player player-list form-select font-2'}),
                    required=False # p3 i p4 nie są wymagane
                )
            # W trybie edycji, pole match_double powinno być widoczne, ale zablokowane.
            # Wartość zostanie przesłana przez widok.
            self.fields['match_double'].widget.attrs['disabled'] = True

            # Zablokuj pole gracza, który jest zalogowanym użytkownikiem
            if user:
                player_fields = {'p1': self.instance.p1, 'p2': self.instance.p2, 'p3': self.instance.p3, 'p4': self.instance.p4}
                for field_name, player_obj in player_fields.items():
                    if player_obj == user:
                        self.fields[field_name].widget.attrs['disabled'] = True
                        # Zapisujemy, które pole zostało zablokowane, aby użyć tego w widoku
                        self.disabled_player_field = field_name
                        break

        elif user:
            # W trybie dodawania, pole p1 powinno zawierać tylko zalogowanego użytkownika.
            self.fields['p1'].queryset = User.objects.filter(pk=user.pk)

            # Pozostałe pola graczy powinny wykluczać zalogowanego użytkownika.
            other_users_qs = User.objects.filter(is_active=True).exclude(pk=user.pk).order_by('first_name', 'last_name')
            for field_name in ['p2', 'p3', 'p4']:
                self.fields[field_name].queryset = other_users_qs

        # Ustaw domyślną datę na dzisiaj tylko podczas tworzenia nowego meczu.
        if not self.instance.pk:
            self.initial['match_date'] = date.today().isoformat()

        # Overwrite the label_from_instance method for all player fields
        empty_label = "Wybierz"
        for field_name in ['p1', 'p2', 'p3', 'p4']:
            self.fields[field_name].empty_label = empty_label
            self.fields[field_name].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"
            

    def clean(self):
        cleaned = super().clean()
        
        # Check for duplicate players based on match type
        players = [
            cleaned.get('p1'), cleaned.get('p2'),
            cleaned.get('p3'), cleaned.get('p4')
        ]
        
        if cleaned.get('match_double'):
            # In a doubles match, all four players must be different.
            if len(set(p for p in players if p)) != 4:
                raise forms.ValidationError("Wszyscy gracze muszą być różni w meczu deblowym.")
        else:
            # In a singles match, p1 and p2 must be different.
            if players[0] and players[1] and players[0] == players[1]:
                raise forms.ValidationError("Gracze p1 i p2 muszą być różni w meczu singlowym.")
        
        return cleaned