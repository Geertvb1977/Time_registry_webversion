"""
URL configuration for djangoproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from time_reg_web.forms import TailwindPasswordResetForm
from time_reg_web import urls

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Authenticatie (Centraal beheerd)
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Wachtwoord herstel
    path('password-reset/', 
        auth_views.PasswordResetView.as_view(
            form_class=TailwindPasswordResetForm,
            template_name='registration/password_reset_form.html',
            html_email_template_name='registration/password_reset_email.html',
        ), 
        name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url=reverse_lazy('login')
         ), 
         name='password_reset_confirm'),

    # De app URL's met de naam 'eventaflow' als namespace
    path('', include(('time_reg_web.urls', 'eventaflow'))),
]
