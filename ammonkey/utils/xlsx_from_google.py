"""
Automated download + dispatching for fusillo notes, from google drive.
just click run whenever you feel like updating local note copies.
** IF PROMPTED FOR GOOGLE ACCOUNT: ** select pi*******dlc@gmail.com.
"""

from pathlib import Path
import tempfile
import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TOKEN = 'token.pickle'
CRED = 'client_secret_1050753027000-deom7qiq1gjm2if6e2bfdnmt0gjvu2pr.apps.googleusercontent.com.json'
CREDENTIALS_FILE = str(Path(__file__).parent / CRED)
TOKEN_FILE = str(Path(__file__).parent / TOKEN)
NOTE_NAME = 'RISO'

def get_oauth_credentials(client_secrets_path: str = CREDENTIALS_FILE) -> object:
    """get oauth credentials with token persistence"""
    
    if not Path(client_secrets_path).exists():
        raise FileNotFoundError(f"client_secrets.json not found. Download from Google Cloud Console")
    
    creds = None
    
    # load existing token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("refreshing expired token...")
            creds.refresh(Request())
        else:
            print("starting oauth flow - browser will open...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # save token for future use
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        print("credentials saved for future use")
    
    return creds

def verify_access(file_id: str) -> dict | None:
    """verify access to google drive file and return metadata"""
    try:
        creds = get_oauth_credentials()
        service = build('drive', 'v3', credentials=creds)
        
        # get file metadata
        file_metadata = service.files().get(fileId=file_id).execute()
        
        print(f"✓ access verified")
        print(f"  file: {file_metadata.get('name')}")
        print(f"  type: {file_metadata.get('mimeType')}")
        print(f"  size: {file_metadata.get('size', 'unknown')} bytes")
        print(f"  modified: {file_metadata.get('modifiedTime')}")
        
        return file_metadata
        
    except HttpError as e:
        print(f"✗ access failed: {e}")
        return None
    except FileNotFoundError as e:
        print(f"✗ setup error: {e}")
        return None

def download_shared_excel_file(file_id: str) -> Path:
    """download/export shared google drive file to temp location"""
    
    creds = get_oauth_credentials()
    service = build('drive', 'v3', credentials=creds)
    
    # get file metadata
    file_metadata = service.files().get(fileId=file_id).execute()
    original_name = file_metadata.get('name', 'downloaded_file') + '.xlsx'
    mime_type = file_metadata.get('mimeType')
    
    print(f"downloading {original_name}...")
    
    # check if it's a google sheets file
    if mime_type == 'application/vnd.google-apps.spreadsheet':
        # export as xlsx
        request = service.files().export_media(fileId=file_id, 
                                              mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        # regular download for binary files
        request = service.files().get_media(fileId=file_id)
    
    file_content = request.execute()
    
    # save to temp file
    temp_file = Path(tempfile.gettempdir()) / original_name
    temp_file.write_bytes(file_content)
    
    print(f"✓ downloaded to {temp_file}")
    return temp_file

if __name__ == "__main__":
    file_id = '1OlhfTBl_ETbguEip9hMwxJeFkiEwENEoUJNksDwm_ng'    # FUSILLO_NOTES
    file_id = '1cKBS9WrjI0VlRT1ddyW3YGSIbgojBGM0AXuYa4Ajv-Q' #RISO NOTES!!!
    if not file_id:
        print("no file id provided")
        exit(1)
    
    # verify access
    metadata = verify_access(file_id)
    if not metadata:
        print("cannot access file or get metadata")
        exit(1)
    
    # download file
    try:
        temp_file = download_shared_excel_file(file_id)

        from excel_extract_sheets import copy_excel_tabs_to_files, dispatch_files
        output_dir = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Riso\2026'
        temp_dir = r'C:\Users\rnel\Documents\Python Scripts\temp_out'
        copy_excel_tabs_to_files(temp_file, temp_dir)
        
        print('Now organizing notes to dest folders...')
        dispatch_files(temp_dir, output_dir)
    
    except FileNotFoundError as e:
        print(f'file not found: {e}. Did you map the P: drive?')
        # this won't be triggered now
    except Exception as e:
        print(f"error: {e}")
    finally:
        # cleanup temp
        if 'temp_file' in locals():
            temp_file.unlink(missing_ok=True)
            print(f"cleaned up {temp_file}")