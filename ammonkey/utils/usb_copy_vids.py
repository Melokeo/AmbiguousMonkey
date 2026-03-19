'''utils for listing usb devices and video copying automation'''

import re
import shutil
from datetime import datetime, timedelta

import platform
if not platform.system() == 'Windows':
    raise NotImplementedError('This utility is currently only implemented for Windows')

import pythoncom
import wmi
from pathlib import Path

from ol_logging import set_colored_logger
lg = set_colored_logger(__name__)

CARD_NAME_REGEX = [r'^cam\d$', ]

TARGET_VID_DIRS = {
    'cam1': 'cam1',
    'cam2': 'cam2',
    'cam3': 'cam3',
    'cam4': 'cam4',
}

FILE_SUFFIXES = ['.mp4', '.xml']    # case insensitive

def _drive_vid_dir(drive: str|Path) -> Path:
    return Path(drive) / 'PRIVATE/M4ROOT/CLIP'

def copy_from_card(
        drive: str, 
        date: datetime|str,
        dest_dir: Path,
        file_list: list[str]|None=None,
    ) -> list[Path]:
    '''copy videos from drive with date in name to dest dir, return list of copied paths'''
    source_dir = _drive_vid_dir(drive)
    if not source_dir.exists():
        raise FileNotFoundError(f'Vid dir not found: {source_dir}')
    
    if file_list:   # use provided file list
        files_to_copy = [source_dir / f for f in file_list]
        if date:
            lg.warning('date filter overridden by file_list')
    else:   # create file list from date filter
        files_to_copy = files_from_date(source_dir, date, suffix=FILE_SUFFIXES)
    
    if not files_to_copy:
        lg.warning(f'No files found for {date} on {drive}')
        return []
    
    lg.info(f'Found {len(files_to_copy)} files for date {date} on drive {drive}')
    copied_files = batch_copy(files_to_copy, dest_dir)
    lg.info(f'Copied {len(copied_files)} files from drive {drive} to {dest_dir}')

    return copied_files

def batch_copy(source: list[Path], dest: Path) -> list[Path]:
    '''copy a batch of files, return list of copied paths'''
    copied = []
    for src in source:
        dst = dest / src.name
        if dst.exists():
            lg.info(f'Skipped copying {src.name} due to existance')
            continue
        shutil.copy(src, dst)
        copied.append(dst)
        lg.info(f'Copied {src.name}')
    return copied

def files_from_date(
        source: str|Path, 
        date: datetime|str,     # yyyymmdd for str
        suffix: list[str]|str|None=None) -> list[Path]:
    '''get files from source with creation date, optionally filter by suffix'''
    source = Path(source)
    if not source.is_dir():
        raise ValueError(f"Source path is not a valid directory: {source}")
    if not source.exists():
        raise FileNotFoundError(f"FNF source path {source}")
    
    # lg.debug(f'getting files from {source=}, {date=}, {suffix=}')
    if isinstance(date, datetime):
        date_str = date.strftime('%Y%m%d')
    else:
        date_str = date
        if not re.match(r'^\d{8}$', date_str):
            raise ValueError(f'Invalid date: {date_str}, expected yyyymmdd')
    
    # normalize suffixes for leading '.'
    if suffix is not None:
        if isinstance(suffix, str):
            valid_suffixes = (suffix if suffix.startswith('.') else f'.{suffix}',)
        else:
            valid_suffixes = tuple(s if s.startswith('.') else f'.{s}' for s in suffix)
    else:
        valid_suffixes = None

    # MATCH LOGIC
    matched_files = []

    for file_path in source.iterdir():
        if not file_path.is_file():
            continue
            
        # filter by suffix first
        if valid_suffixes and file_path.suffix.lower() not in valid_suffixes:
            continue
            
        # file creation time 
        # st_birthtime win/mac; st_ctime linux
        stat = file_path.stat()
        creation_timestamp = getattr(stat, 'st_birthtime', stat.st_ctime)
        file_date_str = datetime.fromtimestamp(creation_timestamp).strftime('%Y%m%d')
        
        if file_date_str == date_str:
            matched_files.append(file_path)

    return matched_files

def list_usb_devices(vol_name_filter: list[str] | str | None = None) -> list[str]:
    '''list connected usb devices'''
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
    finally:
        pythoncom.CoUninitialize()
    
    # filter for removable
    removable_drives = c.Win32_LogicalDisk(DriveType=2) # when can it adapt type checking??
    
    if not removable_drives:
        lg.debug("No removables found.")
        return []
    
    target_drives = []

    for drive in removable_drives:
        drive_letter = drive.DeviceID       # like X:
        # VolumeName can be None??
        volume_name = drive.VolumeName or ""
        
        # check regex filter
        is_target_card = False
        if vol_name_filter:
            if isinstance(vol_name_filter, str):
                vol_name_filter = [vol_name_filter]
            is_target_card = any(re.match(pattern, volume_name, re.IGNORECASE) for pattern in vol_name_filter)
        
        if is_target_card:
            # lg.debug(f"Card found: {drive_letter} (Vol: {volume_name})")
            target_drives.append(drive_letter)
        else:
            pass # lg.debug(f"Other USB: {drive_letter} (Vol: {volume_name})")
    
    return target_drives

def scan_drives() -> dict[str, str]:
    '''map discovered volume names to drive letters for all removable drives'''
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        removable = c.Win32_LogicalDisk(DriveType=2)
        return {(d.VolumeName or ""): d.DeviceID for d in removable}
    finally:
        pythoncom.CoUninitialize()

def drive_is_card(drive: str) -> bool:
    '''double check if a drive looks like cam card'''
    return (Path(drive) / 'PRIVATE/M4ROOT').exists()

if __name__ == "__main__":
    cards = list_usb_devices(CARD_NAME_REGEX)
    for c in cards:
        lg.info(f'{c}\t{drive_is_card(c)}')
    else:
        lg.info('Finished')

    lg.info(
        files_from_date(
            r'C:\Users\mkrig\AppData\Local\anaconda3\envs\amm\Lib\site-packages\ammonkey\utils', 
            datetime.today() - timedelta(days=3),
        ))
    
    target_path = r'P:\projects\monkeys\Remyelination\DATA_RAW\Pepe\2026\02\20260226'

    