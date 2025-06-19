import re, os
from typing import Iterator
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from ambiguousmonkey import monkeyUnityv1_8 as mky
from ambiguousmonkey.utils.silence import silence

t = mky.Task.Pull

reg = {
    'mo':   re.compile('^(0[1-9]|1[0-2])$'),
    'day':  re.compile('^20\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$'),
    'csv':  re.compile('^20\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])-(?i:pici)-.+\.csv$'),
    'ani':  re.compile('anipose\/[^\/]+\/pose-3d'),
}
# will anyone run this after AD2100 ??

raw_dir = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
raw_dir = Path(raw_dir)

def getAllDates(raw_dir:str) -> list[Path]:
    '''go thru all dates'''
    days = []
    for mo in raw_dir.glob('*'):
        mo: Path
        if not reg['mo'].fullmatch(mo.name):
            continue
        for day in mo.glob('*'):
            if reg['day'].fullmatch(day.name):
                days.append(day)
    return days

def convertRawToData(raw:list[Path]) -> list[Path]:
    return [Path(*[p.replace('DATA_RAW', 'DATA') if p == 'DATA_RAW' else p for p in path.parts]) for path in raw]

def getCSVPathUnder(dir: Path) -> list[Path]:
    csv_paths = []
    for f in dir.rglob('*.csv'):
        if reg['csv'].fullmatch(f.name): # and any([p in f.name for p in mky.task_match[t]]):
            csv_paths.append(f)
        # here includes 2 types: dlc csvs and anipose csvs
    return csv_paths

def getCSVStatus(csv_paths:list[Path], et:str) -> int:
    """Check CSV availability status in the given directory.
    Returns:
        int: status code:
            1   found elsewhere
            2   anipose-pose3d
            3   in clean (best)
            0   nowhere 
    """
    matches = [f for f in csv_paths if et in f.name and not 'DLC' in f.name and not 'Synchronize' in str(f)]
    # here peeled off those DLC csvs
    l = len(matches)
    if l == 0:
        return 0
    
    stat = 1
    for m in matches:
        if reg['ani'].fullmatch(m.as_posix()):
            stat = max(stat, 2)
        elif 'clean' in str(m.parent):
            stat = max(stat, 3)
    return stat

def constructVidPath(pdat:str, ets:list[str]) -> list[str]:
    return [os.path.join(pdat, 'SynchronizedVideos', et) for et in ets]

def find_closest_calib(et: str, calib_dir: str) -> Path | None:
    calib_dir:Path = Path(calib_dir)
    et_date = re.search(r'20\d{6}', et)
    if not et_date:
        return None
    et_dt = datetime.strptime(et_date.group(), '%Y%m%d')

    files = calib_dir.glob('calibration-20*.toml')
    dated = []
    for f in files:
        m = re.search(r'20\d{6}', f.name)
        if m:
            f_date = datetime.strptime(m.group(), '%Y%m%d')
            if f_date < et_dt:
                dated.append((f_date, f))
    if not dated:
        return None
    return max(dated, key=lambda x: x[0])[1]

def recordStatsSummary(summary_path: Path, date: Path, stats: dict[str, int]):
    """Append summary stats to a file."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open('a', encoding='utf-8') as f:
        for et, status in stats.items():
            f.write(f'{date.name},{et},{status}\n')

def sortSummaryCSV(csv: Path):
    lines = csv.read_text(encoding='utf-8').splitlines()
    h, *rows = lines
    rows.sort(key=lambda r: (r.split(',')[2] != '3', *r.split(',')[:2]))
    csv.write_text(h + '\n' + '\n'.join(rows), encoding='utf-8')

if __name__ == '__main__':
    summary_csv = Path(r"C:\Users\mkrig\Documents\Python Scripts\auto_anipose_rec.csv")
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_csv.write_text('date,entry,status\n', encoding='utf-8')
    raws = getAllDates(raw_dir)
    datas = convertRawToData(raws)
    for praw, pdat in tqdm(list(zip(raws, datas)), desc='Scanning dates'):
    # for praw, pdat in zip(raws, datas):
        with silence(False):
            csv_paths = getCSVPathUnder(pdat)
            if len(csv_paths) == 0:
                print(f'No kinematic csv found in {str(pdat)}')
                continue
            ets = mky.getTasks(PPATH_RAW=str(praw), task=t) # date-animal-Experiment-Task 'S
            if ets: # has target task
                stats = {et:getCSVStatus(csv_paths, et) for et in ets}
                recordStatsSummary(summary_csv, praw, stats)
                # print(stats)
                if any([stat != 3 for stat in stats.values()]):
                    print(praw.name)
                    mky.pm.PPATH_RAW = str(praw)
                    ets_to_process = [k for k, v in stats.items() if v < 3]
                    #print(f'(will anipose {str(pdat)})')
                    #print(constructVidPath(pdat, ets))
                    r'''if not os.path.exists(mky.pm.ani_base_path):
                        continue
                    calib_path = find_closest_calib(str(pdat), calib_dir=r'C:\Users\mkrig\Documents\Python Scripts\calib history')
                    if not calib_path:
                        print(f'{pdat.name} is using default calib!')
                    mky.ani_calib_mothercopy = str(calib_path or r"C:\Users\mkrig\AppData\Local\anaconda3\envs\dlc-tf\Lib\site-packages\ambiguousmonkey\cfgs\calibration.toml")
                    mky.setupAnipose(
                        mky.pm.ani_base_path,
                        vid_path=constructVidPath(pdat, ets)
                    )
                    try:
                        mky.runAnipose(mky.pm.ani_base_path)
                    except:
                        pass
                    mky.collectCSV()'''
                    

    sortSummaryCSV(summary_csv)     
    
    # check if csv is available in clean

