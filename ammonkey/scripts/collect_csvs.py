import os
import shutil
import hashlib
import re, glob
from tqdm import tqdm

pull_match = ['puul', 'pull']
bbt_match = ['bbt']

def _hash(path, chunk_size=8192) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()

def iec(filename: str) -> bool:
    '''in/exclustion of filenames'''
    if not filename.lower().endswith('.csv'):
        return False
    if not any(m in filename.lower() for m in pull_match):
        return False
    return True

def scan_and_copy(root_dir, dest_dir, headers):
    """
    Recursively finds .csv under root_dir whose first row starts with headers,
    and copies them into dest_dir. If a file name already exists but content differs,
    appends an 8-char hash to avoid collisions.
    """
    os.makedirs(dest_dir, exist_ok=True)
    prefix = ','.join(headers)
    
    pattern = os.path.join(root_dir, '*', '*', '**', '*.csv')

    print('Starting')
    it = glob.iglob(pattern, recursive=True)
    print('Really starting')
    for src in tqdm(it):
        fn = os.path.basename(src)
        if not iec(fn):
            continue
        with open(src, 'r', encoding='utf-8') as f:
            if not f.readline().strip().startswith(prefix):
                continue
        base, ext = os.path.splitext(fn)
        h = _hash(src)[:8]
        dst = os.path.join(dest_dir, fn)
        if os.path.exists(dst):
            if _hash(dst)[:8] == h:
                continue
            dst = os.path.join(dest_dir, f"{base}_{h}{ext}")
        shutil.copy2(src, dst)

def organize_by_date(dest_dir):
    """
    Moves each file in dest_dir into a subfolder named by the first yyyymmdd
    found in its filename (or 'unknown_date' if none).
    """
    pattern = re.compile(r'(\d{8})')
    for fn in os.listdir(dest_dir):
        src = os.path.join(dest_dir, fn)
        if not os.path.isfile(src):
            continue
        m = pattern.search(fn)
        folder = m.group(1) if m else 'unknown_date'
        tgt_dir = os.path.join(dest_dir, folder)
        os.makedirs(tgt_dir, exist_ok=True)
        shutil.move(src, os.path.join(tgt_dir, fn))

if __name__ == '__main__':
    headers = ["LUPA_x", "LUPA_y", "LUPA_z"]
    headers = ['I_T_x', 'I_T_y', 'I_T_z']
    dst = r'C:\Users\mkrig\Documents\Python Scripts\all_csvs\pull-hand-0826'
    os.makedirs(dst, exist_ok=True)
    scan_and_copy(
        r'P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025', 
        dst, 
        headers)
    # organize_by_date(r'C:\Users\mkrig\Documents\Python Scripts\all_csvs\pull-cleaned')