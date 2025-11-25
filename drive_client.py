"""
Google Drive API client for UXR CUJ Analysis
Handles OAuth authentication and Drive operations
"""

import os
import io
import streamlit as st
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import time
import random


class DriveAPIError(Exception):
    """Custom exception for Drive API errors"""
    pass


class DriveClient:
    """Google Drive API client with OAuth 2.0 authentication"""

    # OAuth scopes
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',  # Browse and download
        'https://www.googleapis.com/auth/drive.file'       # Upload files
    ]

    # Video MIME types to filter
    VIDEO_MIME_TYPES = [
        'video/mp4',
        'video/quicktime',
        'video/x-msvideo',
        'video/webm',
        'video/x-matroska',
        'video/x-flv'
    ]

    def __init__(self):
        """Initialize Drive client"""
        self.service = None

    @staticmethod
    def get_redirect_uri() -> str:
        """Get appropriate redirect URI based on environment"""
        # Check if running in Streamlit Cloud
        if os.getenv('STREAMLIT_RUNTIME_ENV') == 'cloud':
            return st.secrets.get("google_drive", {}).get("redirect_uri_prod", "http://localhost:8501")
        return st.secrets.get("google_drive", {}).get("redirect_uri", "http://localhost:8501")

    @staticmethod
    def create_oauth_flow() -> Flow:
        """Create OAuth flow from secrets"""
        client_config = {
            "web": {
                "client_id": st.secrets["google_drive"]["client_id"],
                "client_secret": st.secrets["google_drive"]["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [DriveClient.get_redirect_uri()]
            }
        }

        return Flow.from_client_config(
            client_config,
            scopes=DriveClient.SCOPES,
            redirect_uri=DriveClient.get_redirect_uri()
        )

    @staticmethod
    def credentials_to_dict(credentials: Credentials) -> Dict:
        """Convert credentials object to dictionary for session state"""
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

    @staticmethod
    def dict_to_credentials(creds_dict: Dict) -> Credentials:
        """Convert dictionary to credentials object"""
        return Credentials(**creds_dict)

    @staticmethod
    def get_auth_url() -> Tuple[Flow, str]:
        """Get authorization URL for OAuth flow"""
        flow = DriveClient.create_oauth_flow()
        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline',  # Request refresh token
            include_granted_scopes='true'
        )
        return flow, auth_url

    @staticmethod
    def exchange_code_for_token(code: str) -> Dict:
        """Exchange authorization code for access token"""
        try:
            flow = DriveClient.create_oauth_flow()
            flow.fetch_token(code=code)
            return DriveClient.credentials_to_dict(flow.credentials)
        except Exception as e:
            raise DriveAPIError(f"Failed to exchange code for token: {str(e)}")

    @staticmethod
    def refresh_credentials(creds_dict: Dict) -> Dict:
        """Refresh expired credentials"""
        credentials = DriveClient.dict_to_credentials(creds_dict)

        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                return DriveClient.credentials_to_dict(credentials)
            except Exception as e:
                raise DriveAPIError(f"Failed to refresh credentials: {str(e)}")

        return creds_dict

    def initialize_service(self, creds_dict: Dict):
        """Initialize Drive service with credentials"""
        try:
            # Refresh if needed
            creds_dict = self.refresh_credentials(creds_dict)
            credentials = self.dict_to_credentials(creds_dict)

            # Build service
            self.service = build('drive', 'v3', credentials=credentials)

            # Update session state with refreshed credentials
            if 'drive_credentials' in st.session_state:
                st.session_state.drive_credentials = creds_dict

        except Exception as e:
            raise DriveAPIError(f"Failed to initialize Drive service: {str(e)}")

    @staticmethod
    def exponential_backoff_retry(func, max_retries=5):
        """Execute function with exponential backoff retry logic"""
        retry_count = 0

        while retry_count < max_retries:
            try:
                return func()

            except HttpError as error:
                if error.resp.status in [403, 429]:
                    # Rate limit exceeded
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise DriveAPIError(f"Rate limit exceeded after {max_retries} retries")

                    wait_time = min((2 ** retry_count) + random.random(), 64)
                    time.sleep(wait_time)

                elif error.resp.status in [500, 502, 503, 504]:
                    # Server errors
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise DriveAPIError(f"Server error after {max_retries} retries")

                    wait_time = min((2 ** retry_count), 32)
                    time.sleep(wait_time)

                else:
                    # Non-retryable error
                    raise DriveAPIError(f"Drive API error: {error}")

        raise DriveAPIError(f"Max retries ({max_retries}) exceeded")

    def list_files(self, page_size: int = 100, query: Optional[str] = None,
                   page_token: Optional[str] = None) -> Dict:
        """
        List files in Drive with optional filtering

        Args:
            page_size: Number of files to return (max 1000)
            query: Query string for filtering (e.g., "mimeType contains 'video/'")
            page_token: Token for pagination

        Returns:
            Dictionary with 'files' list and optional 'nextPageToken'
        """
        if not self.service:
            raise DriveAPIError("Drive service not initialized")

        def _list():
            params = {
                'pageSize': min(page_size, 1000),
                'fields': 'nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)',
                'orderBy': 'modifiedTime desc'
            }

            if query:
                params['q'] = query

            if page_token:
                params['pageToken'] = page_token

            return self.service.files().list(**params).execute()

        try:
            return self.exponential_backoff_retry(_list)
        except Exception as e:
            raise DriveAPIError(f"Failed to list files: {str(e)}")

    def list_video_files(self, page_size: int = 50) -> List[Dict]:
        """List only video files from Drive"""
        query = " or ".join([f"mimeType='{mime}'" for mime in self.VIDEO_MIME_TYPES])

        try:
            results = self.list_files(page_size=page_size, query=query)
            return results.get('files', [])
        except Exception as e:
            raise DriveAPIError(f"Failed to list video files: {str(e)}")

    def download_file(self, file_id: str, destination_path: str,
                      progress_callback=None) -> bool:
        """
        Download file from Drive to local storage

        Args:
            file_id: Google Drive file ID
            destination_path: Local path to save file
            progress_callback: Optional callback function(progress_percent)

        Returns:
            True if successful
        """
        if not self.service:
            raise DriveAPIError("Drive service not initialized")

        try:
            # Get file metadata
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields="name, size"
            ).execute()

            file_name = file_metadata.get('name', 'unknown')
            file_size = int(file_metadata.get('size', 0))

            # Create request
            request = self.service.files().get_media(fileId=file_id)

            # Download with progress
            with open(destination_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request, chunksize=10*1024*1024)

                done = False
                while not done:
                    status, done = downloader.next_chunk()

                    if status and progress_callback:
                        progress = int(status.progress() * 100)
                        progress_callback(progress)

            return True

        except HttpError as error:
            raise DriveAPIError(f"Failed to download file: {error}")
        except Exception as e:
            raise DriveAPIError(f"Failed to download file: {str(e)}")

    def upload_file(self, file_path: str, file_name: Optional[str] = None,
                    folder_id: Optional[str] = None,
                    progress_callback=None) -> Dict:
        """
        Upload file to Drive

        Args:
            file_path: Local path to file
            file_name: Optional custom name for Drive
            folder_id: Optional Drive folder ID
            progress_callback: Optional callback function(progress_percent)

        Returns:
            Dictionary with file metadata (id, name, webViewLink)
        """
        if not self.service:
            raise DriveAPIError("Drive service not initialized")

        if not os.path.exists(file_path):
            raise DriveAPIError(f"File not found: {file_path}")

        try:
            # Prepare metadata
            file_metadata = {
                'name': file_name or os.path.basename(file_path)
            }

            if folder_id:
                file_metadata['parents'] = [folder_id]

            # Determine MIME type
            if file_path.endswith('.csv'):
                mime_type = 'text/csv'
            elif file_path.endswith('.json'):
                mime_type = 'application/json'
            else:
                mime_type = 'application/octet-stream'

            # Get file size
            file_size = os.path.getsize(file_path)

            # Use resumable upload for files > 5MB
            if file_size > 5 * 1024 * 1024:
                media = MediaFileUpload(
                    file_path,
                    mimetype=mime_type,
                    resumable=True,
                    chunksize=5*1024*1024
                )

                request = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, webViewLink'
                )

                response = None
                while response is None:
                    try:
                        status, response = request.next_chunk()
                        if status and progress_callback:
                            progress = int(status.progress() * 100)
                            progress_callback(progress)
                    except HttpError as error:
                        if error.resp.status in [500, 502, 503, 504]:
                            time.sleep(2)
                        else:
                            raise

                return response

            else:
                # Simple upload for small files
                media = MediaFileUpload(file_path, mimetype=mime_type)

                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, webViewLink'
                ).execute()

                if progress_callback:
                    progress_callback(100)

                return file

        except HttpError as error:
            raise DriveAPIError(f"Failed to upload file: {error}")
        except Exception as e:
            raise DriveAPIError(f"Failed to upload file: {str(e)}")

    def get_file_metadata(self, file_id: str) -> Dict:
        """Get metadata for a specific file"""
        if not self.service:
            raise DriveAPIError("Drive service not initialized")

        try:
            return self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime, webViewLink, videoMediaMetadata"
            ).execute()
        except HttpError as error:
            raise DriveAPIError(f"Failed to get file metadata: {error}")


# Helper functions for Streamlit integration

def is_drive_authenticated() -> bool:
    """Check if user is authenticated with Drive"""
    return 'drive_credentials' in st.session_state


def get_drive_client() -> Optional[DriveClient]:
    """Get initialized Drive client or None if not authenticated"""
    if not is_drive_authenticated():
        return None

    try:
        client = DriveClient()
        client.initialize_service(st.session_state.drive_credentials)
        return client
    except Exception as e:
        st.error(f"Failed to initialize Drive client: {e}")
        return None


def handle_drive_oauth_callback():
    """Handle OAuth callback from Google Drive"""
    query_params = st.query_params

    if 'code' in query_params:
        try:
            # Exchange code for token
            credentials = DriveClient.exchange_code_for_token(query_params['code'])

            # Store in session state
            st.session_state.drive_credentials = credentials

            # Clear query params
            st.query_params.clear()
            st.rerun()

        except Exception as e:
            st.error(f"Drive authentication failed: {e}")
            return False

    return True


def logout_drive():
    """Logout from Drive (clear credentials)"""
    if 'drive_credentials' in st.session_state:
        del st.session_state.drive_credentials
