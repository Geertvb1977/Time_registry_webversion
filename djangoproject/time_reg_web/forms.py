"""Formulieren voor multi-tenant registratie in Django."""

from django import forms
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import render, redirect
from django.views import View
from .models import Company, UserProfile


# 1. Het Formulier
class RegistrationForm(forms.Form):
    # Bedrijfsgegevens
    company_name = forms.CharField(
        max_length=100,
        label="Bedrijfsnaam",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bijv. Mijn Bedrijf BV'})
    )

    # Gebruikersgegevens
    username = forms.CharField(
        max_length=150,
        label="Gebruikersnaam",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label="E-mailadres",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Wachtwoord"
    )
