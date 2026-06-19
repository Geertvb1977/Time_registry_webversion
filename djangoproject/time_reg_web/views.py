"""Views voor multi-tenant ondersteuning in de tijdregistratie webapplicatie."""

import logging
import secrets
import urllib.parse

import openpyxl
import requests
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Sum, Value, When
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.base import RedirectView

from .forms import MilestoneForm, TodoForm
from .google_drive_service import GoogleDriveService
from .mixins import TenantObjectMixin
from .models import (
    APIToken,
    APITokenUsage,
    Company,
    Customer,
    Divisies,
    GoogleDocument,
    Milstones,
    Project,
    TimeRegistry,
    Todo,
    UserProfile,
)

logger = logging.getLogger(__name__)


# 1. Het Dashboard (Hoofdpagina)
class DashboardView(TenantObjectMixin, View):
    """View voor het dashboard (index) met projectoverzicht en interactieve to-do lijst."""

    template_name = "dashboard/index.html"

    def get_context_data(self, request):
        company = request.user.profile.company
        today = timezone.now().date()

        # Projecten ophalen
        projects = Project.objects.filter(company=company).order_by("project_name")

        # Actieve timer ophalen
        active_timer = TimeRegistry.objects.filter(
            user=request.user, end_time__isnull=True
        ).first()

        # Klanten voor de filters
        customers = Customer.objects.filter(company=company)
        divisies = Divisies.objects.filter(company=company)

        # TO-DO LOGICA
        todos = Todo.objects.filter(company=company, user=request.user).select_related(
            "project_id", "customer_id", "user"
        )

        # Filters verwerken
        customer_filter = request.GET.get("customer")
        if customer_filter:
            todos = todos.filter(customer_id__id=customer_filter)

        project_filter = request.GET.get("project")
        if project_filter:
            todos = todos.filter(project_id__id=project_filter)

        divisie_filter = request.GET.get("divisie")
        if divisie_filter:
            todos = todos.filter(divisie__id=divisie_filter)

        # Default op dashboard: toon enkel onvoltooide taken tenzij anders gevraagd
        is_completed = request.GET.get("is_completed", "false")
        if is_completed == "true":
            todos = todos.filter(is_completed=True)
        elif is_completed == "false":
            todos = todos.filter(is_completed=False)

        # Sortering: 1. Datum (oplopend), 2. Prioriteit (1=hoogst), 3. Aanmaakdatum
        todos = todos.order_by("due_date", "priority", "-created_at")

        return {
            "projects": projects,
            "active_timer": active_timer,
            "customers": customers,
            "divisies": divisies,
            "todos": todos,
            "today": today,  # Nodig voor de kleurcodes in de template
        }

    def get(self, request):
        context = self.get_context_data(request)
        return render(request, self.template_name, context)


# 2. Klanten Beheer (Aanmaken) - Aangepast om handmatig company te koppelen
class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    fields = ["customer_name", "customer_email"]
    template_name = "dashboard/customer_form.html"
    success_url = reverse_lazy("eventaflow:dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customers"] = Customer.objects.filter(company=self.request.user.profile.company)
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Koppel de klant aan het bedrijf van de huidige gebruiker
                form.instance.company = self.request.user.profile.company
                return super().form_valid(form)
        except Exception as e:
            form.add_error(None, f"Fout bij aanmaken klant: {e}")
            return self.form_invalid(form)


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    fields = ["customer_name", "customer_email"]
    template_name = "dashboard/customer_form.html"
    success_url = reverse_lazy("eventaflow:dashboard")

    def get_queryset(self):
        return Customer.objects.filter(company=self.request.user.profile.company)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customers"] = Customer.objects.filter(company=self.request.user.profile.company)
        return context


# 3. Projecten Beheer (Aanmaken) - Aangepast om handmatig company te koppelen
class ProjectFormMixin:
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.is_authenticated:
            form.fields["customer"].queryset = Customer.objects.filter(
                company=self.request.user.profile.company
            )

        field_widget_attrs = {
            "customer": {
                "class": "block w-full pl-10 pr-3 py-3 border border-gray-300 rounded-xl "
                "shadow-sm focus:ring-2 focus:ring-green-500 focus:border-green-500 "
                "transition-all outline-none bg-white appearance-none",
            },
            "project_name": {
                "class": "block w-full pl-10 pr-3 py-3 border border-gray-300 rounded-xl "
                "shadow-sm focus:ring-2 focus:ring-green-500 focus:border-green-500 "
                "transition-all outline-none",
                "placeholder": "Bijv. Website Vernieuwing",
            },
            "start_date": {
                "class": "block w-full px-4 py-3 border border-gray-300 rounded-xl "
                "shadow-sm focus:ring-2 focus:ring-green-500 focus:border-green-500 "
                "transition-all outline-none",
            },
            "end_date": {
                "class": "block w-full px-4 py-3 border border-gray-300 rounded-xl "
                "shadow-sm focus:ring-2 focus:ring-green-500 focus:border-green-500 "
                "transition-all outline-none",
            },
            "project_description": {
                "class": "block w-full px-4 py-3 border border-gray-300 rounded-xl "
                "shadow-sm focus:ring-2 focus:ring-green-500 focus:border-green-500 "
                "transition-all outline-none",
                "rows": "3",
                "placeholder": "Korte omschrijving van de werkzaamheden...",
            },
            "is_active": {
                "class": "w-5 h-5 text-green-600 border-gray-300 rounded focus:ring-green-500",
            },
        }

        for field_name, attrs in field_widget_attrs.items():
            if field_name in form.fields:
                form.fields[field_name].widget.attrs.update(attrs)

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projects"] = Project.objects.filter(
            company=self.request.user.profile.company
        ).order_by("project_name")
        return context


