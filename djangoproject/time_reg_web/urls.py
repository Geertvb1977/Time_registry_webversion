""" URL-configuratie voor de time_reg_web app."""

from django.urls import path
from . import views

# Omdat we de namespace in de include hebben gezet, hoeven we hier niets extra's te doen
urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('select_company/', views.CompanySelectionView.as_view(), name='select_company'),
    path('create_company/', views.CompanyCreateView.as_view(), name='create_company'),
    path('switch_company/<int:company_id>/', views.switch_company, name='switch_company'),
    path('register/', views.RegisterUserView.as_view(), name='register_company'),
    path('customer/new/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('project/new/', views.ProjectCreateView.as_view(), name='project_create'),
    path('timer/start/', views.start_timer, name='start_timer'),
    path('timer/stop/<int:timer_id>/', views.stop_timer, name='stop_timer'),
    path('export/', views.ExportView.as_view(), name='export'),
]
