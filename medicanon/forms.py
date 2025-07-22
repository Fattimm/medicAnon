# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Utilisateur

class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Choisissez un nom d\'utilisateur unique'
        }),
        help_text='Lettres, chiffres et @/./+/-/_ uniquement. 150 caractères maximum.'
    )
    
    first_name = forms.CharField(
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Votre prénom'
        })
    )
    
    last_name = forms.CharField(
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Votre nom'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'votre.email@exemple.com'
        })
    )
    
    # Champ rôle conditionnel
    role = forms.ChoiceField(
        choices=[
            ('Visiteur', 'Visiteur - Accès lecture seule'),
            ('Agent', 'Agent - Gestion des données'),
            ('Administrateur', 'Administrateur - Contrôle total'),
        ],
        required=False,  # Sera requis uniquement pour les admins
        widget=forms.Select(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
        })
    )

    class Meta:
        model = Utilisateur
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'role')

    def __init__(self, *args, **kwargs):
        # Récupérer l'utilisateur connecté pour déterminer s'il est admin
        self.user = kwargs.pop('user', None)
        self.is_admin_creating = kwargs.pop('is_admin_creating', False)
        
        super().__init__(*args, **kwargs)
        
        # Appliquer les classes CSS aux champs de mot de passe avec thème bleu
        for field_name in ['password1', 'password2']:
            self.fields[field_name].widget.attrs.update({
                'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            })
            
        # Personnaliser les placeholders des mots de passe
        self.fields['password1'].widget.attrs['placeholder'] = 'Entrez votre mot de passe'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmez votre mot de passe'
        
        # Configurer le champ rôle selon le contexte
        if self.is_admin_creating:
            # Admin peut choisir le rôle
            self.fields['role'].required = True
            self.fields['role'].initial = 'Visiteur'
        else:
            # Visiteur normal - cacher le champ rôle
            self.fields['role'].widget = forms.HiddenInput()
            self.fields['role'].initial = 'Visiteur'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Utilisateur.objects.filter(email=email).exists():
            raise forms.ValidationError("Cette adresse email est déjà utilisée.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Vérifier l'unicité
            if Utilisateur.objects.filter(username=username).exists():
                raise forms.ValidationError("Ce nom d'utilisateur est déjà pris. Veuillez en choisir un autre.")
            
            # Validation supplémentaire (optionnelle)
            if len(username) < 3:
                raise forms.ValidationError("Le nom d'utilisateur doit contenir au moins 3 caractères.")
                
        return username

    def clean_role(self):
        role = self.cleaned_data.get('role')
        
        # Si c'est un admin qui crée, le rôle est obligatoire
        if self.is_admin_creating and not role:
            raise forms.ValidationError("Veuillez sélectionner un rôle.")
        
        # Si ce n'est pas un admin, forcer le rôle Visiteur
        if not self.is_admin_creating:
            return 'Visiteur'
            
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        # Définir le rôle
        if self.is_admin_creating:
            user.role = self.cleaned_data['role']
        else:
            user.role = 'Visiteur'
            
        if commit:
            user.save()
        return user


# Alternative 2: Username basé sur UUID (toujours unique)
class UUIDUsernameCreationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-medic-500 focus:border-medic-500',
            'placeholder': 'Votre prénom'
        })
    )
    last_name = forms.CharField(
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-medic-500 focus:border-medic-500',
            'placeholder': 'Votre nom'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-medic-500 focus:border-medic-500',
            'placeholder': 'votre.email@exemple.com'
        })
    )

    class Meta:
        model = Utilisateur
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Supprimer le champ username du formulaire
        if 'username' in self.fields:
            del self.fields['username']
        
        # Appliquer les classes CSS aux champs de mot de passe
        for field_name in ['password1', 'password2']:
            self.fields[field_name].widget.attrs.update({
                'class': 'form-input w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-medic-500 focus:border-medic-500'
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Utilisateur.objects.filter(email=email).exists():
            raise forms.ValidationError("Cette adresse email est déjà utilisée.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        # Générer un username unique avec UUID
        user.username = f"user_{uuid.uuid4().hex[:8]}"
        
        user.role = 'Visiteur'
        if commit:
            user.save()
        return user