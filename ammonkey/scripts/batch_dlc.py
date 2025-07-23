'''
a batch processing script to run dlc on all unprocessed data
to use, change:
    1. change target_task
    2. change dp_function to match task
    3. change model regex (re_model)
        -- this can be found by checking DLCModel.final_folder_name
    4. change group_sub_dirs list to match the cameras used (L or LR)
        -- hand is ['R'] and arm is ['L', 'R']
Then run the script directly, in conda env.
Mel
'''

from ammonkey import (
    dataSetup,
    ExpNote, DAET, Path,
    Task, iter_notes, 
    initDlc, createProcessor_Pull,
    createProcessor_BBT, createProcessor_Brkm, createProcessor_TS
)
import re
from ammonkey.utils.silence import silence
import logging
from tqdm import tqdm
import os
import itertools
from typing import Iterator

lg = logging.getLogger(__name__)
lg.setLevel(logging.DEBUG)

p = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
p = Path(p)

target_task = Task.BBT
dp_function = createProcessor_BBT

re_model = re.compile(r'^Pull-LR-\d{7,8}_4480$')
re_model = re.compile(r'^BBT-\d{7,8}_5608$')
group_sub_dirs = ['L', 'R']
group_sub_dirs = ['R']

cutoff_date = 20250315

def cleanSkipFile(p:str | Path):
    P = Path(p)
    SD = P / '.skipDLC'
    flag = False
    for i in P.rglob('*.h5'):
        flag = True

    if not flag and SD.exists():
        os.remove(str(SD))
        lg.warning(f'Cleaned skipDLC in {P.parent.name} {P.name}')

def is_processed_by_model(
        re_model: re.Pattern | str, 
        synced_vid_dir: Path | str, 
        target_h5_count: int = 8
) -> bool:
    synced_vid_dir = Path(synced_vid_dir)
    cleanSkipFile(synced_vid_dir)
    if all(
        [
            (synced_vid_dir / s / '.skipDLC').exists() 
            for s in group_sub_dirs
        ]
    ):      # legacy skip detection
        return True
    
    if not (dlc_dir := synced_vid_dir / 'DLC').exists():
        return False
    
    for model_dir in dlc_dir.iterdir():
        if not re.search(re_model, model_dir.name):
            continue
        h5_count = 0
        for _ in model_dir.glob('*.h5'):
            h5_count += 1
        if h5_count != target_h5_count:
            return False
        else:
            return True
        
    return False

def determine_h5_count(groups: list) -> int:
    return len(groups) * 4

def scan_dlc_unprocessed(note_iterator: Iterator[ExpNote]) -> list[DAET]:
    need_dlc:list[DAET] = []
    
    for note in note_iterator:
        task_types = note.getAllTaskTypes()
        if not note.checkSanity():
            lg.warning(f'{note=}, San={note.checkSanity()}, Tasks={task_types}')

        if not target_task in task_types or int(note.date) < cutoff_date:
            lg.info(f'Skipped {note}')
            continue
        
        if not note.data_path.exists():
            dataSetup(data_path=note.data_path)

        note_filtered = note.applyTaskFilter([target_task])
        for daet in note_filtered.daets:
            if note_filtered.is_daet_void(daet):
                lg.info(f'Skipped void entry {daet}')
                continue

            daet_synced_dir = note_filtered.getDaetSyncRoot(daet)
            if not daet_synced_dir.exists():
                lg.warning(f'{daet} is not synchronized')
                continue
            if not is_processed_by_model(re_model, daet_synced_dir, 
                                        target_h5_count=determine_h5_count(group_sub_dirs)):
                need_dlc.append(daet)

        '''dp = dp_function(note)

        dlc_results = dp.batchProcess()
        lg.debug(dlc_results)'''
    
    return need_dlc

def execute_batch_dlc(note_iterator: Iterator[ExpNote], need_dlc: list[DAET]) -> None:
    dates_need_dlc = {daet.date for daet in need_dlc}
    for note in note_iterator:
            lg.info(f'Stepping {note}')
            if not note.date in dates_need_dlc:
                continue
            
            daet_here = [d for d in need_dlc if d.date == note.date]
            note_filtered = note.dupWithWhiteList(daet_here)
            if not note_filtered.checkSanity():
                lg.error(f'Skipped {note_filtered.date}: sanity check failed')
                continue

            dp = dp_function(note_filtered)

            lg.info(f'Executing DLC on {note_filtered}')
            lg.info(f'Including: {note_filtered.daets}')

            dlc_results = dp.batchProcess()
            lg.info(dlc_results)

def main() -> None:
    notes_iterator = iter_notes(Path(p))
    ni0, ni1 = itertools.tee(notes_iterator, 2)
    need_dlc = scan_dlc_unprocessed(ni0)

    print('='*20, 'Need dlc:', '='*20)
    for daet in need_dlc:
        print(f'{daet}')

    initDlc()
    execute_batch_dlc(ni1, need_dlc)

if __name__  == '__main__':
    main()