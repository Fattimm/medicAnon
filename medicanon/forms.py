from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Utilisateur

class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(choices=Utilisateur._meta.get_field('role').choices)

    class Meta:
        model = Utilisateur
        fields = ('username', 'email', 'role','first_name', 'last_name', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user