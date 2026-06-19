"""
Building multi-tenant support into the time registration web application.
Each company (tenant) has its own set of
users, customers, projects, and time entries.
"""

import json
import logging
import os

# We gebruiken de cryptography bibliotheek voor veilige opslag van de API credentials
from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# Helper-klasse voor encryptie van gevoelige API credentials in de database
class CredentialEncryptor:
    @staticmethod
    def get_cipher():
        """
        Haalt de encryptiesleutel op uit de omgevingsvariabelen.
        Als deze niet bestaat, genereren we een tijdelijke (niet aanbevolen voor productie!).
        Voeg 'FIELD_ENCRYPTION_KEY' toe aan je .env of Docker compose.
        """
        key = os.environ.get("FIELD_ENCRYPTION_KEY")
        if not key:
            logger.warning(
                "FIELD_ENCRYPTION_KEY omgevingsvariabele ontbreekt! "
                "Tijdelijke fallback sleutel wordt gebruikt. "
                "Credentials gaan verloren bij herstart!"
            )
            # Fallback sleutel voor lokale ontwikkeling (veilig gecodeerd)
            key = "django_local_dev_secret_encryption_key_12345="
        try:
            return Fernet(key.encode())
        except Exception as e:
            logger.error(f"Fout bij initialiseren van Fernet cipher: {e}")
            raise

    @classmethod
    def encrypt(cls, value: str) -> str:
        if not value:
            return ""
        cipher = cls.get_cipher()
        return cipher.encrypt(value.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_value: str) -> str:
        if not encrypted_value:
            return ""
        if not encrypted_value.startswith("gAAAA"):
            # Waarde is niet versleuteld (migratiefase)
            return encrypted_value
        cipher = cls.get_cipher()
        return cipher.decrypt(encrypted_value.encode()).decode()


class Company(models.Model):
    """Model voor een bedrijf (tenant)"""

    name = models.CharField(max_length=100, verbose_name="Bedrijfsnaam")
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(User, related_name="companies", blank=True)

    # NIEUW: Google OAuth2 handmatige credentials per bedrijf
    google_client_id = models.CharField(
        max_length=255, blank=True, null=True, help_text="Google OAuth2 Client ID van het bedrijf"
    )
    # Gevoelige velden slaan we versleuteld op in de database
    _google_client_secret_encrypted = models.CharField(
        db_column="google_client_secret",
        max_length=512,
        blank=True,
        null=True,
        help_text="Google OAuth2 Client Secret (Versleuteld)",
    )
    _google_oauth_token_encrypted = models.TextField(
        db_column="google_oauth_token",
        blank=True,
        null=True,
        help_text="OAuth2 Tokens JSON-structuur (Versleuteld)",
    )

    # Custom properties om encryptie transparant te maken bij het opvragen/opslaan
    @property
    def google_client_secret(self):
        return CredentialEncryptor.decrypt(self._google_client_secret_encrypted)

    @google_client_secret.setter
    def google_client_secret(self, value):
        self._google_client_secret_encrypted = CredentialEncryptor.encrypt(value)

    @property
    def google_oauth_token(self):
        decrypted = CredentialEncryptor.decrypt(self._google_oauth_token_encrypted)
        if decrypted:
            try:
                return json.loads(decrypted)
            except json.JSONDecodeError:
                return {}
        return {}

    @google_oauth_token.setter
    def google_oauth_token(self, value):
        if value:
            json_str = json.dumps(value)
            self._google_oauth_token_encrypted = CredentialEncryptor.encrypt(json_str)
        else:
            self._google_oauth_token_encrypted = None

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Bedrijf"
        verbose_name_plural = "Bedrijven"