class ProjectCreateView(ProjectFormMixin, LoginRequiredMixin, CreateView):
    model = Project
    fields = [
        "customer",
        "project_name",
        "project_description",
        "start_date",
        "end_date",
        "is_active",
    ]
    template_name = "dashboard/project_form.html"
    success_url = reverse_lazy("eventaflow:dashboard")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Koppel het project aan het bedrijf van de huidige gebruiker
                form.instance.company = self.request.user.profile.company
                return super().form_valid(form)
        except Exception as e:
            form.add_error(None, f"Fout bij aanmaken project: {e}")
            return self.form_invalid(form)


class ProjectUpdateView(ProjectFormMixin, LoginRequiredMixin, UpdateView):
    model = Project
    fields = [
        "customer",
        "project_name",
        "project_description",
        "start_date",
        "end_date",
        "is_active",
    ]
    template_name = "dashboard/project_form.html"
    success_url = reverse_lazy("eventaflow:dashboard")

    def get_queryset(self):
        return Project.objects.filter(company=self.request.user.profile.company)

    def form_valid(self, form):
        form.instance.company = self.request.user.profile.company
        return super().form_valid(form)


# 4. Export View (Directe Download naar Excel met 5-minuten afronding en totaaltelling)
class ExportView(TenantObjectMixin, View):
    template_name = "dashboard/export.html"

    def get(self, request):
        company = request.user.profile.company
        customers = Customer.objects.filter(company=company)
        projects = Project.objects.filter(company=company)

        return render(request, self.template_name, {"customers": customers, "projects": projects})

    def post(self, request):
        company = request.user.profile.company

        # Filters ophalen
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        customer_id = request.POST.get("customer")
        project_id = request.POST.get("project")

        # Queryset filteren
        entries = TimeRegistry.objects.filter(company=company).order_by("start_time")
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

        headers = [
            "Datum",
            "Klant",
            "Project",
            "Gebruiker",
            "Start",
            "Eind",
            "Duur (u)",
            "Omschrijving",
        ]
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

            ws.append(
                [
                    entry.start_time.strftime("%d-%m-%Y") if entry.start_time else "",
                    entry.project.customer.customer_name,
                    entry.project.project_name,
                    entry.user.username,
                    entry.start_time.strftime("%H:%M") if entry.start_time else "",
                    entry.end_time.strftime("%H:%M") if entry.end_time else "Lopend",
                    duration,
                    entry.description,
                ]
            )

        # Voeg een lege regel toe voor de overzichtelijkheid
        ws.append([])

        # Voeg de totaalregel toe
        # We plaatsen 'TOTAAL' in de kolom van de medewerker/eindtijd en de som in de duur-kolom
        ws.append(["", "", "", "", "", "TOTAAL:", round(total_duration, 2), ""])

        # Response voor download
        filename = f"urenexport_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)

        return response


# 5. NIEUW: Aparte View voor Gebruiker Registratie
class RegisterUserView(View):
    """Maakt alleen een User en UserProfile aan, logt in en stuurt door."""

    template_name = "registration/login.html"

    def post(self, request):
        # Haal data uit de rechterkolom van login.html
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")

        # Basis validatie
        if not all([username, email, password, password_confirm]):
            return render(request, self.template_name, {"reg_error": "Vul alle velden in."})

        if password != password_confirm:
            return render(
                request,
                self.template_name,
                {"reg_error": "Wachtwoorden komen niet overeen."},
            )

        if User.objects.filter(username=username).exists():
            return render(
                request,
                self.template_name,
                {"reg_error": "Deze gebruikersnaam is al bezet."},
            )

        try:
            with transaction.atomic():
                # 1. Maak User aan
                user = User.objects.create_user(username=username, email=email, password=password)
                # 2. Maak UserProfile aan (zonder company)
                UserProfile.objects.get_or_create(user=user)

                # 3. Log in
                login(request, user)

            # 4. Stuur door naar de bedrijfsselectie (die zal redirecten naar create_company)
            return redirect("eventaflow:select_company")
        except Exception as e:
            return render(request, self.template_name, {"reg_error": f"Technisch probleem: {e}"})


class CompanySelectionView(LoginRequiredMixin, ListView):
    model = Company
    template_name = "companies/select_company.html"
    context_object_name = "companies"

    def get_queryset(self):
        return self.request.user.companies.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, "profile", None)
        context["active_company"] = getattr(profile, "company", None) if profile else None
        return context


@login_required
def switch_company(request, company_id):
    # Check of het bedrijf bestaat EN of de user lid is (members)
    # Dit is belangrijk voor de beveiliging!
    company = get_object_or_404(Company, id=company_id, members=request.user)

    # Zet dit bedrijf als actief in het profiel
    # Zorg dat je signalen of een save() methode hebt die het profiel aanmaakt als het niet bestaat
    if not hasattr(request.user, "profile"):
        UserProfile.objects.create(user=request.user)

    request.user.profile.company = company
    request.user.profile.save()

    return redirect("eventaflow:dashboard")


class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    fields = ["name"]
    template_name = "companies/create_company.html"
    success_url = reverse_lazy("eventaflow:dashboard")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # We halen de instance op van het formulier
                # zonder deze direct naar de DB te schrijven
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


# logger = logging.getLogger(__name__)


