""" URL-configuratie voor de time_reg_web app."""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.RegisterCompanyView.as_view(), name='register_company'),
    path('customer/new/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('project/new/', views.ProjectCreateView.as_view(), name='project_create'),
    path('timer/start/', views.start_timer, name='start_timer'),
    path('timer/stop/<int:timer_id>/', views.stop_timer, name='stop_timer'),
    path('export/', views.ExportView.as_view(), name='export'),
]