class UserProfile(models.Model):
    """Model voor gebruikersprofielen die bedrijven koppelen aan gebruikers"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="active_users"
    )
    is_company_admin = models.BooleanField(
        default=False, help_text="Kan deze gebruiker andere gebruikers toevoegen aan dit bedrijf?"
    )

    def __str__(self):
        return f"Profiel van {self.user.username}"


class Customer(models.Model):
    """Model voor klanten binnen een bedrijf"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="customers")
    customer_id = models.IntegerField()
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()

    class Meta:
        unique_together = ("company", "customer_id")

    def save(self, *args, **kwargs):
        if not self.customer_id:
            last_id = Customer.objects.filter(company=self.company).aggregate(Max("customer_id"))[
                "customer_id__max"
            ]
            self.customer_id = (last_id or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.customer_name


class Divisies(models.Model):
    """Model voor divisies binnen een bedrijf"""

    divisie_id = models.IntegerField()
    divisie_name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="divisies")
    google_drive_folder_id = models.CharField(
        max_length=255, blank=True, null=True, help_text="Google Drive map ID voor deze divisie"
    )

    class Meta:
        unique_together = ("company", "divisie_id")

    def save(self, *args, **kwargs):
        if not self.divisie_id:
            last_id = Divisies.objects.filter(company=self.company).aggregate(Max("divisie_id"))[
                "divisie_id__max"
            ]
            self.divisie_id = (last_id or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.divisie_name


class Project(models.Model):
    """Model voor projecten binnen een bedrijf"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="projects")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="projects")
    project_id = models.IntegerField()
    project_name = models.CharField(max_length=255)
    project_description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "project_id")

    def save(self, *args, **kwargs):
        if not self.project_id:
            last_id = Project.objects.filter(company=self.company).aggregate(Max("project_id"))[
                "project_id__max"
            ]
            self.project_id = (last_id or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.project_name


class TimeRegistry(models.Model):
    """Model voor tijdregistraties binnen een bedrijf"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="time_registrys")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="time_registrys")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="time_registrys")
    divisie = models.ForeignKey(
        Divisies, on_delete=models.SET_NULL, null=True, blank=True, related_name="time_registrys"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    Todo = models.ForeignKey(
        "Todo", on_delete=models.SET_NULL, null=True, blank=True, related_name="time_registrys"
    )

    def __str__(self):
        return f"{self.user.username} - {self.project.project_name} - {self.start_time}"


class Milstones(models.Model):
    """Model voor mijlpalen binnen een bedrijf"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="milstones")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milstones")
    divisie = models.ForeignKey(
        Divisies, on_delete=models.SET_NULL, null=True, blank=True, related_name="milstones"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Todo(models.Model):
    """Model voor taken binnen een bedrijf"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="todos")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="todos")
    customer_id = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="todos")
    project_id = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="todos")
    divisie = models.ForeignKey(
        Divisies, on_delete=models.SET_NULL, null=True, blank=True, related_name="todos"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.IntegerField(default=3)  # 1 = Hoog, 2 = Midden, 3 = Laag
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    milestone = models.ForeignKey(
        Milstones, on_delete=models.SET_NULL, null=True, blank=True, related_name="todos"
    )

    def __str__(self):
        return self.title


class GoogleDocument(models.Model):
    """Slaat de koppeling op tussen bedrijven en hun Google documenten"""

    FILE_TYPES = (
        ("document", "Google Doc (Bewerkbaar)"),
        ("spreadsheet", "Google Sheet (Bewerkbaar)"),
        ("pdf", "PDF (Alleen lezen)"),
        ("binary", "Overig bestand (Enkel downloaden)"),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    google_file_id = models.CharField(
        max_length=255, unique=True, help_text="De unieke ID van het bestand op Google Drive"
    )
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default="document")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_file_type_display()})"


# Simple API token model for project-level customer access
class APIToken(models.Model):
    """API token to allow external customers to fetch project status.

    Tokens are generated by a company employee and emailed to the customer.
    They can be single-use or reusable and may have an expiry.
    """

    key = models.CharField(max_length=128, unique=True, db_index=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="api_tokens")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="api_tokens")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    single_use = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"APIToken {self.key} for {self.project}"

    @staticmethod
    def generate_key():
        import secrets

        return secrets.token_urlsafe(32)

    def mark_used(self):
        if self.single_use:
            self.is_active = False
            self.save()


# Record API token usage events for auditing
class APITokenUsage(models.Model):
    token = models.ForeignKey(APIToken, on_delete=models.CASCADE, related_name="usages")
    used_at = models.DateTimeField(auto_now_add=True)
    remote_ip = models.CharField(max_length=64, blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True, null=True)

    def __str__(self):
        return f"Usage of {self.token.key} at {self.used_at.isoformat()}"


# --- SIGNALS ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
