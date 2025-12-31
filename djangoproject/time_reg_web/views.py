"""Views voor multi-tenant ondersteuning in de tijdregistratie webapplicatie."""

from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin

from django.contrib.auth import logout
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView

from .models import Company, UserProfile, Customer, Project, TimeRegistry
from .mixins import TenantObjectMixin
from .forms import RegistrationForm


# 1. Het Dashboard (Hoofdpagina)
class DashboardView(TenantObjectMixin, ListView):
    model = Project
    template_name = 'dashboard/index.html'
    context_object_name = 'projects'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Filter klanten op het bedrijf van de ingelogde gebruiker
        if self.request.user.is_authenticated:
            context['customers'] = Customer.objects.filter(
                company=self.request.user.profile.company
            )
        return context


# 2. Klanten Beheer (Aanmaken)
class CustomerCreateView(TenantObjectMixin, CreateView):
    model = Customer
    # Gebaseerd op jouw models.py: customer_name, customer_id, customer_email
    fields = ['customer_name', 'customer_email']
    template_name = 'dashboard/customer_form.html'
    success_url = '/'


# 3. Projecten Beheer (Aanmaken)
class ProjectCreateView(TenantObjectMixin, CreateView):
    model = Project
    # Gebaseerd op jouw models.py: customer, project_id, project_name, project_description, start_date, end_date, is_active
    fields = ['customer', 'project_id', 'project_name', 'project_description', 'start_date', 'end_date', 'is_active']
    template_name = 'dashboard/project_form.html'
    success_url = '/'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter de klanten-dropdown zodat je alleen eigen klanten ziet
        if self.request.user.is_authenticated:
            form.fields['customer'].queryset = Customer.objects.filter(
                company=self.request.user.profile.company
            )
        return form


# 4. Registratie van een nieuw bedrijf (Tenant)
class RegisterCompanyView(View):
    template_name = 'registration/register_company.html'

    def get(self, request):
        form = RegistrationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                company = Company.objects.create(
                    name=form.cleaned_data['company_name']
                )
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password']
                )
                profile = user.profile
                profile.company = company
                profile.is_company_admin = True
                profile.save()

            return redirect('login')
        return render(request, self.template_name, {'form': form})


# 5. Uitloggen

class LogoutView(RedirectView):

    url = reverse_lazy('login')

    def get(self, request, *args, **kwargs):
        logout(request)
        return super().get(request, *args, **kwargs)
