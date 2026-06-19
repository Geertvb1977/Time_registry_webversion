import io
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from .models import Company

logger = logging.getLogger(__name__)


class GoogleDriveService:
    def __init__(self, company: Company):
        """
        Initialiseert de Google Drive client op basis van de OAuth2 credentials
        die handmatig door de beheerder van het bedrijf zijn ingevoerd.
        """
        self.company = company
        self.scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/documents",
        ]

        # Haal de gegevens op uit de database
        # (deze worden transparant gedecrypt door de model getters)
        client_id = self.company.google_client_id
        client_secret = self.company.google_client_secret
        token_data = self.company.google_oauth_token

        if not client_id or not client_secret or not token_data:
            raise ValueError(
                "Google Drive integratie is nog niet geconfigureerd"
                "of geautoriseerd voor dit bedrijf."
            )

        # Bouw de Google Credentials structuur
        try:
            self.credentials = Credentials(
                token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token", # nosec B106
                client_id=client_id,
                client_secret=client_secret,
                scopes=self.scopes,
            )

            # Automatisch verversen van de access token als deze verlopen is
            if self.credentials.expired and self.credentials.refresh_token:
                logger.info("Access token is verlopen. Token verversen via refresh_token...")
                self.credentials.refresh(Request())

                # Sla de nieuwe access token op in het Company model
                token_data["access_token"] = self.credentials.token
                self.company.google_oauth_token = token_data
                self.company.save()
                logger.info("Access token met succes vernieuwd en opgeslagen.")

        except Exception as e:
            logger.error(f"Fout tijdens het initialiseren van de Google Credentials: {e}")
            raise

        # Bouw de API client (Drive v3 is de standaard voor bestandsbeheer)
        self.drive_client = build("drive", "v3", credentials=self.credentials)

    def create_folder(
        self, name: str, parent_folder_id: str = None, share_with_members: bool = True
    ) -> str:
        """
        Maakt een nieuwe map aan op de Google Drive van de Admin.
        Omdat de Admin de eigenaar is van de Drive,
        verbruikt dit uitsluitend de opslagquota van de Admin!
        """
        file_metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}

        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]

        try:
            folder = self.drive_client.files().create(body=file_metadata, fields="id").execute()

            folder_id = folder.get("id")

            # Deel de nieuwe map direct met alle company members
            if folder_id and share_with_members:
                self.share_folder_with_company_members(folder_id)

            return folder_id
        except HttpError as error:
            logger.error(f"Fout bij aanmaken van map '{name}': {error}")
            return None

    def share_folder_with_company_members(self, folder_id: str, role: str = "writer") -> None:
        """
        Deelt een map met alle members van de gekoppelde Company.
        """
        members = self.company.members.all()
        for member in members:
            if member.email:
                self.share_file_with_user(file_id=folder_id, email_address=member.email, role=role)
            else:
                logger.warning(
                    f"Lid {member.username} heeft geen e-mailadres geconfigureerd."
                    "Kan map niet delen."
                )

    def create_empty_google_doc(
        self, title: str, file_type: str = "document", parent_folder_id: str = None
    ) -> str:
        """
        Maakt direct een gloednieuw Google Doc of Sheet aan op de Google Drive.
        Kan binnen een specifieke parent folder (bijv. een divisie-map) worden geplaatst.
        """
        mime = "application/vnd.google-apps.document"
        if file_type == "spreadsheet":
            mime = "application/vnd.google-apps.spreadsheet"

        file_metadata = {
            "name": title,
            "mimeType": mime,
        }

        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]

        try:
            file = self.drive_client.files().create(body=file_metadata, fields="id").execute()
            return file.get("id")
        except HttpError as error:
            logger.error(f"Fout bij aanmaken leeg Google Doc: {error}")
            return None

    def upload_and_convert_file(
        self,
        django_file,
        title: str,
        original_mime_type: str,
        convert_to_google: bool = True,
        parent_folder_id: str = None,
    ) -> tuple:
        """
        Uploadt een fysiek bestand naar de Google Drive binnen een optionele parent folder.
        """
        file_metadata = {"name": title}

        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]

        detected_file_type = "binary"

        if convert_to_google:
            if (
                original_mime_type
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                file_metadata["mimeType"] = "application/vnd.google-apps.document"
                detected_file_type = "document"
            elif (
                original_mime_type
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ):
                file_metadata["mimeType"] = "application/vnd.google-apps.spreadsheet"
                detected_file_type = "spreadsheet"

        if original_mime_type == "application/pdf":
            detected_file_type = "pdf"

        media = MediaIoBaseUpload(
            io.BytesIO(django_file.read()), mimetype=original_mime_type, resumable=True
        )

        try:
            file = (
                self.drive_client.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            return file.get("id"), detected_file_type
        except HttpError as error:
            logger.error(f"Fout tijdens uploaden van bestand: {error}")
            return None, None

    def share_file_with_user(self, file_id: str, email_address: str, role: str = "writer") -> bool:
        """
        Deelt het bestand (Doc, Sheet of PDF) met een specifieke gebruiker op Google Drive.
        role: 'writer' (bewerken) of 'reader' (lezen)
        """
        user_permission = {"type": "user", "role": role, "emailAddress": email_address}
        try:
            self.drive_client.permissions().create(
                fileId=file_id,
                body=user_permission,
                fields="id",
                sendNotificationEmail=False,  # Geen spamberichten sturen naar gebruikers!
            ).execute()
            return True
        except HttpError as error:
            logger.error(f"Fout bij delen van bestand {file_id} met {email_address}: {error}")
            return False

    def get_iframe_url(self, file_id: str, file_type: str, mode: str = "edit") -> str:
        """
        Genereert de iframe-vriendelijke embed URL voor een Google Doc of Sheet.
        """
        action = "edit" if mode == "edit" else "preview"
        if file_type == "spreadsheet":
            return f"https://docs.google.com/spreadsheets/d/{file_id}/{action}?rm=minimal"
        return f"https://docs.google.com/document/d/{file_id}/{action}?embedded=true"

    def list_files_from_drive(self, limit: int = 50, folder_id: str = None) -> list:
        """
        Haalt een lijst op van Google Docs en Sheets, optioneel gefilterd op een specifieke map ID.
        """
        try:
            queries = [
                "(mimeType='application/vnd.google-apps.document'"
                "or mimeType='application/vnd.google-apps.spreadsheet')",
                "trashed = false",
            ]
            if folder_id:
                queries.append(f"'{folder_id}' in parents")

            query = " and ".join(queries)

            results = (
                self.drive_client.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name, mimeType, createdTime)",
                    pageSize=limit,
                    orderBy="createdTime desc",
                )
                .execute()
            )
            return results.get("files", [])
        except HttpError as error:
            logger.error(f"Fout bij laden van bestanden van Drive: {error}")
            return []
