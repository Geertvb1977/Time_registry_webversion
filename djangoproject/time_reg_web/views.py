"""Views voor multi-tenant ondersteuning in de tijdregistratie webapplicatie."""

from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
import openpyxl

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


# 2. Klanten Beheer (Aanmaken) - Aangepast om handmatig company te koppelen
class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    fields = ['customer_name', 'customer_email']
    template_name = 'dashboard/customer_form.html'
    success_url = reverse_lazy('eventaflow:dashboard')

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Koppel de klant aan het bedrijf van de huidige gebruiker
                form.instance.company = self.request.user.profile.company
                return super().form_valid(form)
        except Exception as e:
            form.add_error(None, f"Fout bij aanmaken klant: {e}")
            return self.form_invalid(form)


# 3. Projecten Beheer (Aanmaken) - Aangepast om handmatig company te koppelen
class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    fields = ['customer', 'project_name', 'project_description', 'start_date', 'end_date', 'is_active']
    template_name = 'dashboard/project_form.html'
    success_url = reverse_lazy('eventaflow:dashboard')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.is_authenticated:
            # Zorg dat je alleen klanten van je eigen bedrijf ziet
            form.fields['customer'].queryset = Customer.objects.filter(
                company=self.request.user.profile.company
            )
        return form

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Koppel het project aan het bedrijf van de huidige gebruiker
                form.instance.company = self.request.user.profile.company
                return super().form_valid(form)
        except Exception as e:
            form.add_error(None, f"Fout bij aanmaken project: {e}")
            return self.form_invalid(form)


# 4. Export View (Directe Download naar Excel met 5-minuten afronding en totaaltelling)
class ExportView(TenantObjectMixin, View):
    template_name = 'dashboard/export.html'

    def get(self, request):
        company = request.user.profile.company
        customers = Customer.objects.filter(company=company)
        projects = Project.objects.filter(company=company)
        
        return render(request, self.template_name, {
            'customers': customers,
            'projects': projects
        })

    def post(self, request):
        company = request.user.profile.company
        
        # Filters ophalen
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        customer_id = request.POST.get('customer')
        project_id = request.POST.get('project')

        # Queryset filteren
        entries = TimeRegistry.objects.filter(company=company).order_by('start_time')
        if start_date:
            entries = entries.filter(start_time__date__gte=start_date)
        if end_date:
            entries = entries.filter(start_time__date__lte=end_date)
        if customer_id:
            entries = entries.filter(project__customer_id=customer_id)
        if project_id:
            entries = entries.filter(project_id=project_id)

        # Excel genereren
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Uren Export"

        headers = ['Datum', 'Klant', 'Project', 'Gebruiker', 'Start', 'Eind', 'Duur (u)', 'Omschrijving']
        ws.append(headers)

        total_duration = 0  # Variabele voor de totaaltelling

        for entry in entries:
            duration = 0
            if entry.end_time:
                # Bereken verschil in seconden
                total_seconds = (entry.end_time - entry.start_time).total_seconds()
                
                # Afronden op 5 minuten (300 seconden)
                rounded_seconds = round(total_seconds / 300) * 300
                
                # Omzetten naar uren voor de kolom
                duration = round(rounded_seconds / 3600, 2)
                total_duration += duration  # Voeg toe aan totaal

            ws.append([
                entry.start_time.strftime('%d-%m-%Y') if entry.start_time else "",
                entry.project.customer.customer_name,
                entry.project.project_name,
                entry.user.username,
                entry.start_time.strftime('%H:%M') if entry.start_time else "",
                entry.end_time.strftime('%H:%M') if entry.end_time else "Lopend",
                duration,
                entry.description
            ])

        # Voeg een lege regel toe voor de overzichtelijkheid
        ws.append([])
        
        # Voeg de totaalregel toe
        # We plaatsen 'TOTAAL' in de kolom van de medewerker/eindtijd en de som in de duur-kolom
        ws.append(['', '', '', '', '', 'TOTAAL:', round(total_duration, 2), ''])

        # Response voor download
        filename = f"urenexport_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        
        return response


