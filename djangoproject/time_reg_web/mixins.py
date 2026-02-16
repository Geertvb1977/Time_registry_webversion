"""Mixin voor multi-tenant support in Django views."""

from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin

class TenantObjectMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        # 1. Is user ingelogd? (LoginRequiredMixin doet dit al, maar dubbelcheck voor flow)
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # 2. Heeft de user een actief bedrijf in zijn profiel?
        if not hasattr(request.user, 'profile') or not request.user.profile.company:
            # GEEN bedrijf? -> Forceer naar selectie/aanmaak pagina
            # Voorkom redirect loop als we al op de selectie pagina zitten
            if request.resolver_match.url_name not in ['select_company', 'create_company', 'switch_company']:
                return redirect('eventaflow:select_company')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if not hasattr(self.request.user, 'profile') or not self.request.user.profile.company:
            return queryset.none()
        return queryset.filter(company=self.request.user.profile.company)