class CompanyDetailView(LoginRequiredMixin, View):
    template_name = "companies/company_detail.html"

    def get_context_data(self, company):
        """Helper-methode om de context op te bouwen voor de template."""
        return {
            "company": company,
            "company_employees": UserProfile.objects.filter(company=company),
            "divisies": Divisies.objects.filter(company=company),
            "google_configured": bool(company.google_client_id and company.google_client_secret),
            "google_authorized": bool(company.google_oauth_token),
        }

    def get(self, request):
        company = request.user.profile.company
        if not company:
            messages.error(request, "Je bent niet gekoppeld aan een bedrijf.")
            return redirect("eventaflow:dashboard")
        return render(request, self.template_name, self.get_context_data(company))

    def post(self, request):
        company = request.user.profile.company
        if not company:
            messages.error(request, "Je bent niet gekoppeld aan een bedrijf.")
            return redirect("eventaflow:dashboard")

        # Controleer of de gebruiker superuser is OF de rol van company admin heeft
        is_admin = request.user.profile.is_company_admin or request.user.is_superuser
        if not is_admin:
            messages.error(request, "Je hebt geen rechten om deze actie uit te voeren.")
            return render(request, self.template_name, self.get_context_data(company))

        # 1. Bedrijfsnaam bijwerken
        if "update_company" in request.POST:
            company_name = request.POST.get("company_name", "").strip()
            if not company_name:
                messages.error(request, "Voer een bedrijfsnaam in.")
            else:
                company.name = company_name
                company.save()
                messages.success(request, "Bedrijfsnaam is bijgewerkt.")

        # 2. Medewerker toevoegen via e-mail
        elif "add_employee" in request.POST:
            email = request.POST.get("employee_email", "").strip()
            if not email:
                messages.error(request, "Voer alstublieft een e-mailadres in.")
            else:
                try:
                    user_to_add = User.objects.get(email__iexact=email)
                    existing_profile = UserProfile.objects.filter(
                        user=user_to_add, company=company
                    ).first()
                    if existing_profile:
                        messages.warning(
                            request,
                            f"{user_to_add.username} is al lid van dit bedrijf.",
                        )
                    else:
                        profile, created = UserProfile.objects.get_or_create(user=user_to_add)
                        profile.company = company
                        profile.is_company_admin = False
                        profile.save()
                        company.members.add(user_to_add)
                        messages.success(
                            request,
                            f"{user_to_add.username} ({user_to_add.email})"
                            f" is toegevoegd aan het bedrijf.",
                        )
                except User.DoesNotExist:
                    messages.error(
                        request,
                        f"Geen gebruiker gevonden met e-mailadres '{email}'."
                        f" Controleer het e-mailadres.",
                    )

        # 3. Medewerker verwijderen
        elif "remove_employee" in request.POST:
            employee_id = request.POST.get("remove_employee")
            try:
                profile = UserProfile.objects.get(id=employee_id, company=company)
                user_name = profile.user.username
                profile.delete()
                messages.success(request, f"{user_name} is verwijderd uit het bedrijf.")
            except UserProfile.DoesNotExist:
                messages.error(request, "Medewerker niet gevonden.")

        # 4. Divisie toevoegen
        elif "add_divisie" in request.POST:
            divisie_name = request.POST.get("divisie_name", "").strip()
            if not divisie_name:
                messages.error(request, "Voer alstublieft een divisienaam in.")
            else:
                try:
                    with transaction.atomic():
                        if Divisies.objects.filter(
                            company=company, divisie_name__iexact=divisie_name
                        ).exists():
                            messages.warning(request, f"Divisie '{divisie_name}' bestaat al.")
                        else:
                            Divisies.objects.create(divisie_name=divisie_name, company=company)
                            messages.success(request, f"Divisie '{divisie_name}' is toegevoegd.")
                except Exception as e:
                    messages.error(request, f"Fout bij aanmaken divisie: {e}")

        # 5. Divisie verwijderen
        elif "remove_divisie" in request.POST:
            divisie_id = request.POST.get("remove_divisie")
            try:
                divisie = Divisies.objects.get(id=divisie_id, company=company)
                divisie_name = divisie.divisie_name
                divisie.delete()
                messages.success(request, f"Divisie '{divisie_name}' is verwijderd.")
            except Divisies.DoesNotExist:
                messages.error(request, "Divisie niet gevonden.")

        # 6. Google OAuth Credentials opslaan
        elif "update_google_credentials" in request.POST:
            client_id = request.POST.get("google_client_id", "").strip()
            client_secret = request.POST.get("google_client_secret", "").strip()

            if client_id and client_secret:
                company.google_client_id = client_id

                # Sla client_secret alleen op als het geen gemaskeerde weergave is
                if client_secret != "********": # nosec B105
                    company.google_client_secret = client_secret

                company.save()
                messages.success(
                    request,
                    "Google OAuth credentials succesvol opgeslagen! "
                    "Klik nu op de groene knop om de autorisatie te starten.",
                )
            else:
                messages.error(
                    request, "Zowel het Client ID als het Client Secret zijn verplicht."
                )

        # 7. Google Credentials en actieve Tokens volledig verwijderen (Ontkoppelen)
        elif "remove_google_credentials" in request.POST:
            company.google_client_id = None
            company.google_client_secret = None
            company.google_oauth_token = None
            company.save()
            messages.success(
                request, "Google Drive integratie en actieve tokens zijn succesvol verwijderd."
            )

        return render(request, self.template_name, self.get_context_data(company))


# 6. Uitloggen
class LoginView(RedirectView):
    url = reverse_lazy("login")

    def get(self, request, *args, **kwargs):
        logout(request)
        return super().get(request, *args, **kwargs)


# 1.1 View om de timer te starten
def start_timer(request):
    if request.method == "POST":
        # We gebruiken de database 'id' uit het <select> element
        project_pk = request.POST.get("project")
        if project_pk:
            project = get_object_or_404(
                Project, pk=project_pk, company=request.user.profile.company
            )

            # Voorkom dubbele actieve timers
            active_timer = TimeRegistry.objects.filter(
                user=request.user, end_time__isnull=True
            ).exists()

            if not active_timer:
                TimeRegistry.objects.create(
                    user=request.user,
                    project=project,
                    company=request.user.profile.company,
                    description=request.POST.get("description"),
                    start_time=timezone.now(),
                )
    return redirect("eventaflow:dashboard")


# 1.2 View om de timer te stoppen
def stop_timer(request, timer_id):
    # Alleen stoppen via POST voor de veiligheid (tegen 405 errors)
    if request.method == "POST":
        timer = get_object_or_404(TimeRegistry, id=timer_id, user=request.user)
        timer.end_time = timezone.now()
        timer.description = request.POST.get("description")
        timer.save()
    return redirect("eventaflow:dashboard")


