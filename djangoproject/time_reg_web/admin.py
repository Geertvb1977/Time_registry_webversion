""" Register your models here."""

from django.contrib import admin
from .models import Company, UserProfile, Customer, Project, TimeRegistry


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin interface for Company model."""
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for UserProfile model."""
    list_display = ('user', 'company', 'is_company_admin')
    list_filter = ('company', 'is_company_admin')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin interface for Customer model."""
    list_display = ('customer_name', 'company')
    list_filter = ('company',)
    search_fields = ('name',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin interface for Project model."""
    list_display = ('project_name', 'customer', 'company')
    list_filter = ('company', 'customer')
    search_fields = ('name',)


@admin.register(TimeRegistry)
class TimeRegistryAdmin(admin.ModelAdmin):
    """Admin interface for TimeRegistry model."""
    list_display = ('user', 'project', 'start_time', 'end_time', 'company')
    list_filter = ('company', 'user', 'start_time')
