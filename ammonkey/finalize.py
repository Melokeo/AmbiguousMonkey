'''finalize - collect csvs to folder "clean"'''
import shutil
from pathlib import Path
from datetime import datetime
import logging
lg = logging.getLogger(__name__)

from .expNote import ExpNote

def violentCollect(ani_path: Path|str, clean_path: Path|str) -> bool:
    '''
    simply collects all csvs in pose-3d inside an anipose folder
    
    returns True if anything is copied.
    '''
    ani_path = Path(ani_path)
    clean_path = Path(clean_path)
    if not ani_path.exists():
        raise FileNotFoundError(f'violentCollect: non-existing ani_path {ani_path}')
    
    dst = clean_path / ani_path.name
    prev_files = [] # records files prior to copy, to keep record
    if (dir_exists:=dst.exists()):
        lg.warning(f'violentCollect: destination already exists {dst}')
        prev_files = list(dst.rglob('*.csv'))
    dst.mkdir(exist_ok=True)

    csv_list: list[str] = []
    for csv in ani_path.rglob('*.csv'):
        csv_list.append(str(csv))
        dst_file = dst / csv.name
        if dst_file.exists():
            # raise FileExistsError(f'violentCollect: refused to overwrite already-collected csv: {dst_file}')
            continue
        shutil.copy(csv, dst_file)
    
    log = dst / 'scent.log'
    log.touch()
    if csv_list:
        with open(log, 'a') as f:
            f.write(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]\n')
            f.write('Files copied: \n\t')
            f.write('\n\t'.join(csv_list))
            f.write('\n\n')
            if dir_exists:
                f.write(f'This is not a de novo copying. Files before copying:\n\t')
                f.write('\n\t'.join([f.name for f in prev_files]))
                f.write('\n\n')
        return True
    
    return False

def writeProcedureSummaryCsv(note: ExpNote, ani_path: Path, clean_path: Path) -> None:
    pass

def one_stop_collect(note: ExpNote) -> list[str]:
    '''collects all anipose csvs into clean folder'''
    clean_root = note.getCleanDir()
    ani_root = note.getAniRoot()
    if not ani_root.exists():
        lg.warning(f'one_stop_collect: anipose dir not found: {ani_root}')
        return []
    
    collected_sets = []
    for ms_folder in ani_root.glob('*'):
        if not ms_folder.is_dir() or not ms_folder.name[-4:].isnumeric():
            continue
        lg.info(f'Collecting from set {ms_folder.name}')
        if violentCollect(ms_folder, clean_root):
            collected_sets.append(ms_folder.name)
    
    return collected_sets