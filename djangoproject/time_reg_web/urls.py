""" URL-configuratie voor de time_reg_web app."""

from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from time_reg_web.forms import TailwindPasswordResetForm

from . import views


urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('select_company/', views.CompanySelectionView.as_view(), name='select_company'),
    path('create_company/', views.CompanyCreateView.as_view(), name='create_company'),
    path('switch_company/<int:company_id>/', views.switch_company, name='switch_company'),
    path('register/', views.RegisterCompanyView.as_view(), name='register_company'),
    path('customer/new/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('project/new/', views.ProjectCreateView.as_view(), name='project_create'),
    path('timer/start/', views.start_timer, name='start_timer'),
    path('timer/stop/<int:timer_id>/', views.stop_timer, name='stop_timer'),
    path('export/', views.ExportView.as_view(), name='export'),
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
]
