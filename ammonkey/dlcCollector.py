'''
an adaptor transferring dlc output to anipose
'''

import shutil
import re
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def mergeDlcOutput(*folders:Path) -> int:
    '''
    combines multiple dlc output folders like TS-L-yyyymmdd [xxxx].
    Assumes folder is {daet}/DLC/separate/{named_after_model}
    '''
    nef = next((f for f in folders if not f.exists()), None)
    if nef:
        raise FileNotFoundError(f'mergeDLCOutput: passed non-existing folder: {nef}')
    
    if (l:=len(folders)) < 1:
        raise ValueError(f'mergeDLCOutput: expected >=1 args, passed {l}')
    elif l == 1:
        merge_name = getDLCMergedFolderName(folders[0], None)
    else:
        merge_name = getDLCMergedFolderName(*folders[0:2])

    dlc_root = folders[0].parent.parent  # should be {daet}/DLC/    # NG - hardcoded
    dst = dlc_root / merge_name
    dst.mkdir(exist_ok=True)

    record: list[dict] = []
    for f in folders:
        folder_json = f / 'inherit.json'
        try:
            with open(folder_json) as jf:
                folder_info_dict = json.load(jf)
        except FileNotFoundError as e:
            logger.error(f'mergeDLCOutput: inherit json not found: {e}')
            folder_info_dict = None
        j = {}
        j['dlc_info'] = folder_info_dict

        # copy h5 coords
        j['files'] = copyH5(f, dst)
        
        record.append(j)

    with open(dst / 'inherit.json', 'w') as f:
        json.dump(record, f, indent=4)

    logger.info(f'mergeDLCOutput: merged {", ".join([f.name for f in folders])}')
    return 1

def copyH5(
    src: Path, dst: Path, 
    filtered_only: bool = True, 
) -> list[str]:
    '''copies h5 files in folder src to dst. Returns names of file copied'''
    file_list = []
    search_pattern = '*_filtered.h5' if filtered_only else '*.h5'
    for f in src.glob('*.h5'):
        try:
            shutil.copy(f, dst)
            file_list.append(f.name)
        except OSError as e:
            logger.error(f'copyH5: failed {f.name} - {e}')

    return file_list

def getDLCMergedFolderName(f1: Path, f2: Path | None) -> str:
    '''logic for determining merged dlc folder name. expandable.'''
    f1_info = parseDLCFolderName(f1)

    try:
        f2_info = parseDLCFolderName(f2)
    except AttributeError:
        # single camgroup field
        postfix = f'{f1_info[1]}_{f1_info[2]}'
        if 'Brkm' in f1_info[0]:
            return f'Brkm-{postfix}'
        elif 'BBT' in f1_info[0]:
            return f'BBT-{postfix}'
        elif 'Pull-Hand' in f1_info[0]:
            return f'Pull-Hand-{postfix}'
        else:
            return f'{f1_info[0]}-{postfix}'
        
    # multiple group field
    if 'TS' in f1_info[0] and 'TS' in f2_info[0]:
        return f'TS-LR-{f1_info[1]}_{mergeId(f1_info[2], f2_info[2])}'
    elif 'Pull' in f1_info[0] and 'Pull' in f2_info[0]:
        return f'Pull-LR-{f1_info[1]}_{mergeId(f1_info[2], f2_info[2])}'
    
    raise ValueError(f'Unsupported model set: {f1.name} and {f2.name}')

def getDLCMergedNameShort(f1: Path, f2: Path) -> str:
    '''logic for determining merged dlc folder name. expandable.'''
    f1_info = parseDLCFolderName(f1)
    f2_info = parseDLCFolderName(f2)
    merged_id = mergeId(f1_info[2], f2_info[2])

    if 'TS' in f1_info[0] and 'TS' in f2_info[0]:
        return f'TS[{merged_id}]'
    elif 'Pull' in f1_info[0] and 'Pull' in f2_info[0]:
        return f'Pull[{merged_id}]'
    elif True:
        pass
    
    raise ValueError(f'Unsupported model set: {f1.name} and {f2.name}')

def mergeId(a: int, b: int) -> int:
    return int(f"{a:04d}"[-2:] + f"{b:04d}"[-2:])

def parseDLCFolderName(f: Path) -> tuple[str, int, int]:
    '''matches names eg. TS-L-20250618 [1991]'''
    m = re.match(r'^(.*?)-(\d{8})\s\[(\d+)]$', f.name)
    if not m:
        raise ValueError(f"Unrecognized folder name format: {f.name}")
    name, ymd, dex = m.groups()
    return name, int(ymd), int(dex)