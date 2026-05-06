'''
an adaptor transferring dlc output to anipose
'''

import shutil
import re
import json
import logging
from pathlib import Path
from .daet import DAET
from .ani import AniposeProcessor
from .expNote import ExpNote
from .statusChecker import StatusChecker
from .config import Config

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

def getDLCMergedFolderName(*paths: Path) -> str:
    '''logic for determining merged dlc folder name. look for full match in the process
    combos in config.
    Returns first full match. Doesn't check for cam group id (L/R..)'''

    infos = [parseDLCFolderName(p) for p in paths]
    part_names = [i[0] for i in infos]
    part_names = sorted(part_names)

    combo_name = None

    for cname, cinfo in Config.dlc_combos.items():
        models = list(cinfo.values())
        if sorted(models) == part_names:
            combo_name = cname
            break
    else: # no match, try model dir-name for backward comp
        for model, minfo in Config.dlc_models.items():
            mdir_name = minfo.get('dir-name', None)
            if not mdir_name or mdir_name not in part_names:
                continue
            part_names = [model if p == mdir_name else p for p in part_names]
        
        for cname, cinfo in Config.dlc_combos.items():
            models = list(cinfo.values())
            if sorted(models) == part_names:
                combo_name = cname
                break
        else:
            combo_name = part_names[0]
    
    merged_id = mergeId(*(i[2] for i in infos))

    return f'{combo_name}-{infos[0][1]}_{merged_id}'

def mergeId(*ids: int) -> str:
    if len(ids) == 1:
        return f"{ids[0]:04d}"[-4:]
    if len(ids) == 2:
        return f"{ids[0]:02d}"[-2:] + f"{ids[1]:02d}"[-2:]
    if len(ids) == 3:
        return f"{ids[0]:02d}"[-2:] + f"{ids[1]:01d}"[-1:] + f"{ids[2]:01d}"[-1:]
    # 4 or more: take last digit of each, use first 4
    return "".join(f"{i:01d}"[-1:] for i in ids[:4])

def parseDLCFolderName(f: Path) -> tuple[str, int, int]:
    '''matches names eg. TS-L-20250618 [1991]'''
    m = re.match(r'^(.*?)-(\d{8})\s\[(\d+)]$', f.name)
    if not m:
        raise ValueError(f"Unrecognized folder name format: {f.name}")
    name, ymd, dex = m.groups()
    return name, int(ymd), int(dex)

def searchModelSets(data_path: Path) -> set[str] | None:
    all_sets = Config.dlc_combos.keys()
    all_sets_pattern = '|'.join(all_sets)
    pattern = re.compile(rf'^(?:{all_sets_pattern})-\d{{8}}_\d{{3,4}}$')
    seen = set()
    for file in Path(data_path).rglob('*'):
        if pattern.fullmatch(file.name) and file.name not in seen:
            # print(file.name)
            seen.add(file.name)
    return seen if seen else None

def getDaetsUnderModel(
        sync_root_path: Path, 
        model_name: str,
        note: ExpNote|None = None,
) -> list[str] | None:
    '''given "./SynchronizedVideos", return the DAETs involved'''
    logger.debug(f'getDaetsUnderModel: {sync_root_path=}, {model_name=}')
    if not sync_root_path.exists():
        raise FileNotFoundError(f'getDaetsUnderModel: {sync_root_path} doesnt exist')
    
    seen_daets: list[str] = []
    for daet_folder in sync_root_path.glob('*'):
        if not daet_folder.is_dir():
            continue
        try:
            daet = DAET.fromString(daet_folder.name)
        except ValueError as e:
            logger.debug(f'daet conversion failed {daet_folder.name}')
            continue
        else:
            if note and not daet in note.daets:
                logger.warning(f'Skipped {daet} due to not included in note provided')
                continue
        dlc_model_path = daet_folder / 'DLC' / model_name        #FIXME this is fragile
        if not dlc_model_path.exists():
            logger.debug(f'Skipped {dlc_model_path}, does not exist')
            continue
        seen_daets.append(daet_folder.name)
    
    # logger.debug(f'{seen_daets=}')
    return seen_daets

def isAniProcessed(ani_path: Path, sync_root_path: Path, ap: AniposeProcessor|None = None, note: ExpNote | None = None) -> int:  #FIXME if a folder is just copied with calib, it doesnt show as need ani
    '''0: totally not; 1: fully processed (csv_count==daet_count); -1: partly processed'''
    if not ani_path.exists():
        return False
    process_stat: dict[str, bool] = {}
    for daet_folder in ani_path.glob('*'):
        if not daet_folder.is_dir(): 
            continue
        if not daet_folder.name or not DAET.isDaet(daet_folder.name):
            continue
        csv_folder = daet_folder / 'pose-3d'
        for f in csv_folder.glob('*.csv'):
            process_stat[daet_folder.name] = True
            break
        else:   # i.e. no csv
            try:
                daet = DAET.fromString(daet_folder.name)
                process_stat[daet_folder.name] = daet.isCalib
            except ValueError:  # who knows what folder you put
                process_stat[daet_folder.name] = False

    logger.debug(f'{ani_path=}, {process_stat=}')
    
    if all(process_stat.values()):
        if ap and not note:
            note = ap.note
        daet_namelist = getDaetsUnderModel(sync_root_path=sync_root_path, model_name=ani_path.name, note=note)
        logger.debug(f'{daet_namelist=}')
        if daet_namelist:
            if all([d in process_stat.keys() for d in daet_namelist]):
                return 1
            else:
                return -1
        else: return 1
    elif any(process_stat.values()):
        return -1
    else:
        return 0

def getUnprocessedDlcData(
        data_path: Path, 
        ap: AniposeProcessor|None = None, 
        note: ExpNote|None=None) -> list[str]|None:
    '''
    input a data_path, then 
    '''
    if not data_path.exists():
        raise FileNotFoundError(f'FNF: {data_path}')
    sync_root_path = data_path / 'SynchronizedVideos'
    if not sync_root_path.exists():
        raise FileNotFoundError(f'FNF: {sync_root_path}')
    
    model_sets = searchModelSets(sync_root_path)
    if not model_sets:
        return None
    
    unprocessed:list[str] = []
    for p in model_sets:
        if_ap = isAniProcessed(ani_path=data_path / 'anipose' / p, sync_root_path=sync_root_path, ap=ap, note=note)
        logger.debug(if_ap)
        if if_ap in [0, -1]:
            unprocessed.append(p)
    return unprocessed if unprocessed else None
        