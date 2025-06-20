'''
Tracking status checker
p.s. daet = date-animal-experiment-task
'''
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union, List
import re
from tqdm import tqdm
from .. import monkeyUnityv1_8 as mky
from .pullAniAll import getAllDates, convertRawToData, getCSVPathUnder
from .silence import silence

@dataclass
class checkpoint:
    name: str
    subdir: Optional[list[str]] = None
    condition: list[str] = None
    interpret: Optional[dict[Union[tuple[bool],int], str]] = None

    def __post_init__(self):
        if not self.subdir:
            self.subdir = ['']
        if not self.condition:
            self.condition = []
        if len(self.condition) == 0:
            raise ValueError('checkpoint must have a condition')
    
    def check(self, data_path:Union[Path,str], daet:str) -> tuple[bool]:
        if isinstance(data_path, str): data_path = Path(data_path)
        subdir = subph(self.subdir, daet)
        cond = subph(self.condition, daet)

        workdir = data_path.joinpath(*subdir)
        if not workdir.exists(): raise FileNotFoundError

        stat = []
        for p in cond:
            r = re.compile(p)
            flg = False
            for f in workdir.rglob('*'):    #TODO this can be inefficient
                if r.fullmatch(f.name):
                    flg = True
                    break
            stat.append(flg)
        return tuple(stat)

dlc_interp = {
            (True, True, False, False): 'OK',
            (False, False, True, True): 'Not filtered',
            4: "OK",
            3: 'Mixed state',
            2: 'Mixed state',
            1: 'Not fully processed',
            0: 'Possibly not processed',
        }
skip_interp = {
            1: 'Marked',
            0: 'x'
        }

checkpoints = {
    'sync_L': checkpoint(
        'SyncL',
        subdir=['SynchronizedVideos', '`', 'L'],
        condition=['`-cam1\.mp4', '`-cam2\.mp4'],
        interpret={
            2: 'OK',
            1: 'Missing 1 video',
            0: 'Missing all'
        }
    ),
    'sync_R': checkpoint(
        'SyncR',
        subdir=['SynchronizedVideos', '`', 'R'],
        condition=['`-cam3\.mp4', '`-cam4\.mp4'],
        interpret={
            2: 'OK',
            1: 'Missing 1 video',
            0: 'Missing all'
        }
    ),
    'skipsync': checkpoint(
        '.skipSync',
        subdir=['SynchronizedVideos', '`'],
        condition=['\.skipSync'],
        interpret=skip_interp
    ),
    'skipdet': checkpoint(
        '.skipDet',
        subdir=['SynchronizedVideos', '`'],
        condition=['\.skipDet'],
        interpret=skip_interp
    ),
    'dlc_L': checkpoint(
        'DLC_L',
        subdir=['SynchronizedVideos', '`', 'L'],
        condition=['`-cam1DLC.*?_filtered\.h5', '`-cam1DLC.*?\.h5',
                '`-cam2DLC.*?_filtered\.h5', '`-cam2DLC.*?\.h5'],
        interpret=dlc_interp
    ),
    'dlc_R': checkpoint(
        'DLC_R',
        subdir=['SynchronizedVideos', '`', 'R'],
        condition=['`-cam3DLC.*?_filtered\.h5', '`-cam3DLC.*?\.h5',
                '`-cam4DLC.*?_filtered\.h5', '`-cam4DLC.*?\.h5'],
        interpret=dlc_interp
    ),
    'skipdlc_L': checkpoint(
        'skipdlc_L',
        subdir=['SynchronizedVideos', '`', 'L'],
        condition=['\.skipDLC'],
        interpret=skip_interp
    ),
    'skipdlc_R': checkpoint(
        'skipdlc_L',
        subdir=['SynchronizedVideos', '`', 'R'],
        condition=['\.skipDLC'],
        interpret=skip_interp
    ),
}

anipose_interp = {
    4: "OK",
    3: "x Only 3 *.h5 found",
    2: "x Only 2 *.h5 found",
    1: "x Only 1 *.h5 found",
    0: "x Only 3 *.h5 found",
}

checkpoints_anipose = {
    'pose-2d-f': checkpoint(
        'pose-2d-filtered',
        subdir=['anipose', '`', 'pose-2d-filtered'],
        condition=['`-cam1\.h5', '`-cam2\.h5', '`-cam3\.h5', '`-cam4\.h5'],
        interpret={
            4: "OK",
            3: "x Only 3 *.h5 found",
            2: "x Only 2 *.h5 found",
            1: "x Only 1 *.h5 found",
            0: "No *.h5",
        }
    ),
    'pose-3d': checkpoint(
        'pose-3d',
        subdir=['anipose', '`', 'pose-3d'],
        condition=['`\.csv'],
        interpret={
            1: "OK",
            0: "x"
        }
    ),
    'clean': checkpoint(
        'clean',
        subdir=['clean'],
        condition=['`\.csv'],
        interpret={
            1: "OK",
            0: "x"
        }
    ),
}

checkpoints_extra = {
    'csv_aw': checkpoint(
        'Anywhere CSV',
        subdir=[''],
        condition=['`\.csv'],
        interpret={
            1: "Found CSV elsewhere",
            0: 'FNF'
        }
    )
}

chk_dict = checkpoints | checkpoints_anipose | checkpoints_extra

def subph(x: Union[str, List[str]], replacement: str) -> Union[str, List[str]]:
    '''SUBstitute PlaceHolder (`)'''
    if isinstance(x, str):
        return x.replace('`', replacement)
    elif isinstance(x, list):
        return [i.replace('`', replacement) if isinstance(i, str) else i for i in x]
    return x

def checkDaetValidity() -> bool:
    pass

def checkOnDate(praw:Path, pdat:Path=None) -> None:
    if pdat is None:
        pdat = Path(str(praw).replace('DATA_RAW', 'DATA'))
    print(f'\n===== {pdat.name} =====')
    daets = mky.getTasks(PPATH_RAW=str(praw), task=mky.Task.All)
    if daets:
        for daet in daets:
            if 'calib' in daet.lower(): continue
            print(f'--- {daet} ---')
            if Path(pdat/'clean').exists:
                if sum(chk_dict['clean'].check(pdat, daet)) == 1:
                    print('OK')
                    continue
            for chk in chk_dict.values():
                print(chk.name, end=': ', flush=True)
                try:
                    stat = chk.check(pdat, daet)
                except FileNotFoundError:
                    print('FNF')
                    continue
                if chk.interpret:
                    if stat in chk.interpret.keys():
                        print(chk.interpret[stat])
                    elif sum(stat) in chk.interpret.keys():
                        print(chk.interpret[sum(stat)])
                    else:
                        print('Undefined status')
                else:
                    print(stat)
    else: 
        print('No tasks')

def main():
    raw_dir = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
    raws = getAllDates(Path(raw_dir))
    datas = convertRawToData(raws)
    #for praw, pdat in tqdm(list(zip(raws, datas)), desc='Scanning dates'):
    for praw, pdat in zip(raws, datas):
        checkOnDate(praw, pdat)

if __name__ == '__main__':
    #main()
    checkOnDate(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\03\20250321')