# 5. NIEUW: Aparte View voor Gebruiker Registratie
class RegisterUserView(View):
    """Maakt alleen een User en UserProfile aan, logt in en stuurt door."""
    template_name = 'registration/login.html' 

    def post(self, request):
        # Haal data uit de rechterkolom van login.html
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Basis validatie
        if not all([username, email, password, password_confirm]):
            return render(request, self.template_name, {'reg_error': 'Vul alle velden in.'})
            
        if password != password_confirm:
            return render(request, self.template_name, {'reg_error': 'Wachtwoorden komen niet overeen.'})

        if User.objects.filter(username=username).exists():
            return render(request, self.template_name, {'reg_error': 'Deze gebruikersnaam is al bezet.'})

        try:
            with transaction.atomic():
                # 1. Maak User aan
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                # 2. Maak UserProfile aan (zonder company)
                UserProfile.objects.get_or_create(user=user)
                
                # 3. Log in
                login(request, user)
                
            # 4. Stuur door naar de bedrijfsselectie (die zal redirecten naar create_company)
            return redirect('eventaflow:select_company')
        except Exception as e:
            return render(request, self.template_name, {'reg_error': f"Technisch probleem: {e}"})


class CompanySelectionView(LoginRequiredMixin, ListView):
    model = Company
    template_name = 'companies/select_company.html'
    context_object_name = 'companies'

    def get_queryset(self):
        # We halen nu alleen de bedrijven op waar de user LID van is
        return self.request.user.companies.all()


class CompanySelectionView(LoginRequiredMixin, ListView):
    model = Company
    template_name = 'companies/select_company.html'
    context_object_name = 'companies'

    def get_queryset(self):
        return self.request.user.companies.all()


@login_required
def switch_company(request, company_id):
    # Check of het bedrijf bestaat EN of de user lid is (members)
    # Dit is belangrijk voor de beveiliging!
    company = get_object_or_404(Company, id=company_id, members=request.user)
    
    # Zet dit bedrijf als actief in het profiel
    # Zorg dat je signalen of een save() methode hebt die het profiel aanmaakt als het niet bestaat
    if not hasattr(request.user, 'profile'):
        UserProfile.objects.create(user=request.user)
        
    request.user.profile.company = company
    request.user.profile.save()
    
    return redirect('eventaflow:dashboard')


class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    fields = ['name']
    template_name = 'companies/create_company.html'
    success_url = reverse_lazy('eventaflow:dashboard')
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                # We halen de instance op van het formulier zonder deze direct naar de DB te schrijven
                # Dit voorkomt dat we een ongeldig formulier proberen te saven
                self.object = form.save() 
                
                user = self.request.user
                
                # Koppel de gebruiker aan het zojuist aangemaakte bedrijf
                self.object.members.add(user)
                
                # Update of maak het profiel aan
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile.company = self.object
                profile.is_company_admin = True
                profile.save()
                
                # Omdat we een CreateView gebruiken en we self.object hebben gezet, 
                # kunnen we de standaard redirect van Django gebruiken
                return redirect(self.get_success_url())
                
        except Exception as e:
            form.add_error(None, f"Fout bij aanmaken bedrijf: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        # Voeg extra logging toe voor jezelf in de console als het formulier faalt
        print(f"Form errors: {form.errors}")
        return super().form_invalid(form)


# 6. Uitloggen
class LoginView(RedirectView):

    url = reverse_lazy('login')

    def get(self, request, *args, **kwargs):
        logout(request)
        return super().get(request, *args, **kwargs)


# 1.1 View om de timer te starten
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
    return redirect('eventaflow:dashboard')


# 1.2 View om de timer te stoppen
def stop_timer(request, timer_id):
    # Alleen stoppen via POST voor de veiligheid (tegen 405 errors)
    if request.method == 'POST':
        timer = get_object_or_404(TimeRegistry, id=timer_id, user=request.user)
        timer.end_time = timezone.now()
        timer.description = request.POST.get('description')
        timer.save()
    return redirect('eventaflow:dashboard')
