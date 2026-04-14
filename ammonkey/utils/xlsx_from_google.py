"""
Automated download + dispatching for fusillo notes, from google drive.
just click run whenever you feel like updating local note copies.
** IF PROMPTED FOR GOOGLE ACCOUNT: ** select pi*******dlc@gmail.com.
"""

from pathlib import Path
import tempfile
import pickle
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ammonkey.utils.excel_extract_sheets import (
    copy_excel_tabs_to_files, dispatch_files,
)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TOKEN = 'token.pickle'
CRED = 'client_secret_1050753027000-deom7qiq1gjm2if6e2bfdnmt0gjvu2pr.apps.googleusercontent.com.json'
CREDENTIALS_FILE = str(Path(__file__).parent / 'google_cred' / CRED)
TOKEN_FILE = str(Path(__file__).parent / 'google_cred' / TOKEN)
NOTE_CONFIG_FILE = Path(__file__).parent / 'google_cred' / 'riso.json'


def load_note_config(config_path: Path = NOTE_CONFIG_FILE) -> dict[str, str]:
    """load note source/destination config from json"""

    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")

    config_data = json.loads(config_path.read_text(encoding='utf-8'))
    if not isinstance(config_data, dict):
        raise ValueError(f"invalid config format: {config_path}")

    required_keys = ("file_id", "output_dir", "output_prefix")
    missing = [key for key in required_keys if not config_data.get(key)]
    if missing:
        raise ValueError(f"missing config keys in {config_path}: {', '.join(missing)}")

    return {
        "file_id": str(config_data["file_id"]),
        "output_dir": str(config_data["output_dir"]),
        "output_prefix": str(config_data["output_prefix"]),
    }

def get_oauth_credentials(client_secrets_path: str = CREDENTIALS_FILE) -> object:
    """get oauth credentials with token persistence"""
    
    if not Path(client_secrets_path).exists():
        raise FileNotFoundError(f"client_secrets.json not found. Download from Google Cloud Console")
    
    creds = None
    token_path = Path(TOKEN_FILE)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    
    # load existing token
    if token_path.exists():
        with open(token_path, 'rb') as token:
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
        with open(token_path, 'wb') as token:
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

def download_shared_excel_file(file_id: str, temp_dir: Path | None = None) -> Path:
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
    if temp_dir is None:
        temp_dir = Path(tempfile.gettempdir())
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / original_name
    temp_file.write_bytes(file_content)
    
    print(f"✓ downloaded to {temp_file}")
    return temp_file

if __name__ == "__main__":
    temp_dir = None
    temp_file = None
    # try:
    #     note_config = load_note_config()
    # except (FileNotFoundError, ValueError) as e:
    #     print(f"config error: {e}")
    #     exit(1)

    # why bother, just hardcode for __main__
    note_config = {
        "name": "Riso",
        "file_id": "1cKBS9WrjI0VlRT1ddyW3YGSIbgojBGM0AXuYa4Ajv-Q",
        "output_dir": r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Riso\2026",
        "output_prefix": "RISO"
    }

    file_id = note_config["file_id"]
    output_dir = note_config["output_dir"]
    note_prefix = note_config["output_prefix"]

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
        temp_dir = Path(tempfile.mkdtemp())
        temp_file = download_shared_excel_file(file_id, temp_dir=temp_dir)
        copy_excel_tabs_to_files(temp_file, temp_dir)
        
        print('Now organizing notes to dest folders...')
        dispatch_files(temp_dir, output_dir, prefix=note_prefix)
    
    except FileNotFoundError as e:
        print(f'file not found: {e}. Did you map the P: drive?')
        # this won't be triggered now
    except Exception as e:
        print(f"error: {e}")
    finally:
        # cleanup temp
        if temp_file is not None:
            temp_file.unlink(missing_ok=True) #type: ignore
            print(f"cleaned up {temp_file}")  #type: ignore
        if temp_dir is not None and temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)
            print(f"cleaned up {temp_dir}")