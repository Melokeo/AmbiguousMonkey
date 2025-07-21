'''finalize - collect csvs to folder "clean"'''
import shutil
from pathlib import Path
from datetime import datetime

from .expNote import ExpNote

def violentCollect(ani_path: Path|str, clean_path: Path|str) -> None:
    '''simply collects all csvs in pose-3d inside an anipose folder'''
    ani_path = Path(ani_path)
    clean_path = Path(clean_path)
    if not ani_path.exists():
        raise FileNotFoundError(f'violentCollect: non-existing ani_path {ani_path}')
    
    dst = clean_path / ani_path.name
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
            f.write(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n]')
            f.write('Files copied: \n\t')
            f.write('\n\t'.join(csv_list))
            f.write('\n\n')

def writeProcedureSummaryCsv(note: ExpNote, ani_path: Path, clean_path: Path) -> None:
    pass