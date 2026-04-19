"""Formulieren voor multi-tenant registratie in Django."""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from django.db import transaction
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.forms import PasswordResetForm
from .models import Company, Milstones, UserProfile, Todo, Divisies


# 1. Het Formulier
# 1. Het Formulier met wachtwoordherhaling
class RegistrationForm(forms.Form):
    company_name = forms.CharField(
        max_length=100,
        label="Bedrijfsnaam",
        widget=forms.TextInput(attrs={"placeholder": "Bijv. Mijn Bedrijf BV"}),
    )
    username = forms.CharField(max_length=150, label="Gebruikersnaam")
    email = forms.EmailField(label="E-mailadres")
    password = forms.CharField(widget=forms.PasswordInput(), label="Wachtwoord")
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(), label="Bevestig Wachtwoord"
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
        widget=forms.EmailInput(
            attrs={
                "class": "block w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 shadow-sm",
                "placeholder": "uw@email.be",
            }
        ),
    )


class TodoForm(forms.ModelForm):
    """Formulier voor aanmaken en bewerken van taken."""

    class Meta:
        model = Todo
        fields = [
            "customer_id",
            "project_id",
            "divisie",
            "user",
            "priority",
            "title",
            "due_date",
            "description",
            "is_completed",
            "milestone",
        ]
        widgets = {
            "customer_id": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
            "project_id": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
            "divisie": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
            "user": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
            "priority": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
            "title": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4",
                    "placeholder": "Bijv. Website Homepage Update",
                }
            ),
            "due_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4 resize-none",
                    "rows": 6,
                    "placeholder": "Detailleerde beschrijving van de taak...",
                }
            ),
            "is_completed": forms.CheckboxInput(
                attrs={
                    "class": "w-5 h-5 text-green-600 border-gray-300 rounded focus:ring-green-500"
                }
            ),
            "milestone": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
        }


class DivisieForm(forms.ModelForm):
    """Formulier voor aanmaken van divisies."""

    class Meta:
        model = Divisies
        fields = ["divisie_name"]
        widgets = {
            "divisie_name": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 py-3 px-4",
                    "placeholder": "Bijv. Ontwikkeling, Marketing, Verkoop",
                }
            )
        }


class MilestoneForm(forms.ModelForm):
    """Formulier voor aanmaken en bewerken van taken."""

    class Meta:
        model = Milstones
        fields = [
            "project",
            "divisie",
            "title",
            "due_date",
            "description",
            "is_completed",
        ]
        widgets = {
            "project": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
            "divisie": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4"
                }
            ),
            "title": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4",
                    "placeholder": "Bijv. Website Homepage Update",
                }
            ),
            "due_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 py-3 px-4 resize-none",
                    "rows": 6,
                    "placeholder": "Detailleerde beschrijving van de taak...",
                }
            ),
            "is_completed": forms.CheckboxInput(
                attrs={
                    "class": "w-5 h-5 text-green-600 border-gray-300 rounded focus:ring-green-500"
                }
            ),
        }
