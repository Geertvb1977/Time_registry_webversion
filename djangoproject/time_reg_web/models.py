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
    members = models.ManyToManyField(User, related_name='companies', blank=True)
    google_service_account_json = models.JSONField(help_text="Google Service Account JSON voor Google Sheets API", blank=True, null=True)
    google_client_id = models.CharField(max_length=255, blank=True, null=True, help_text="OAuth Client ID")
    google_client_secret = models.CharField(max_length=255, blank=True, null=True, help_text="OAuth Client Secret")
    google_oauth_token = models.JSONField(blank=True, null=True, help_text="OAuth tokens (Access & Refresh)")

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
        Company, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='active_users'
    )
    is_company_admin = models.BooleanField(
        default=False,
        help_text="Kan deze gebruiker andere gebruikers toevoegen aan dit bedrijf?"
    )

    def __str__(self):
        return f"Profiel van {self.user.username}"


# 3. Klantmodel (Koppelt klanten aan bedrijven)
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


# 4. Divisiemodel (Koppelt divisies aan bedrijven)
class Divisies(models.Model):
    """ Model voor divisies binnen een bedrijf """
    divisie_id = models.IntegerField()
    divisie_name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='divisies')
    google_drive_folder_id = models.CharField(max_length=255, blank=True, null=True, help_text="Optioneel: Google Drive map ID voor deze divisie")

    class Meta:
        unique_together = ('company', 'divisie_id')

    def save(self, *args, **kwargs):
        if not self.divisie_id:
            last_id = Divisies.objects.filter(
                company=self.company
            ).aggregate(Max('divisie_id'))['divisie_id__max']
            self.divisie_id = (last_id or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.divisie_name


# 5. Projectmodel (Koppelt projecten aan bedrijven en klanten)
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


# 6. Tijdregistratiemodel (Koppelt tijdregistraties aan bedrijven, gebruikers, projecten en divisies)
class TimeRegistry(models.Model):
    """ Model voor tijdregistraties binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='time_registrys')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_registrys')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='time_registrys')
    divisie = models.ForeignKey(Divisies, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_registrys')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    Todo = models.ForeignKey('Todo', on_delete=models.SET_NULL, null=True, blank=True, related_name='time_registrys')

    def __str__(self):
        return f"{self.user.username} - {self.project.project_name} - {self.start_time}"


# 7. Mijlpaalmodel (Koppelt mijlpalen aan bedrijven, projecten en divisies)
class Milstones(models.Model):
    """ Model voor mijlpalen binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='milstones')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milstones')
    divisie = models.ForeignKey(Divisies, on_delete=models.SET_NULL, null=True, blank=True, related_name='milstones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# 8. Taakmodel (Koppelt taken aan bedrijven, gebruikers, klanten, projecten en divisies)
class Todo(models.Model):
    """ Model voor taken binnen een bedrijf """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='todos')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todos')
    customer_id = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='todos')
    project_id = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='todos')
    divisie = models.ForeignKey(Divisies, on_delete=models.SET_NULL, null=True, blank=True, related_name='todos')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.IntegerField(default=3)  # 1 = Hoog, 2 = Midden, 3 = Laag
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    milestone = models.ForeignKey(Milstones, on_delete=models.SET_NULL, null=True, blank=True, related_name='todos')

    def __str__(self):
        return self.title


# 9. Google Sheets Configuratiemodel (Koppelt Google Sheets configuraties aan bedrijven)
class GoogleDocument(models.Model):
    """
    Slaat de koppeling op bedrijven en hun Google Sheets configuraties.
    """
    FILE_TYPES = (
        ('document', 'Google Doc (Bewerkbaar)'),
        ('spreadsheet', 'Google Sheet (Bewerkbaar)'),
        ('pdf', 'PDF (Alleen lezen)'),
        ('binary', 'Overig bestand (Enkel downloaden)'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    google_file_id = models.CharField(
        max_length=255, 
        unique=True, 
        help_text="De unieke ID van het bestand op Google Drive"
    )
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='document')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_file_type_display()})"


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
