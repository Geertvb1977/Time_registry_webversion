"""Views voor multi-tenant ondersteuning in de tijdregistratie webapplicatie."""

from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.shortcuts import get_object_or_404

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
        context['active_timer'] = TimeRegistry.objects.filter(user=self.request.user, end_time__isnull=True).first()
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
    fields = ['customer', 'project_name', 'project_description', 'start_date', 'end_date', 'is_active']
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
class LoginView(RedirectView):

    url = reverse_lazy('login')

    def get(self, request, *args, **kwargs):
        logout(request)
        return super().get(request, *args, **kwargs)


# View om de timer te starten
def start_timer(request):
    if request.method == 'POST':
        # We gebruiken de database 'id' uit het <select> element
        project_pk = request.POST.get('project')
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk, company=request.user.profile.company)

            # Voorkom dubbele actieve timers
            active_timer = TimeRegistry.objects.filter(
                user=request.user,
                end_time__isnull=True
            ).exists()

            if not active_timer:
                TimeRegistry.objects.create(
                    user=request.user,
                    project=project,
                    company=request.user.profile.company,
                    description=request.POST.get('description'),
                    start_time=timezone.now()
                )
    return redirect('dashboard')


# View om de timer te stoppen
def stop_timer(request, timer_id):
    # Alleen stoppen via POST voor de veiligheid (tegen 405 errors)
    if request.method == 'POST':
        timer = get_object_or_404(TimeRegistry, id=timer_id, user=request.user)
        timer.end_time = timezone.now()
        timer.description = request.POST.get('description')
        # Automatische berekening van uren
        # diff = timer.end_time - timer.start_time
        # timer.duration = diff.total_seconds() / 3600

        timer.save()
    return redirect('dashboard')
