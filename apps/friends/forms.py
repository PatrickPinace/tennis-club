from django import forms
from .models import Friend
from django.contrib.auth.models import User


class FriendAddForm(forms.Form):
    friend_id = forms.ModelChoiceField(queryset=User.objects.none(), label="Użytkownik", empty_label="Wybierz")

    def __init__(self, *args, **kwargs):
        user_queryset = kwargs.pop("user_queryset", User.objects.none())
        super().__init__(*args, **kwargs)
        self.fields["friend_id"].queryset = user_queryset


class FriendRemoveForm(forms.Form):
    friend_id = forms.IntegerField()
