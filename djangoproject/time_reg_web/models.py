"""
Building multi-tenant support into the time registration web application.
Each company (tenant) has its own set of
users, customers, projects, and time entries.
"""
from django.db import models
from django.db.models import Max
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# 1. Het Bedrijf (De 'Tenant')
class Company(models.Model):
    """ Model voor een bedrijf (tenant) """
    name = models.CharField(max_length=100, verbose_name="Bedrijfsnaam")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        """Meta informatie voor het bedrijf."""
        verbose_name = "Bedrijf"
        verbose_name_plural = "Bedrijven"


# 2. Het Gebruikersprofiel (Koppelt User aan Company)
class UserProfile(models.Model):
    """ Model voor gebruikersprofielen die bedrijven koppelen aan gebruikers """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile'
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='employees',
        null=True, blank=True
    )
    is_company_admin = models.BooleanField(
        default=False,
        help_text="Kan deze gebruiker andere gebruikers toevoegen aan dit bedrijf?"
    )

    def __str__(self):
        return f"{self.user.username} - {self.company.name if self.company else 'Geen bedrijf'}"

# 3. Bestaande modellen aanpassen (Klant, Project, etc.)

# company = models.ForeignKey(Company, on_delete=models.CASCADE)


class Customer(models.Model):
    """ Model voor klanten binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customers')
    customer_id = models.IntegerField()
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()

    class Meta:
        unique_together = ('company', 'customer_id')

    def save(self, *args, **kwargs):
        if not self.customer_id:
            last_id = Customer.objects.filter(
                company=self.company
            ).aggregate(Max('customer_id'))['customer_id__max']
            self.customer_id = (last_id or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.customer_name


class Project(models.Model):
    """ Model voor projecten binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='projects')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='projects')
    project_id = models.IntegerField()
    project_name = models.CharField(max_length=255)
    project_description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'project_id')

    def save(self, *args, **kwargs):
        if not self.project_id:
            last_id = Project.objects.filter(
                company=self.company
            ).aggregate(Max('project_id'))['project_id__max']
            self.project_id = (last_id or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.project_name


class TimeRegistry(models.Model):
    """ Model voor tijdregistraties binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='time_registrys')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_registrys')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='time_registrys')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.project.project_name} - {self.start_time}"


class Todo(models.Model):
    """ Model voor taken binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='todos')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todos')
    customer_id = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='todos')
    project_id = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='todos')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.IntegerField(default=3)  # 1 = Hoog, 2 = Midden, 3 = Laag
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Milstones(models.Model):
    """ Model voor mijlpalen binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='milstones')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milstones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# --- SIGNALS ---
# Deze zorgen ervoor dat als je een User aanmaakt in de admin, er direct een profiel komt.

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """ Maakt een UserProfile aan wanneer een nieuwe User wordt aangemaakt. """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """ Slaat het UserProfile op wanneer de User wordt opgeslagen. """
    instance.profile.save()