# 5. To-Do List View
class TodoListView(LoginRequiredMixin, View):
    """View voor het beheren van taken (to-do's) met edit-functionaliteit via URL parameters."""

    template_name = "dashboard/to-do-beheer.html"

    def get_context_data(self, request):
        company = request.user.profile.company

        # Haal basisgegevens op voor dropdowns
        customers = Customer.objects.filter(company=company)
        projects = Project.objects.filter(company=company)
        divisies = Divisies.objects.filter(company=company)
        milestone = Milstones.objects.filter(company=company)
        company_members = company.members.all()

        # Filtering logica voor de linkerlijst
        todos = Todo.objects.filter(company=company).select_related(
            "user", "project_id", "customer_id"
        )

        customer_filter = request.GET.get("customer")
        if customer_filter:
            todos = todos.filter(customer_id__id=customer_filter)

        project_filter = request.GET.get("project")
        if project_filter:
            todos = todos.filter(project_id__id=project_filter)

        divisie_filter = request.GET.get("divisie")
        if divisie_filter:
            todos = todos.filter(divisie__id=divisie_filter)

        milestone_filter = request.GET.get("milestone")
        if milestone_filter:
            todos = todos.filter(milestone__id=milestone_filter)

        is_completed = request.GET.get("is_completed")
        if is_completed == "true":
            todos = todos.filter(is_completed=True)

        elif is_completed == "false":
            todos = todos.filter(is_completed=False)

        todos = todos.order_by("-created_at")

        # Bewerkingslogica: check of er een ?edit=ID parameter is
        form_instance = None
        edit_id = request.GET.get("edit")
        if edit_id:
            # We filteren op company om te zorgen dat gebruikers
            # geen taken van andere bedrijven kunnen editen
            form_instance = get_object_or_404(Todo, id=edit_id, company=company)

        return {
            "customers": customers,
            "projects": projects,
            "divisies": divisies,
            "company_members": company_members,
            "todos": todos,
            "milestone": milestone,
            "form": TodoForm(instance=form_instance),
            "edit_id": edit_id,
        }

    def get(self, request):
        context = self.get_context_data(request)
        return render(request, self.template_name, context)

    def post(self, request):
        # Check of we een bestaande taak updaten (verborgen 'id' veld in HTML)
        todo_id = request.POST.get("id")
        company = request.user.profile.company

        if todo_id:
            instance = get_object_or_404(Todo, id=todo_id, company=company)
            form = TodoForm(request.POST, instance=instance)
        else:
            form = TodoForm(request.POST)

        try:
            with transaction.atomic():
                if form.is_valid():
                    todo = form.save(commit=False)
                    todo.company = company
                    # Valideer of er een user is, anders huidige user
                    if not todo.user:
                        todo.user = request.user
                    todo.save()

                    action = "bijgewerkt" if todo_id else "aangemaakt"
                    messages.success(request, f"Taak succesvol {action}!")
                    return redirect("eventaflow:todo_list")
                else:
                    messages.error(request, "Er staan fouten in het formulier.")
                    context = self.get_context_data(request)
                    context["form"] = form
                    return render(request, self.template_name, context)
        except Exception as e:
            messages.error(request, f"Technische fout: {e}")
            context = self.get_context_data(request)
            return render(request, self.template_name, context)


# 6. Toggle Todo Completion Status
@login_required
def toggle_todo(request, todo_id):
    """Toggle de completion status van een taak"""
    if request.method == "POST":
        todo = get_object_or_404(Todo, id=todo_id, company=request.user.profile.company)
        todo.is_completed = not todo.is_completed
        todo.save()
        messages.success(request, "Taak status bijgewerkt!")

    # Redirect back to the page the request came from
    referer = request.META.get("HTTP_REFERER", reverse_lazy("eventaflow:dashboard"))
    return redirect(referer)


# 7. Google Docs Management View


