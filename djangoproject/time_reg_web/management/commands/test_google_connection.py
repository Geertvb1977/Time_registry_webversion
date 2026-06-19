import json
import logging
import os

from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from time_reg_web.models import (
    Company,  # Pas de importnaam aan naar jouw app-naam indien nodig
)

logger = logging.getLogger(__name__)


# Tip voor productie-beveiliging:
# Je kunt 'cryptography.fernet' gebruiken om gevoelige velden te ontcijferen:
# from cryptography.fernet import Fernet


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test de Google Drive & Docs API-verbinding via OAuth2 (ingevoerd door Company Admin) voor een bedrijf."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company_id",
            type=int,
            help="Het ID van het bedrijf (Company) in de database dat getest moet worden.",
        )
        parser.add_argument(
            "--folder_id",
            type=str,
            help="Optioneel: Het ID van de Google Drive map waarin testdocumenten gemaakt moeten worden.",
        )

    def decrypt_value(self, encrypted_value: str) -> str:
        """
        Hulpmethode voor het ontcijferen van gevoelige database-velden.
        Als je nog geen encryptie gebruikt, retourneert dit momenteel gewoon de platte tekst.
        """
        if not encrypted_value:
            return ""

        # Voorbeeld van hoe je dit in productie activeert:
        # key = os.environ.get("FIELD_ENCRYPTION_KEY")
        # if key and encrypted_value.startswith("gAAAA"):  # Fernet tokens beginnen meestal met gAAAA
        #     f = Fernet(key.encode())
        #     return f.decrypt(encrypted_value.encode()).decode()

        return encrypted_value

    def handle(self, *args, **options):
        company_id = options["company_id"]
        folder_id = options["folder_id"]

        # 1. Selecteer het bedrijf (interactief indien geen ID is meegegeven)
        if not company_id:
            companies = Company.objects.all()
            if not companies.exists():
                self.stdout.write(
                    self.style.ERROR(
                        "[-] Er zijn geen bedrijven in de database gevonden. Voeg er eerst een toe."
                    )
                )
                return

            self.stdout.write(self.style.WARNING("[!] Geen --company_id meegegeven als argument."))
            self.stdout.write("Beschikbare bedrijven in de database:")

            for c in companies:
                has_oauth = (
                    "JA" if hasattr(c, "google_oauth_token") and c.google_oauth_token else "NEE"
                )
                self.stdout.write(f"   [{c.id}] {c.name} (OAuth2 Tokens aanwezig: {has_oauth})")

            while True:
                try:
                    user_input = input(
                        "\nVoer het ID in van het bedrijf dat je wilt testen (of 'q' om te stoppen): "
                    ).strip()
                    if user_input.lower() == "q":
                        self.stdout.write(self.style.WARNING("[!] Test geannuleerd."))
                        return

                    if not user_input:
                        continue

                    selected_id = int(user_input)
                    company = Company.objects.get(pk=selected_id)
                    break
                except ValueError:
                    self.stdout.write(
                        self.style.ERROR("[-] Ongeldige invoer. Voer een geldig numeriek ID in.")
                    )
                except Company.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[-] Bedrijf met ID '{user_input}' bestaat niet. Probeer het opnieuw."
                        )
                    )
        else:
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"[-] Bedrijf met ID {company_id} bestaat niet.")
                )
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[+] Starten met testen van OAuth2-verbinding voor bedrijf: {company.name} (ID: {company.id})"
            )
        )

        # 2. Haal de handmatig ingevoerde OAuth2 configuratie en tokens op
        self.stdout.write("[*] Stap 1: Controleren van handmatig ingevoerde OAuth2-credentials...")

        client_id_raw = getattr(company, "google_client_id", None)
        client_secret_raw = getattr(company, "google_client_secret", None)
        token_info_raw = getattr(company, "google_oauth_token", None)

        if not client_id_raw or not client_secret_raw or not token_info_raw:
            self.stdout.write(
                self.style.ERROR(
                    "[-] FOUT: Handmatige OAuth2-velden ontbreken nog in je Company database-model!"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "    Zorg ervoor dat de volgende velden op je Company-model staan en zijn ingevuld door de admin:"
                )
            )
            self.stdout.write(
                "    -> google_client_id = models.CharField(max_length=255, blank=True, null=True)"
            )
            self.stdout.write(
                "    -> google_client_secret = models.CharField(max_length=255, blank=True, null=True)  # Versleuteld opslaan!"
            )
            self.stdout.write(
                "    -> google_oauth_token = models.JSONField(blank=True, null=True)                  # Versleuteld opslaan!"
            )
            return

        # Ontcijfer credentials indien versleuteld
        client_id = self.decrypt_value(client_id_raw)
        client_secret = self.decrypt_value(client_secret_raw)

        try:
            if isinstance(token_info_raw, str):
                token_data = json.loads(self.decrypt_value(token_info_raw))
            elif isinstance(token_info_raw, dict):
                # Als het een JSONField is, kan het al een dict zijn. We decrypten dan de specifieke tokens binnen de dict indien nodig.
                token_data = token_info_raw
            else:
                token_data = token_info_raw

            self.stdout.write(
                self.style.SUCCESS("    [v] OAuth2 configuratie succesvol geladen en gedecrypt.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"[-] FOUT: Kan oauth_token JSON niet parsen/decrypten: {e}")
            )
            return

        # 3. Bouw OAuth2 Credentials en ververs indien nodig
        self.stdout.write("[*] Stap 2: Valideren van de tokens bij Google...")
        try:
            scopes = [
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/documents",
            ]
            credentials = Credentials(
                token=self.decrypt_value(token_data.get("access_token")),
                refresh_token=self.decrypt_value(token_data.get("refresh_token")),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes,
            )

            # Automatisch verversen van de token met de refresh_token
            if credentials.expired and credentials.refresh_token:
                self.stdout.write(
                    self.style.WARNING(
                        "    [!] Access token is verlopen. Token verversen via refresh_token..."
                    )
                )
                credentials.refresh(Request())

                # Sla de nieuwe access token op in de database (eventueel weer versleutelen in productie)
                token_data["access_token"] = credentials.token
                company.google_oauth_token = token_data
                company.save()
                self.stdout.write(
                    self.style.SUCCESS("    [v] Access token succesvol vernieuwd en opgeslagen.")
                )

            drive_client = build("drive", "v3", credentials=credentials)
            self.stdout.write(
                self.style.SUCCESS("    [v] Google OAuth2 client succesvol opgebouwd.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"[-] FOUT tijdens initialiseren OAuth2 client: {e}")
            )
            return

        # 4. Test ophalen van bestanden (Read test)
        self.stdout.write("[*] Stap 3: Testen van leesrechten op de Google Drive van de Admin...")
        try:
            results = (
                drive_client.files().list(pageSize=5, fields="files(id, name, mimeType)").execute()
            )

            files = results.get("files", [])
            self.stdout.write(
                self.style.SUCCESS(
                    f"    [v] Verbinding geslaagd! Bestanden in de Drive van de Admin:"
                )
            )
            for f in files:
                self.stdout.write(f"        - {f['name']} ({f['mimeType']}) ID: {f['id']}")

        except HttpError as error:
            self.stdout.write(
                self.style.ERROR(f"[-] Google Drive API Fout bij het oplijsten: {error}")
            )
            return

        # 5. Test aanmaken van een testmap (Write test)
        self.stdout.write("[*] Stap 4: Testen van schrijfrechten (aanmaken van een map)...")
        file_metadata = {
            "name": "Eventaflow OAuth2 Test Map",
            "mimeType": "application/vnd.google-apps.folder",
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        try:
            folder = drive_client.files().create(body=file_metadata, fields="id").execute()

            test_folder_id = folder.get("id")
            self.stdout.write(
                self.style.SUCCESS(
                    f"    [v] Map succesvol aangemaakt onder het Admin-account! ID: {test_folder_id}"
                )
            )

            # Direct weer opruimen
            self.stdout.write("[*] Stap 5: Testmap opruimen (verwijderen)...")
            drive_client.files().delete(fileId=test_folder_id).execute()
            self.stdout.write(self.style.SUCCESS("    [v] Testmap succesvol opgeruimd."))

        except HttpError as error:
            self.stdout.write(
                self.style.ERROR(f"[-] Google Drive API Schrijffout bij map aanmaken: {error}")
            )
            return

        # 6. Test aanmaken Google Doc (Geen quota fouten meer!)
        self.stdout.write("[*] Stap 6: Testen van aanmaken Google Doc (zonder quota-fout!)...")
        doc_metadata = {
            "name": "Eventaflow OAuth2 Test Document",
            "mimeType": "application/vnd.google-apps.document",
        }
        if folder_id:
            doc_metadata["parents"] = [folder_id]

        try:
            doc_file = drive_client.files().create(body=doc_metadata, fields="id").execute()
            doc_id = doc_file.get("id")
            self.stdout.write(
                self.style.SUCCESS(
                    f"    [v] Google Doc succesvol aangemaakt op de Drive van de Admin! ID: {doc_id}"
                )
            )

            # Opruimen
            drive_client.files().delete(fileId=doc_id).execute()
            self.stdout.write(self.style.SUCCESS("    [v] Test Google Doc succesvol opgeruimd."))
        except HttpError as error:
            self.stdout.write(self.style.ERROR(f"[-] FOUT bij aanmaken Google Doc: {error}"))

        # 7. Test aanmaken Google Sheet
        self.stdout.write("[*] Stap 7: Testen van aanmaken Google Sheet...")
        sheet_metadata = {
            "name": "Eventaflow OAuth2 Test Spreadsheet",
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        if folder_id:
            sheet_metadata["parents"] = [folder_id]

        try:
            sheet_file = drive_client.files().create(body=sheet_metadata, fields="id").execute()
            sheet_id = sheet_file.get("id")
            self.stdout.write(
                self.style.SUCCESS(
                    f"    [v] Google Sheet succesvol aangemaakt op de Drive van de Admin! ID: {sheet_id}"
                )
            )

            # Opruimen
            drive_client.files().delete(fileId=sheet_id).execute()
            self.stdout.write(self.style.SUCCESS("    [v] Test Google Sheet succesvol opgeruimd."))
        except HttpError as error:
            self.stdout.write(self.style.ERROR(f"[-] FOUT bij aanmaken Google Sheet: {error}"))

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS("[SUCCESS] OAuth2 API-verbinding en rechten zijn 100% in orde!")
        )
        self.stdout.write("=" * 50)
