import os
import json
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger("kshan.gdrive_oauth")

OAUTH_TOKEN_FILE = settings.BASE_DIR / "gdrive_token.json"
OAUTH_CLIENT_SECRETS_FILE = settings.BASE_DIR / "client_secret.json"

SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

def get_oauth_flow():
    from google_auth_oauthlib.flow import Flow
    if not OAUTH_CLIENT_SECRETS_FILE.exists():
        return None

    flow = Flow.from_client_secrets_file(
        str(OAUTH_CLIENT_SECRETS_FILE),
        scopes=SCOPES,
        redirect_uri="http://127.0.0.1:1212/admin/gdrive/callback/"
    )
    return flow

def get_gdrive_oauth_service():
    """
    Returns an authorized Google Drive service using user's personal OAuth token.
    """
    if not OAUTH_TOKEN_FILE.exists():
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(OAUTH_TOKEN_FILE), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(OAUTH_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        if creds and creds.valid:
            return build('drive', 'v3', credentials=creds, cache_discovery=False)
    except Exception as e:
        logger.error(f"Failed to load OAuth credentials: {e}")

    return None