# 8. Milestones View (Vergelijkbaar met TodoListView maar dan voor Milestones)
class MilestonesView(LoginRequiredMixin, View):
    """View voor het beheren van taken Milestones met edit-functionaliteit via URL parameters."""

    template_name = "dashboard/milestones.html"

    def get(self, request):
        company = request.user.profile.company

        # Haal basisgegevens op voor dropdowns
        projects = Project.objects.filter(company=company)
        divisies = Divisies.objects.filter(company=company)

        # Filtering logica voor de linkerlijst
        milestones = (
            Milstones.objects.filter(company=company)
            .select_related("project", "divisie")
            .annotate(
                total_todos=Count("todos"),
                completed_todos=Sum(
                    Case(
                        When(todos__is_completed=True, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
            )
        )

        project_filter = request.GET.get("project")
        if project_filter:
            milestones = milestones.filter(project__id=project_filter)

        divisie_filter = request.GET.get("divisie")
        if divisie_filter:
            milestones = milestones.filter(divisie__id=divisie_filter)

        is_completed = request.GET.get("is_completed")
        if is_completed == "true":
            milestones = milestones.filter(is_completed=True)
        elif is_completed == "false":
            milestones = milestones.filter(is_completed=False)

        milestones = milestones.order_by("-created_at")

        # Bewerkingslogica: check of er een ?edit=ID parameter is
        form_instance = None
        edit_id = request.GET.get("edit")
        if edit_id:
            form_instance = get_object_or_404(Milstones, id=edit_id, company=company)

        return render(
            request,
            self.template_name,
            context={
                "projects": projects,
                "divisies": divisies,
                "milestones": milestones,
                "form": MilestoneForm(instance=form_instance),
                "edit_id": edit_id,
            },
        )

    def post(self, request):
        # Check of we een bestaande taak updaten (verborgen 'id' veld in HTML)
        milestone_id = request.POST.get("id")
        company = request.user.profile.company

        if milestone_id:
            instance = get_object_or_404(Milstones, id=milestone_id, company=company)
            form = MilestoneForm(request.POST, instance=instance)
        else:
            form = MilestoneForm(request.POST)

        try:
            with transaction.atomic():
                if form.is_valid():
                    milestone = form.save(commit=False)
                    milestone.company = company
                    milestone.save()

                    action = "bijgewerkt" if milestone_id else "aangemaakt"
                    messages.success(request, f"Milestone succesvol {action}!")
                    return redirect("eventaflow:milestone_list")
                else:
                    messages.error(request, "Er staan fouten in het formulier.")
                    context = self._get_context(request)
                    context["form"] = form
                    return render(request, self.template_name, context)
        except Exception as e:
            messages.error(request, f"Technische fout: {e}")
            context = self._get_context(request)
            return render(request, self.template_name, context)

    def _get_context(self, request):
        """Helper method to get context data for rendering the template."""
        company = request.user.profile.company
        projects = Project.objects.filter(company=company)
        divisies = Divisies.objects.filter(company=company)
        milestones = (
            Milstones.objects.filter(company=company)
            .select_related("project", "divisie")
            .annotate(
                total_todos=Count("todos"),
                completed_todos=Sum(
                    Case(
                        When(todos__is_completed=True, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
            )
            .order_by("-created_at")
        )

        return {
            "projects": projects,
            "divisies": divisies,
            "milestones": milestones,
            "form": MilestoneForm(),
        }


# 8.1. Toggle Milestone Completion Status
@login_required
def toggle_milestone(request, milestone_id):
    """Toggle de completion status van een milestone"""
    if request.method == "POST":
        milestone = get_object_or_404(
            Milstones, id=milestone_id, company=request.user.profile.company
        )
        milestone.is_completed = not milestone.is_completed
        milestone.save()
        messages.success(request, "Milestone status bijgewerkt!")

    return redirect("eventaflow:milestone_list")


@login_required
def create_doc_view(request):
    """
    View om direct een nieuw, leeg Google Doc aan te maken voor het actieve bedrijf.
    """
    active_company_id = request.session.get("active_company_id")
    if not active_company_id:
        return redirect("company_select")

    company = get_object_or_404(Company, id=active_company_id)

    if request.method == "POST":
        title = request.POST.get("title", "Naamloos Document")

        # Initialiseer de service voor dit specifieke bedrijf
        service = GoogleDriveService(company)

        # Maak het lege document aan op Google Drive
        google_file_id = service.create_empty_google_doc(title)

        if google_file_id:
            # Sla de referentie op in onze lokale Django database
            doc = GoogleDocument.objects.create(
                company=company, title=title, google_file_id=google_file_id, file_type="document"
            )
            return redirect("view_document", doc_id=doc.id)

    return render(request, "docs/create_document.html")


@login_required
def upload_file_view(request):
    """
    View die een lokaal bestand (Word, Excel, PDF) accepteert,
    het uploadt naar Google Drive, en optioneel converteert naar een Google Doc/Sheet.
    """
    active_company_id = request.session.get("active_company_id")
    if not active_company_id:
        return redirect("company_select")

    company = get_object_or_404(Company, id=active_company_id)

    if request.method == "POST" and request.FILES.get("file"):
        uploaded_file = request.FILES["file"]
        title = request.POST.get("title", uploaded_file.name)

        # Wil de gebruiker automatische conversie naar Google Docs/Sheets?
        # (Dit vinken we standaard aan voor Word en Excel)
        convert = request.POST.get("convert_to_google", "on") == "on"

        service = GoogleDriveService(company)

        # Upload en converteer via onze service
        google_file_id, file_type = service.upload_and_convert_file(
            django_file=uploaded_file,
            title=title,
            original_mime_type=uploaded_file.content_type,
            convert_to_google=convert,
        )

        if google_file_id:
            # Sla op in de lokale database
            doc = GoogleDocument.objects.create(
                company=company, title=title, google_file_id=google_file_id, file_type=file_type
            )
            return redirect("view_document", doc_id=doc.id)

    return render(request, "docs/upload_document.html")


@login_required
def view_document(request, doc_id):
    """
    Toont het bestand in de template.
    Als het een bewerkbaar document/sheet is, embedden we het in een Iframe.
    Als het een PDF is, gebruiken we een PDF viewer of een Drive preview link.
    """
    active_company_id = request.session.get("active_company_id")
    company = get_object_or_404(Company, id=active_company_id)
    document = get_object_or_404(GoogleDocument, id=doc_id, company=company)

    # Haal het Google-emailadres van het gebruikersprofiel op
    user_google_email = request.user.profile.google_email

    service = GoogleDriveService(company)

    # Deel het bestand met de gebruiker zodat de browser-sessie toegang heeft
    # Voor bewerkbare bestanden geven we 'writer', voor PDFs of overig geven we 'reader'
    role = "writer" if document.file_type in ["document", "spreadsheet"] else "reader"
    service.share_file_with_user(document.google_file_id, user_google_email, role=role)

    # Bepaal de juiste Iframe URL op basis van het type bestand
    if document.file_type == "document":
        embed_url = (
            f"https://docs.google.com/document/d/{document.google_file_id}"
            f"/edit?usp=embed_javascript"
        )
    elif document.file_type == "spreadsheet":
        embed_url = (
            f"https://docs.google.com/spreadsheets/d/{document.google_file_id}"
            f"/edit?usp=drivesdk&rm=minimal"
        )
    else:
        # Voor PDFs en overige binaire bestanden gebruiken we de universele Google Drive previewer
        embed_url = f"https://drive.google.com/file/d/{document.google_file_id}/preview"

    context = {
        "document": document,
        "embed_url": embed_url,
    }
    return render(request, "docs/view_document.html", context)


@login_required
def google_settings_view(request):
    """
    Instellingenpagina (gebaseerd op google_settings.html) waar gebruikers met de juiste
    rechten de Google OAuth credentials kunnen beheren en autoriseren.
    """
    company = request.user.profile.company
    if not company:
        messages.error(request, "Je bent niet gekoppeld aan een bedrijf.")
        return redirect("eventaflow:dashboard")

    # Beveiliging: Iedereen binnen het bedrijf mag de status zien,
    # maar alleen admins/superusers mogen POST-wijzigingen doorvoeren.
    is_admin = request.user.profile.is_company_admin or request.user.is_superuser

    if request.method == "POST":
        if not is_admin:
            messages.error(request, "Je hebt geen rechten om deze instellingen aan te passen.")
            return redirect("eventaflow:google_settings")

        client_id = request.POST.get("client_id", "").strip()
        client_secret = request.POST.get("client_secret", "").strip()

        if client_id and client_secret:
            company.google_client_id = client_id

            # Voorkom dat we de gemaskeerde '********' weergave overschrijven in de database
            if client_secret != "********": # nosec B105
                company.google_client_secret = client_secret

            company.save()
            messages.success(
                request, "Google OAuth credentials succesvol opgeslagen. Start nu de autorisatie."
            )
        else:
            messages.error(request, "Vul zowel het Client ID als het Client Secret in.")
        return redirect("eventaflow:google_settings")

    context = {
        "company": company,
        "has_credentials": bool(company.google_client_id and company.google_client_secret),
        "is_authorized": bool(company.google_oauth_token),
    }
    return render(request, "dashboard/google_settings.html", context)


@login_required
def google_authorize_start(request):
    """
    Genereert de autorisatie-URL voor Google en start de flow.
    We voegen hier een cryptografisch veilige 'state' parameter toe om CSRF-aanvallen te voorkomen.
    """
    company = request.user.profile.company
    if not company:
        return HttpResponseBadRequest("Geen bedrijf gekoppeld.")

    client_id = company.google_client_id
    if not client_id:
        messages.error(request, "Sla eerst je Client ID en Client Secret op.")
        return redirect("eventaflow:google_settings")

    # Genereer een cryptografisch veilige state en sla deze op in de sessie van de gebruiker
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    # Bepaal de dynamische callback URI op basis van de huidige host
    redirect_uri = request.build_absolute_uri(reverse("eventaflow:google_callback"))

    # Configureer de parameters voor Google OAuth2
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/documents",
        "access_type": "offline",  # Essentieel om een 'refresh_token' te ontvangen!
        "prompt": "consent",  # Forceert Google om het toestemmingsscherm te tonen
        "state": state,  # CSRF-beveiliging
    }

    authorization_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    )
    return HttpResponseRedirect(authorization_url)


@login_required
def google_authorize_callback(request):
    """
    Callback view waar we de 'state' verifiëren en de autorisatiecode inwisselen voor tokens.
    """
    company = request.user.profile.company
    code = request.GET.get("code")
    returned_state = request.GET.get("state")
    session_state = request.session.pop("oauth_state", None)

    # 1. CSRF controle via de State parameter
    if not session_state or returned_state != session_state:
        messages.error(
            request, "Veiligheidscontrole mislukt (ongeldige OAuth state). Probeer het opnieuw."
        )
        return redirect("eventaflow:google_settings")

    if not code:
        messages.error(request, "Geen autorisatiecode ontvangen van Google.")
        return redirect("eventaflow:google_settings")

    redirect_uri = request.build_absolute_uri(reverse("eventaflow:google_callback"))

    # Wissel de code uit voor tokens
    token_url = "https://oauth2.googleapis.com/token" # nosec B105
    payload = {
        "code": code,
        "client_id": company.google_client_id,
        "client_secret": company.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        # Provide a timeout to avoid hanging requests (Bandit B113)
        response = requests.post(token_url, data=payload, timeout=10)
        response_data = response.json()

        if response.status_code == 200:
            # Sla de tokens gecodeerd op in de database
            company.google_oauth_token = response_data
            company.save()
            messages.success(request, "Google Account met succes gekoppeld aan de app!")
            return redirect("eventaflow:google_docs")
        else:
            error_desc = response_data.get("error_description", "Onbekende fout")
            messages.error(request, f"Fout bij het ophalen van tokens: {error_desc}")
            return redirect("eventaflow:google_settings")

    except requests.exceptions.Timeout:
        messages.error(request, "Verzoek naar Google time-out. Probeer het later opnieuw.")
        return redirect("eventaflow:google_settings")
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Fout tijdens de netwerkverbinding met Google: {e}")
        return redirect("eventaflow:dashboard/google_settings")


@login_required
def generate_project_api_token(request, project_id):
    """Generate an API token for a project and email it to the provided address.

    POST params: `email` (recipient), `single_use` (optional)
    """
    company = request.user.profile.company
    if not company:
        return HttpResponseBadRequest("No company")

    # only company admins may generate tokens
    if not (request.user.profile.is_company_admin or request.user.is_superuser):
        return HttpResponseForbidden("Not allowed")

    project = get_object_or_404(Project, id=project_id, company=company)
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    recipient = request.POST.get("email")
    single_use = request.POST.get("single_use", "true").lower() in ("1", "true", "yes")
    if not recipient:
        return HttpResponseBadRequest("email required")

    key = APIToken.generate_key()
    token = APIToken.objects.create(
        key=key,
        project=project,
        company=company,
        created_by=request.user,
        single_use=single_use,
    )

    # Build a one-click URL that contains the token as a query param
    url = (
        request.build_absolute_uri(reverse("eventaflow:api_project_status"))
        + f"?token={token.key}&project_id={project.id}"
    )

    subject = f"API toegang voor project {project.project_name}"
    # Render plaintext and HTML email with a button
    plaintext = render_to_string("emails/api_token_email.txt", {"url": url, "project": project})
    html_content = render_to_string(
        "emails/api_token_email.html", {"url": url, "project": project}
    )
    msg = EmailMultiAlternatives(subject, plaintext, None, [recipient])
    msg.attach_alternative(html_content, "text/html")
    try:
        msg.send(fail_silently=True)
    except Exception:
        logger.exception("Failed to send API token email")

    return JsonResponse({"status": "ok", "token": token.key})


def _get_token_from_request(request):
    # Try header Authorization: Token <key>
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.startswith("Token "):
        return auth.split(" ", 1)[1].strip()
    # fallback to query param
    return request.GET.get("token") or request.POST.get("token")


def api_project_status(request):
    """Return project status as JSON when a valid token is supplied.

    Accepts token via `Authorization: Token <key>` header or `?token=` query param.
    """
    token_key = _get_token_from_request(request)
    project_id = request.GET.get("project_id") or request.POST.get("project_id")
    if not token_key or not project_id:
        return HttpResponseForbidden("token and project_id required")

    try:
        token = APIToken.objects.get(key=token_key, is_active=True)
    except APIToken.DoesNotExist:
        return HttpResponseForbidden("invalid token")

    # check expiry
    if token.expires_at and timezone.now() > token.expires_at:
        return HttpResponseForbidden("token expired")

    if str(token.project.id) != str(project_id):
        return HttpResponseForbidden("project mismatch")

    project = token.project

    # Build a simple status payload
    time_entries = TimeRegistry.objects.filter(project=project).order_by("-start_time")[:20]
    entries = [
        {
            "user": t.user.username,
            "start_time": t.start_time.isoformat(),
            "end_time": t.end_time.isoformat() if t.end_time else None,
            "description": t.description,
        }
        for t in time_entries
    ]

    payload = {
        "project": {
            "id": project.id,
            "name": project.project_name,
            "description": project.project_description,
            "is_active": project.is_active,
        },
        "recent_time_entries": entries,
    }

    # record usage
    try:
        remote_ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR"))
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        APITokenUsage.objects.create(token=token, remote_ip=remote_ip, user_agent=user_agent)
    except Exception:
        logger.exception("Failed to record token usage")

    # include todos and milestones for the project
    todos_qs = Todo.objects.filter(project_id=project).order_by("-created_at")[:50]
    milestones_qs = Milstones.objects.filter(project=project).order_by("-due_date")[:50]

    payload["todos"] = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "is_completed": t.is_completed,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in todos_qs
    ]

    payload["milestones"] = [
        {
            "id": m.id,
            "title": m.title,
            "description": m.description,
            "is_completed": m.is_completed,
            "due_date": m.due_date.isoformat() if m.due_date else None,
        }
        for m in milestones_qs
    ]

    # mark token used if single-use
    token.mark_used()

    return JsonResponse(payload)


@csrf_exempt
def generate_project_api_token_api(request, project_id):
    """Programmatic endpoint to generate an API token for a project.

    Protects with an application API key sent via header `X-APP-API-KEY` or
    query param `api_key`. Does not require CSRF.
    """
    from django.conf import settings

    # Check API key
    header_key = request.META.get("HTTP_X_APP_API_KEY")
    api_key = header_key or request.GET.get("api_key") or request.POST.get("api_key")
    if not api_key or api_key != getattr(settings, "APP_API_KEY", ""):
        return HttpResponseForbidden("invalid api key")

    # Only POST allowed
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    recipient = request.POST.get("email") or request.GET.get("email")
    single_use = (
        request.POST.get("single_use") or request.GET.get("single_use") or "true"
    ).lower() in ("1", "true", "yes")
    if not recipient:
        return HttpResponseBadRequest("email required")

    project = get_object_or_404(Project, id=project_id)

    key = APIToken.generate_key()
    token = APIToken.objects.create(
        key=key,
        project=project,
        company=project.company,
        created_by=None,
        single_use=single_use,
    )

    url = (
        request.build_absolute_uri(reverse("eventaflow:api_project_status"))
        + f"?token={token.key}&project_id={project.id}"
    )
    subject = f"API toegang voor project {project.project_name}"
    plaintext = render_to_string("emails/api_token_email.txt", {"url": url, "project": project})
    html_content = render_to_string(
        "emails/api_token_email.html", {"url": url, "project": project}
    )
    msg = EmailMultiAlternatives(subject, plaintext, None, [recipient])
    msg.attach_alternative(html_content, "text/html")
    try:
        msg.send(fail_silently=True)
    except Exception:
        logger.exception("Failed to send API token email (api)")

    return JsonResponse({"status": "ok", "token": token.key})


@login_required
def google_docs_view(request):
    """
    Hoofdscherm voor documentenbeheer binnen de gekoppelde divisies en mappen.
    Vangt eventuele ingetrokken tokens (Revocation) netjes op.
    """
    company = request.user.profile.company
    divisies = Divisies.objects.filter(company=company)
    docs = GoogleDocument.objects.filter(company=company)

    iframe_url = None
    is_configured = bool(
        company.google_client_id and company.google_client_secret and company.google_oauth_token
    )

    service = None
    if is_configured:
        try:
            service = GoogleDriveService(company)
        except Exception as e:
            # Token Revocation / Intrekken opvangen:
            # Als Google de tokens weigert,
            # wissen we deze om fouten te voorkomen en zetten de app terug in "Ontkoppeld"
            logger.error(f"Fout bij starten Google Drive koppeling (mogelijk ingetrokken): {e}")
            company.google_oauth_token = None
            company.save()
            messages.error(
                request,
                "De Google integratie is niet langer geautoriseerd (mogelijks ingetrokken). "
                "Gelieve opnieuw te koppelen in de instellingen.",
            )
            is_configured = False

    # DYNAMISCHE MAPPING IN HET GEHEUGEN:
    # We lopen alle divisiemappen langs op Google Drive
    # en mappen de lokale docs in-memory naar de juiste divisie-ID
    if service:
        # Initialiseer temp parameters op alle geladen docs
        for d in docs:
            d.temp_divisie_id = "root"
            d.temp_divisie_name = "Hoofdmap"

        for divisie in divisies:
            if divisie.google_drive_folder_id:
                try:
                    # Haal bestanden op specifiek binnen deze divisiemap
                    folder_files = service.list_files_from_drive(
                        limit=100, folder_id=divisie.google_drive_folder_id
                    )
                    folder_file_ids = {f.get("id") for f in folder_files}
                    for d in docs:
                        if d.google_file_id in folder_file_ids:
                            d.temp_divisie_id = str(divisie.pk)
                            d.temp_divisie_name = divisie.divisie_name
                except Exception as e:
                    logger.warning(
                        f"Kon mappen van divisie '{divisie.divisie_name}' niet uitlezen: {e}"
                    )

    if request.method == "POST":
        if not service:
            messages.error(request, "Google integratie is momenteel niet geautoriseerd.")
            return redirect("eventaflow:google_docs")

        action = request.POST.get("action")

        # Synchroniseer bestanden vanuit de Google Drive (Hoofdmap + Divisiemappen)
        if action == "sync":
            synced_count = 0

            # CORRECTIE 1: Haal ENKEL bestanden op die DIRECT in de hoofdmap (root) staan
            # (voorkomt dupliceren in mappen)
            try:
                drive_files = service.list_files_from_drive(limit=50, folder_id="root")
                for f in drive_files:
                    file_id = f.get("id")
                    name = f.get("name")
                    mime_type = f.get("mimeType")

                    if mime_type == "application/vnd.google-apps.document":
                        file_type = "document"
                    elif mime_type == "application/vnd.google-apps.spreadsheet":
                        file_type = "spreadsheet"
                    else:
                        continue

                    obj, created = GoogleDocument.objects.get_or_create(
                        google_file_id=file_id,
                        defaults={"company": company, "title": name, "file_type": file_type},
                    )
                    if created:
                        synced_count += 1
            except Exception as e:
                logger.error(f"Fout bij synchroniseren hoofdmap: {e}")

            # 2. Haal alle bestanden op die binnen bestaande divisie-mappen staan
            for divisie in divisies:
                if divisie.google_drive_folder_id:
                    try:
                        folder_files = service.list_files_from_drive(
                            limit=50, folder_id=divisie.google_drive_folder_id
                        )
                        for f in folder_files:
                            file_id = f.get("id")
                            name = f.get("name")
                            mime_type = f.get("mimeType")

                            if mime_type == "application/vnd.google-apps.document":
                                file_type = "document"
                            elif mime_type == "application/vnd.google-apps.spreadsheet":
                                file_type = "spreadsheet"
                            else:
                                continue

                            obj, created = GoogleDocument.objects.get_or_create(
                                google_file_id=file_id,
                                defaults={
                                    "company": company,
                                    "title": name,
                                    "file_type": file_type,
                                },
                            )
                            if created:
                                synced_count += 1
                    except Exception as e:
                        logger.error(
                            f"Fout bij synchroniseren divisie-map '{divisie.divisie_name}': {e}"
                        )

            messages.success(
                request,
                f"Synchronisatie voltooid! {synced_count} "
                f"nieuwe documenten van Google Drive geïmporteerd.",
            )
            return redirect("eventaflow:google_docs")

        elif action == "create_division_folder":
            divisie_pk = request.POST.get("divisie_pk")
            divisie = get_object_or_404(Divisies, pk=divisie_pk, company=company)

            folder_id = service.create_folder(name=divisie.divisie_name, share_with_members=True)
            if folder_id:
                divisie.google_drive_folder_id = folder_id
                divisie.save()
                messages.success(
                    request,
                    f"Google Drive map succesvol aangemaakt voor '{divisie.divisie_name}'.",
                )
            else:
                messages.error(request, "Kan map niet aanmaken.")
            return redirect("eventaflow:google_docs")

        elif action == "create":
            title = request.POST.get("title")
            file_type = request.POST.get("file_type")
            divisie_pk = request.POST.get("divisie_pk")

            parent_folder_id = None
            if divisie_pk:
                divisie = get_object_or_404(Divisies, pk=divisie_pk, company=company)
                parent_folder_id = divisie.google_drive_folder_id

            google_file_id = service.create_empty_google_doc(
                title=title, file_type=file_type, parent_folder_id=parent_folder_id
            )

            if google_file_id:
                GoogleDocument.objects.create(
                    company=company,
                    title=title,
                    google_file_id=google_file_id,
                    file_type=file_type,
                )
                messages.success(request, f"Document '{title}' aangemaakt.")
            else:
                messages.error(request, "Kan document niet aanmaken.")
            return redirect("eventaflow:google_docs")

        elif action == "upload":
            uploaded_file = request.FILES.get("file")
            upload_title = request.POST.get("upload_title") or uploaded_file.name
            divisie_pk = request.POST.get("divisie_pk")

            parent_folder_id = None
            if divisie_pk:
                divisie = get_object_or_404(Divisies, pk=divisie_pk, company=company)
                parent_folder_id = divisie.google_drive_folder_id

            google_file_id, file_type = service.upload_and_convert_file(
                django_file=uploaded_file,
                title=upload_title,
                original_mime_type=uploaded_file.content_type,
                convert_to_google=True,
                parent_folder_id=parent_folder_id,
            )

            if google_file_id:
                GoogleDocument.objects.create(
                    company=company,
                    title=upload_title,
                    google_file_id=google_file_id,
                    file_type=file_type,
                )
                messages.success(request, "Bestand geüpload.")
            else:
                messages.error(request, "Upload mislukt.")
            return redirect("eventaflow:google_docs")

        elif action == "open":
            doc_pk = request.POST.get("doc_pk")
            doc = get_object_or_404(GoogleDocument, pk=doc_pk, company=company)
            service.share_file_with_user(doc.google_file_id, request.user.email, role="writer")
            iframe_url = service.get_iframe_url(doc.google_file_id, doc.file_type, mode="edit")
        """
        elif action == "share":
            doc_pk = requests.request.POST.get("doc_pk")
            doc = get_object_or_404(GoogleDocument, pk=doc_pk, company=company)
            service.share_folder_with_company_members(doc.google_file_id, role='writer')
            messages.success(request, f"'{doc.title}' is gedeeld met alle collega's.")
            return redirect('eventaflow:google_docs')
        """
    context = {
        "divisies": divisies,
        "docs": docs,
        "iframe_url": iframe_url,
        "is_configured": is_configured,
        "is_admin": request.user.profile.is_company_admin or request.user.is_superuser,
    }
    return render(request, "dashboard/google_docs.html", context)
