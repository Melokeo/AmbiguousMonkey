from ammonkey import (
    dataSetup,
    ExpNote, DAET, Path,
    Task, iter_notes, 
    VidSynchronizer,
)
from ammonkey.utils.silence import silence
from ammonkey.utils.statusChecker import checkpoints

import re
import logging
from tqdm import tqdm
import os
import itertools

lg = logging.getLogger(__name__)
lg.setLevel(logging.DEBUG)

p = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
p = Path(p)

re_model = re.compile(r'^Pull-LR-\d{7,8}_4480$')
group_sub_dirs = ['L', 'R']
target_vid_counts = [2, 4]

cutoff_date = 20250315


notes_iterator = iter_notes(p)
ni0, ni1 = itertools.tee(notes_iterator, 2)

need_sync:list[DAET] = []

for note in ni0:
    if int(note.date) < cutoff_date:
        lg.info(f'Skipped ancient note {note}')
        continue
    if not note.checkSanity():
        lg.warning(f'{note} sanity check failed')

    sl = checkpoints['sync_L']
    sr = checkpoints['sync_R']
    sk = checkpoints['skipsync']
    dl = checkpoints['dlc_L']
    dr = checkpoints['dlc_R']
    dp = note.data_path

    for daet in note.daets:
        if note.is_daet_void(daet):
            lg.info(f'Skipped void entry {daet}')
            continue

        bools = note.checkVideoExistence(daet=daet).values()
        if not all(bools) and sum(bools) not in target_vid_counts:
            lg.warning(f'{daet} videos unhealthy')
            continue
        if not note.data_path.exists():
            dataSetup(data_path=note.data_path)

        if not (
            sum(sl.check(dp, daet)) == 2 and
            sum(sr.check(dp, daet)) == 2 and 
            sum(sk.check(dp, daet)) == 1 
            ) or not (
            True
        ):
            vs = VidSynchronizer(note)
            vs.setROI()
            if input('Change cam 2 Y/G? [y/g]') == 'y':
                vs.cam_config.led_colors[2] = 'Y'
            else:
                vs.cam_config.led_colors[2] = 'G'
 
            results = vs.syncAll()
            print(results)
            need_sync.append(daet)

print('='*20, 'Need sync:', '='*20)
for daet in need_sync:
    print(f'{daet}')