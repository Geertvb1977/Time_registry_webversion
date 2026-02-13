"""Formulieren voor multi-tenant registratie in Django."""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from django.db import transaction
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.forms import PasswordResetForm
from .models import Company, UserProfile


# 1. Het Formulier
# 1. Het Formulier met wachtwoordherhaling
class RegistrationForm(forms.Form):
    company_name = forms.CharField(
        max_length=100, 
        label="Bedrijfsnaam",
        widget=forms.TextInput(attrs={'placeholder': 'Bijv. Mijn Bedrijf BV'})
    )
    username = forms.CharField(max_length=150, label="Gebruikersnaam")
    email = forms.EmailField(label="E-mailadres")
    password = forms.CharField(
        widget=forms.PasswordInput(),
        label="Wachtwoord"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(),
        label="Bevestig Wachtwoord"
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("De wachtwoorden komen niet overeen.")
        return cleaned_data
   
class TailwindPasswordResetForm(PasswordResetForm):
    """
    We gebruiken het standaard Django formulier maar voegen 
    Tailwind klassen toe aan het e-mailveld.
    """
    email = forms.EmailField(
        label="E-mailadres",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'block w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 shadow-sm',
            'placeholder': 'uw@email.be'
        })
    )