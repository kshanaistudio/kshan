import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kshan_project.settings')
django.setup()

from gallery.services.gdrive_service import get_gdrive_service

def inspect_folder(folder_id):
    s = get_gdrive_service()
    res = s.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    print("Files found in folder:", res.get("files", []))

if __name__ == "__main__":
    print("--- Parent folder ---")
    inspect_folder('1jYID7X5Uu-6AZFw21E14gPG_yqZnKcvn')
    print("--- Subfolder Wedding ---")
    inspect_folder('1JeirrRhoS9Csyb_XC3UFOORCxJ5yfGpF')
