'''
File operations centered
'''

import os, logging, platform
from pathlib import Path

try:
    import win32com.client
except ImportError:
    pass

logger = logging.getLogger(__name__)

def getDataPath(path:Path|str) -> Path:
    return Path(str(path).replace('DATA_RAW', 'DATA'))

def dataSetup(
        raw_path:str|Path=None, 
        data_path:str|Path=None, 
) -> bool: 
    '''Creates data_path structure'''
    if not raw_path and not data_path:
        raise ValueError('dataSetup doesnt get valid path args')
    if not data_path:
        data_path = getDataPath(raw_path)
    data_path = Path(data_path)
    
    try:
        os.makedirs(data_path, exist_ok = True)
        sub_dir = [
            'SynchronizedVideos',
            'anipose',
            'SynchronizedVideos/SyncDetection',
            'clean'
            ]
        for sd in sub_dir:
            os.makedirs((data_path / sd), exist_ok = True)
    except OSError as e:
        logger.critical(f'Cannot setup data_path {e}')
    
    if raw_path:
        twoWayShortcuts(str(raw_path), str(data_path))

def twoWayShortcuts(path1:str, path2:str) -> None:
    """Creates two-way shortcuts in windows"""
    # print(platform.platform())
    if not 'Windows' in platform.platform():
        return
    
    path1, path2 = str(path1), str(path2)
    
    shell = win32com.client.Dispatch("WScript.Shell")
    
    # Define shortcut paths
    shortcut1_path = os.path.join(path1, os.path.basename(path2) + ".lnk")
    shortcut2_path = os.path.join(path2, os.path.basename(path1) + ".lnk")

    # Create shortcut from path1 → path2
    shortcut1 = shell.CreateShortcut(shortcut1_path)
    shortcut1.TargetPath = path2
    shortcut1.WorkingDirectory = path2
    shortcut1.Save()

    # Create shortcut from path2 → path1
    shortcut2 = shell.CreateShortcut(shortcut2_path)
    shortcut2.TargetPath = path1
    shortcut2.WorkingDirectory = path1
    shortcut2.Save()

    print(f"Shortcut created: {shortcut1_path} → {path2}")
    print(f"Shortcut created: {shortcut2_path} → {path1}")
