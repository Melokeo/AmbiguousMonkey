'''
Tracking status checker
p.s. daet = date-animal-experiment-task
'''
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import re

from .. import monkeyUnityv1_8 as mky
from .pullAniAll import getAllDates, convertRawToData, getCSVPathUnder
from .silence import silence
from ..core.daet import DAET
import logging

logger = logging.getLogger(__name__)

@dataclass
class checkpoint:
    '''Checkpoint for tracking file processing status'''
    name: str
    subdir: list[str] = field(default_factory=lambda: [''])
    condition: list[str] = field(default_factory=list)
    interpret: dict[Any, str] | None = None

    def __post_init__(self):
        if not self.subdir:
            self.subdir = ['']
        if not self.condition:
            self.condition = []
        if len(self.condition) == 0:
            raise ValueError('checkpoint must have a condition')
    
    def check(self, data_path: Path | str, daet: DAET) -> tuple[bool]:
        '''
        main checking function

        usage: chk.check(data_path:Path|str, daet:DAET) -> tuple[bool]
        1. construct working directory with given path, daet and subdir
        2. check for each "condition" regex if **any** file in each dir matches
        3. return tuple of bools for each condition
        
        Raises FileNotFoundError if working directory does not exist

        Interpretation of the result tuple:
        use interpret dict to map the result to readable status,
        '''
        if isinstance(data_path, str): 
            data_path = Path(data_path)
        subdir = subph(self.subdir, daet)
        cond = subph(self.condition, daet, escape=True)
        # logger.debug(f'{subdir=}, {cond=}')

        workdir = data_path.joinpath(*subdir)
        if not workdir.exists(): # raise FileNotFoundError(workdir)
            return (False,)
        
        stat = []
        for p in cond:
            r = re.compile(p)
            flg = False
            for f in workdir.rglob('*'):    #TODO this can be inefficient
                if r.search(f.name):
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
        condition=[r'`-cam1\.mp4', r'`-cam2\.mp4'],
        interpret={
            2: 'OK',
            1: 'Missing 1 video',
            0: 'Missing all'
        }
    ),
    'sync_R': checkpoint(
        'SyncR',
        subdir=['SynchronizedVideos', '`', 'R'],
        condition=[r'`-cam3\.mp4', r'`-cam4\.mp4'],
        interpret={
            2: 'OK',
            1: 'Missing 1 video',
            0: 'Missing all'
        }
    ),
    'sync_calib': checkpoint(
        'syncCalib',
        subdir=['SynchronizedVideos', '`'],
        condition=[r'`-cam1\.mp4', r'`-cam2\.mp4', r'`-cam3\.mp4', r'`-cam4\.mp4'],
        interpret={
            4: 'OK',
            3: 'Missing 1', 2: 'Missing 2',
        }
    ),
    'skipsync': checkpoint(
        '.skipSync',
        subdir=['SynchronizedVideos', '`'],
        condition=[r'\.skipSync'],
        interpret=skip_interp
    ),
    'skipdet': checkpoint(
        '.skipDet',
        subdir=['SynchronizedVideos', '`'],
        condition=[r'\.skipDet'],
        interpret=skip_interp
    ),
    'dlc_L': checkpoint(
        'DLC_L',
        subdir=['SynchronizedVideos', '`', 'L'],
        condition=[r'`-cam1DLC.*?_filtered\.h5', r'`-cam1DLC.*?\.h5',
                r'`-cam2DLC.*?_filtered\.h5', r'`-cam2DLC.*?\.h5'],
        interpret=dlc_interp
    ),
    'dlc_R': checkpoint(
        'DLC_R',
        subdir=['SynchronizedVideos', '`', 'R'],
        condition=[r'`-cam3DLC.*?_filtered\.h5', r'`-cam3DLC.*?\.h5',
                r'`-cam4DLC.*?_filtered\.h5', r'`-cam4DLC.*?\.h5'],
        interpret=dlc_interp
    ),
    'skipdlc_L': checkpoint(
        'skipdlc_L',
        subdir=['SynchronizedVideos', '`', 'L'],
        condition=[r'\.skipDLC'],
        interpret=skip_interp
    ),
    'skipdlc_R': checkpoint(
        'skipdlc_L',
        subdir=['SynchronizedVideos', '`', 'R'],
        condition=[r'\.skipDLC'],
        interpret=skip_interp
    ),
}

anipose_interp = {
    4: "OK",
    3: "x Only 3 *.h5 found",
    2: "x Only 2 *.h5 found",
    1: "x Only 1 *.h5 found",
    0: "No *.h5 found",
}

checkpoints_anipose = {
    'pose-2d-f': checkpoint(
        'pose-2d-filtered',
        subdir=['anipose', '`', 'pose-2d-filtered'],
        condition=[r'`-cam1\.h5', r'`-cam2\.h5', r'`-cam3\.h5', r'`-cam4\.h5'],
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
        condition=[r'`\.csv'],
        interpret={
            1: "OK",
            0: "x"
        }
    ),
    'clean': checkpoint(
        'clean',
        subdir=['clean'],
        condition=[r'`\.csv'],
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
        condition=[r'`\.csv'],
        interpret={
            1: "Found CSV elsewhere",
            0: 'FNF'
        }
    )
}

chk_dict = checkpoints | checkpoints_anipose | checkpoints_extra

def subph(x: str | list[str], replacement: str | DAET, escape: bool = False) -> str | list[str]:
    '''SUBstitute PlaceHolder (`)'''
    if escape:
        replacement = re.escape(str(replacement))
    else:
        replacement = str(replacement)

    if isinstance(x, str):
        return x.replace('`', replacement)
    elif isinstance(x, list):
        return [i.replace('`', replacement) if isinstance(i, str) else i for i in x]
    return x

def checkDaetValidity() -> bool:
    return True

def checkOnDate(praw:Path|str, pdat:Path|str|None=None) -> None:
    '''
    Checks the completeness of data processing for a single date.

    Args:
        praw (Path or str): Path to the raw data directory. Should be a valid directory path containing raw data for a specific date.
        pdat (Path or str or None, optional): Path to the processed data directory. If None, it is inferred by replacing 'DATA_RAW' with 'DATA' in `praw`.

    Prints:
        For each DAET (date-animal-experiment-task) found, prints the status of each checkpoint for that date.
        The output includes the name of the processed data directory, each DAET, and the status of each checkpoint (e.g., 'OK', 'Missing', 'FNF', etc.).

    Returns:
        None
    '''
    praw = Path(praw)
    if pdat is None:
        pdat = str(praw).replace('DATA_RAW', 'DATA')
    pdat = Path(pdat)
    print(f'\n===== {pdat.name} =====')

    daets = mky.getTasksInDAET(PPATH_RAW=str(praw), task=mky.Task.All) #TODO with next fixme, use ExpNote method instead of mky.
    if daets:
        for d in daets:
            daet = DAET.fromString(d)   #FIXME vulnerable
            if daet.isCalib: continue
            print(f'--- {daet} ---')
            if Path(pdat/'clean').exists():
                clean_check = chk_dict['clean'].check(pdat, daet)
                if clean_check == (False,):
                    print('Missing directory or file')
                    continue
                if sum(clean_check) == 1:
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
                    print(interpret_status(stat, chk.interpret))
                else:
                    print(stat)
    else: 
        print('No tasks')

def interpret_status(stat, interp_dict):
    if stat in interp_dict:
        return interp_dict[stat]
    elif isinstance(stat, tuple):
        s = sum(stat)
        if s in interp_dict:
            return interp_dict[s]
    return 'Undefined status'

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