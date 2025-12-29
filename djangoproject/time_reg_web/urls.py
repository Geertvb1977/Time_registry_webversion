""" URL-configuratie voor de time_reg_web app."""

from django.urls import path
from . import views


urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('register/', views.RegisterCompanyView.as_view(), name='register_company'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('customer/new/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('project/new/', views.ProjectCreateView.as_view(), name='project_create'),
]
