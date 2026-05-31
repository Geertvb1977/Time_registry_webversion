
import io
from django.core.files.uploadedfile import UploadedFile

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

from .models import Company


class GoogleDriveService:
    def __init__(self, company: Company):
        """
        Initialiseert de Google Drive client met de credentials van het specifieke bedrijf.
        """
        self.company = company
        self.scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/documents'
        ]
        
        # Laad credentials rechtstreeks vanuit de JSON in de database
        self.credentials = service_account.Credentials.from_service_account_info(
            self.company.google_service_account_json,
            scopes=self.scopes
        )
        
        # Bouw de Drive API client (Drive v3 is de standaard voor bestandsbeheer)
        self.drive_client = build('drive', 'v3', credentials=self.credentials)

    def create_empty_google_doc(self, title: str) -> str:
        """
        Maakt direct een gloednieuw, leeg Google Doc aan op Google Drive.
        Returnt de unieke google_file_id.
        """
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'  # Dit forceert het Google Doc formaat
        }
        try:
            file = self.drive_client.files().create(
                body=file_metadata, 
                fields='id'
            ).execute()
            return file.get('id')
        except HttpError as error:
            print(f"Fout bij aanmaken leeg Google Doc: {error}")
            return None

    def upload_and_convert_file(self, django_file, title: str, original_mime_type: str, convert_to_google: bool = True) -> tuple:
        """
        Uploadt een fysiek bestand (Word, Excel, PDF) naar Google Drive.
        
        Parameters:
        - django_file: Het geüploade bestandsobject (bijv. request.FILES['file'])
        - title: De gewenste naam van het bestand op Google Drive
        - original_mime_type: Het oorspronkelijke bestandstype (bijv. 'application/pdf')
        - convert_to_google: Indien True, converteert Google Word/Excel automatisch naar Docs/Sheets.
        
        Returnt:
        - (google_file_id, detected_file_type)
        """
        file_metadata = {
            'name': title
        }
        
        detected_file_type = 'binary'

        # Als conversie is ingeschakeld, bepalen we het doel-MIME-type van Google
        if convert_to_google:
            # Word (.docx) -> Google Doc
            if original_mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                file_metadata['mimeType'] = 'application/vnd.google-apps.document'
                detected_file_type = 'document'
            # Excel (.xlsx) -> Google Sheet
            elif original_mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                file_metadata['mimeType'] = 'application/vnd.google-apps.spreadsheet'
                detected_file_type = 'spreadsheet'
        
        # Als het een PDF is, behouden we het als PDF (dit kan niet geconverteerd worden naar een live Doc)
        if original_mime_type == 'application/pdf':
            detected_file_type = 'pdf'

        # Lees het bestand in het geheugen in voor de upload helper
        media = MediaIoBaseUpload(
            io.BytesIO(django_file.read()), 
            mimetype=original_mime_type, 
            resumable=True
        )
        
        try:
            file = self.drive_client.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id'), detected_file_type
        except HttpError as error:
            print(f"Fout tijdens uploaden/converteren van bestand: {error}")
            return None, None

    def share_file_with_user(self, file_id: str, email_address: str, role: str = 'writer') -> bool:
        """
        Deelt het bestand (ongeacht of het een Doc, Sheet of PDF is) met de browser-gebruiker.
        role: 'writer' (bewerken) of 'reader' (lezen)
        """
        user_permission = {
            'type': 'user',
            'role': role,
            'emailAddress': email_address
        }
        try:
            self.drive_client.permissions().create(
                fileId=file_id,
                body=user_permission,
                fields='id'
            ).execute()
            return True
        except HttpError as error:
            print(f"Fout bij delen van bestand: {error}")
            return False