'''
a batch processing script to synchronize all unprocessed videos
just set p then directly run it.
(plz also change roi json save path!!)
change debug to True if you just want to see whats not synced.
your precious roi selection data will be saved in json.
'''

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
import json

lg = logging.getLogger(__name__)
lg.setLevel(logging.DEBUG)

p = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
p = Path(p)

group_sub_dirs = ['L', 'R']
target_vid_counts = [2, 4]

cutoff_date = 20250315

notes_iterator = iter_notes(p)
ni0, ni1 = itertools.tee(notes_iterator, 2)

debug = True

need_sync:list[DAET] = []
bad_sanity: list[ExpNote] = []

sl = checkpoints['sync_L']
sr = checkpoints['sync_R']
sk = checkpoints['skipsync']
sc = checkpoints['sync_calib']
dl = checkpoints['dlc_L']
dr = checkpoints['dlc_R']

synchronizers: list[VidSynchronizer] = []

try:
    for note in ni0:
        if int(note.date) < cutoff_date:
            lg.info(f'Skipped ancient note {note}')
            continue
        if not note.checkSanity():
            lg.warning(f'{str(note):50} \033[33msanity check failed\033[0m')
            bad_sanity.append(note)

        if not note.data_path.exists():
            dataSetup(data_path=note.data_path)

        dp = note.data_path

        need_sync = []
        for daet in note.daets:
            if note.is_daet_void(daet):
                lg.info(f'Skipped void entry {daet}')
                continue

            bools = note.checkVideoExistence(daet=daet).values()
            if not all(bools) and sum(bools) not in target_vid_counts:
                lg.warning(f'{daet} videos unhealthy')
                continue

            if daet.isCalib:
                if not (
                    sum(sc.check(dp, daet)) == 4 or
                    sum(sk.check(dp, daet)) == 1 
                ):
                    need_sync.append(daet)
            elif not (
                sum(sl.check(dp, daet)) == 2 and
                sum(sr.check(dp, daet)) == 2
                ) and not (
                sum(sk.check(dp, daet)) == 1 
                ) or not (
                True
            ):
                need_sync.append(daet)

        if not need_sync: 
            lg.info(f'{str(note):50} \033[32mpassed sync check\033[0m')
            continue
        else:
            lg.info(need_sync)

        note_filtered = note.dupWithWhiteList(need_sync)

        vs = VidSynchronizer(note_filtered)
        if not debug:
            vs.setROI()
            if input('Change cam 2 Y/G? [y/g]') == 'y':
                vs.cam_config.led_colors[2] = 'Y'
            else:
                vs.cam_config.led_colors[2] = 'G'

        synchronizers.append(vs)
finally:
    rois = {}
    for vs in synchronizers:
        rois[vs.notes.date] = vs.cam_config.rois
    with open('C:/Users/mkrig/Documents/Python Scripts/all_rois_temp.json', 'w') as f:
        json.dump(rois, f, indent=4) 

lg.info('='*40)
lg.info(f'collected synchronizers * {len(synchronizers)}')
lg.info('='*40)
lg.info('Dates need sync:')

rois = {}
for vs in synchronizers:
    rois[vs.notes.date] = vs.cam_config.rois
    lg.info(f'\t{vs.notes}')
    dp = vs.notes.data_path
    for daet in vs.notes.daets:
        lg.info(f'\t\t{str(daet):35} [sl:{sl.check(dp, daet)}, sr:{sr.check(dp, daet)}, sk:{sk.check(dp, daet)}]')

if bad_sanity:
    lg.info('='*40)
    lg.info('Sanity check failed notes')
    lg.info('These are skipped during scanning')
    lg.info(set(n.date for n in bad_sanity))
    lg.info('='*40)
    for note in bad_sanity:
        lg.info(f'\t{note}')
        for daet in note.daets:
            vs = note.getVidSetIdx(daet=daet)
            ve = note.checkVideoExistence(daet=daet)
            if not any([v is None for v in vs]) and sum(ve.values()) == 4:  #FIXME hardcoded
                continue
            lg.info(f'\t\t{str(daet):35} [VS:{note.getVidSetIdx(daet=daet)}, VE:{note.checkVideoExistence(daet=daet)}]')

# print(rois)
with open('C:/Users/mkrig/Documents/Python Scripts/all_rois.json', 'w') as f:
    json.dump(rois, f, indent=4) 

if not debug:
    for vs in synchronizers:
        lg.info(vs.notes.date)
        lg.info(vs.notes.daets)
        vs.config.override_existing = True
        results = vs.syncAll(skip_existing=False)
        print(results)
