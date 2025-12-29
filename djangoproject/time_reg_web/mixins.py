"""Mixin voor multi-tenant support in Django views."""

from django.contrib.auth.mixins import LoginRequiredMixin
# from django.core.exceptions import PermissionDenied


class TenantObjectMixin(LoginRequiredMixin):
    """
    Deze mixin zorgt ervoor dat gebruikers alleen objecten kunnen zien,
    bewerken of verwijderen die bij hun bedrijf horen.
    """
    def get_queryset(self):
        """ Ophalen en filteren van de queryset op basis van het bedrijf van de gebruiker. """
        # 1. Haal de originele queryset op van de view
        queryset = super().get_queryset()

        # 2. Controleer of de gebruiker een profiel en bedrijf heeft
        if not hasattr(self.request.user, 'profile') or not self.request.user.profile.company:
            # Als de gebruiker geen bedrijf heeft, mag hij niets zien
            return queryset.none()

        # 3. Filter de queryset op het bedrijf van de gebruiker
        return queryset.filter(company=self.request.user.profile.company)

    def form_valid(self, form):
        """
        Zorgt ervoor dat bij het aanmaken van een nieuw object
        (zoals een Project) het 'company' veld automatisch wordt ingevuld.
        """
        form.instance.company = self.request.user.profile.company
        return super().form_valid(form)

# --- VOORBEELD GEBRUIK IN VIEWS.PY ---

# Stel je hebt een ListView voor projecten:
# from django.views.generic import ListView
# from .models import Project

# class ProjectListView(TenantObjectMixin, ListView):
#     model = Project
#     template_name = 'projects/project_list.html'
#     # Je hoeft hier GEEN get_queryset meer te schrijven,
#     # de mixin filtert dit nu veilig op de achtergrond.
