'''
A Great Unity of monkey task pipeline
Run this in cmd with `conda activate monkeyUnity`
Mel
Feb 2025

Mostly refactored
June 2025
'''

import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path

import filecmp
import json
import pandas as pd

from platform import system
if system() == 'Windows':
    import win32com.client

from .utils import VidSyncLED as Sync
from .utils import VidSyncAud as SyncAud
from .utils.log import Wood
from .utils.silence import silence
from .utils.PathManager import PathMngr
    
class Task(Enum):
    All = auto()
    TS = auto()
    BBT = auto()
    BRKM = auto()
    Pull = auto()
    Calib = auto()

BASE_DIR = os.path.dirname(__file__)
# print(BASE_DIR)
debugging = False
pstart_time = time.time()
ystd = datetime.today() - timedelta(days=1)
today = datetime.now().strftime('%Y%m%d')
PPATH_RAW = os.path.join(
    r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici',
    ystd.strftime('%Y'),
    ystd.strftime('%m'),
    ystd.strftime('%Y%m%d'),
    )
if not os.path.exists(PPATH_RAW):
    PPATH_RAW = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\04\20250403'
                         # path of default raw data (eg P:\....02\05\20250205\). keep the r in front.
                         
with silence(): # suppress init output
    pm = PathMngr(PPATH_RAW)
ANIMALS = ['Pici']
PATH_ANI_CFG = ''
PATH_ANI_CALIB = ''
HEADER_KEY = 'Experiment'#'Video # From' #'Task'
ROIs = {1: [550, 148, 75, 71], 2: [1277, 29, 119, 67], 3: [864, 302, 84, 77], 4: [1031, 379, 105, 71]}
ROIs = {1: [462, 30, 359, 271], 2: [159, 5, 288, 217], 3: [531, 110, 395, 334], 4: [882, 284, 317, 338]}
LEDs = {1: "Y", 2: "G", 3: "G", 4: "G"}
THRES = 175
THRES_ERROR = 5    # max tolerable error b/w audio and LED sync results
OUTPUT_SIZE = [1920, 1080]
CAM_OFFSETS = {1: 0, 2: 459, 3: 567, 4: 608}
ani_cfg_mothercopy = os.path.join(BASE_DIR, 'config.toml')
ani_cfg_mothercopy_add_ref = r"C:\Users\rnel\Documents\Python Scripts\config-ref.toml"
ani_calib_mothercopy = os.path.join(BASE_DIR, 'calibration.toml')
ani_env_name = 'anipose-3d'
Colab_path = r'G:\My Drive\MonkeyModels'
model_path_colab = {'L': r'G:\My Drive\MonkeyModels\TS-L-shaved', 'R': r'G:\My Drive\MonkeyModels\TS-R-shaved'}
camL = [1, 2]
camR = [3, 4]
ncams = 4
hascam = [True] * ncams
list_skipped_file_name = ['x', '-']
pause_before_sync = True
pause_before_dlc = True
pm.dlc_mdl_path = {
    'L': r'D:\DeepLabCut\TS-L-shaved-N',
    'R': r'D:\DeepLabCut\TS-R-shaved-N',
}
vid_type = 'mp4'
base_header = ['Experiment Number', 'Experiment', 'Task', 'VOID']
xlsx_cam_header = ['Camera files \n(1 LR)','Camera files \n(2 LL)', 'Camera files (3 RR)', 'Camera files (4 RL)']
first_run = True
filename_cam_head = ['x','x','x','x']
curr_task = Task.All
task_match = {  # all should be lowercase
    Task.BBT: ['bbt'],
    Task.BRKM: ['brkm', 'brnk', 'kman'], # you wont misspell it, right??
    Task.Pull: ['pull', 'puul'],    # yes, someone once typed puul
    Task.TS: ['touchscreen', 'touch screen', 'ts'],
    Task.Calib: ['calib'],
    Task.All: ['']
}

if __name__ != '__main__':
    module_path = os.path.dirname(__file__)
    cfg_path = os.path.join(module_path, 'cfgs')
    ani_cfg_mothercopy = os.path.join(cfg_path, 'config.toml')
    ani_calib_mothercopy = os.path.join(cfg_path, 'calibration.toml')

def updateOffset(cam_filename):
    for i in range(2, 5):
        if cam_filename[i-1] != -1:
            CAM_OFFSETS[i] = cam_filename[i-1] - cam_filename[0]
        else:
            CAM_OFFSETS[i] = -1

def dataSetup():
    """
    Creates necessary data directories for processing based on pm.data_path.
    Automatically uses pm.PPATH_RAW
    """
    print(pm.animal, pm.date) 
    # make folders
    # if not os.path.exists(data_path):
    if True: #input(f'Will set up folder in {data_path}, input y to continue: ') == 'y':
        os.makedirs(pm.data_path, exist_ok = True)
        sub_dir = [
            '\\SynchronizedVideos',
            '\\anipose',
            '\\SynchronizedVideos\\SyncDetection',
            '\\clean'
            ]
        for sd in sub_dir:
            os.makedirs((pm.data_path + sd), exist_ok = True)
    else:
        # raise RuntimeError('Then why do you run this script??')
        pass

def _infoFromPath(PPATH_RAW):
    path = Path(PPATH_RAW)
    pt = path.parts
    date = pt[-1]
    animal = next((p for p in pt if p in ANIMALS), None)
    if animal == None:
        raise ValueError(f'Check animal name raw path. Recognized names: {ANIMALS}')
    return animal, date

def readExpNote(PPATH_RAW=None, header=base_header+xlsx_cam_header, HEADER_KEY='Experiment', TASK_KEY='')->pd.DataFrame:
    """
    Reads experiment notes from the corresponding Excel file.
    Args:
        PPATH_RAW (str, optional): Path to raw data folder. Defaults to pm.PPATH_RAW.
        header (list, optional): Columns to extract from the Excel file.
        HEADER_KEY (str, optional): Keyword to identify header row.
        TASK_KEY (str, optional): Filter for specific tasks.
    Returns:
        pd.DataFrame: Filtered experiment data.
    Usage:
        df = readExpNote()
    """
    PPATH_RAW = PPATH_RAW or pm.PPATH_RAW
    animal, date = _infoFromPath(PPATH_RAW)
    xlsx_path = f'{PPATH_RAW}\\{animal}_{date}.xlsx'
    df = pd.read_excel(xlsx_path, header = None)
    # print(df)
    header_idx = df[df.apply(
        lambda row: row.astype(str).str.contains(HEADER_KEY, case = True, na = False).any(), axis = 1
        )].index[0]
    df = pd.read_excel(xlsx_path, header = header_idx)
    df = df[header]
    df = df[df['Task'].astype(str).str.contains(TASK_KEY, case = False, na = False)]
    print(f'\nFetched record from {xlsx_path}\n{df}')
    return df

def getTasksInDAET(PPATH_RAW=None, HEADER_KEY:str='Experiment', task:Task=Task.All, skip_void=False) -> list[str]:
    '''helper function: read exp note & return tasks in daet list'''
    PPATH_RAW = PPATH_RAW or pm.PPATH_RAW
    animal, date = _infoFromPath(PPATH_RAW)
    df = getTasksInDict(PPATH_RAW, HEADER_KEY, task, skip_void)
    if df is None:
        print(f'Found nothing when getting daets for {os.path.basename(PPATH_RAW)}')
        return None
    # return experiment-task str
    return [f'{date}-{animal}-{e}-{t}' for e,t in zip(df['Experiment'], df['Task'])]

def getTasksInDict(PPATH_RAW=None, HEADER_KEY:str='Experiment', task:Task=Task.All, skip_void=False) -> list[str]:
    '''helper function: read exp note & return tasks
    Returns:
        df[['Experiment', 'Task']]
    '''
    PPATH_RAW = PPATH_RAW or pm.PPATH_RAW
    animal, date = _infoFromPath(PPATH_RAW)
    xlsx_path = f'{PPATH_RAW}\\{animal}_{date}.xlsx'
    try:
        df = pd.read_excel(xlsx_path, header = None)
    except FileNotFoundError:
        print(f'getTasks() fileNotFoundErr: {xlsx_path}')
        return None
    # print(df)
    header_idx = df[df.apply(
        lambda row: row.astype(str).str.contains(HEADER_KEY, case = True, na = False).any(), axis = 1
        )].index[0]
    df = pd.read_excel(xlsx_path, header = header_idx)
    if skip_void and 'VOID' in df.columns:
        df = df[df['VOID'] != True]
    try:
        df = df[['Experiment', 'Task']]
    except KeyError:
        print("KeyError reading tasks with ['Experiment', 'Task']")
        return None
    
    # --filter tasks--
    pattern = '|'.join(re.escape(k) for k in task_match[task])
    df = df[df['Experiment'].astype(str).str.contains(pattern, case = False, na = False)]
    # print(df)

    return df

def getVideoSets(PPATH_RAW=None, cam_header=xlsx_cam_header) -> dict[str,list[int]]:
    PPATH_RAW = PPATH_RAW or pm.PPATH_RAW
    animal, date = _infoFromPath(PPATH_RAW)
    xlsx_path = f'{PPATH_RAW}\\{animal}_{date}.xlsx'
    daets = getTasksInDAET(PPATH_RAW)
    try:
        df = pd.read_excel(xlsx_path, header = None)
    except FileNotFoundError:
        print(f'getVideoSets() fileNotFoundErr: {xlsx_path}')
        return None
    
    header_idx = df[df.apply(
        lambda row: row.astype(str).str.contains(HEADER_KEY, case = True, na = False).any(), axis = 1
        )].index[0]
    df = pd.read_excel(xlsx_path, header = header_idx)
    
    vid_dict = {}
    try:
        for _, r in df.iterrows():
            vid_set: list[int] = []
            daet = f"{date}-{animal}-{r['Experiment']}-{r['Task']}"
            if not daet in daets:
                print(f'Unexpected task {daet}')
            for i in range(ncams):
                vid_id = r[cam_header[i]]
                if (vid_id in list_skipped_file_name) or vid_id=='NaN':
                    vid_set.append(None)
                else:
                    try:
                        vid_id = int(vid_id)
                    except ValueError:        # people write everything in the notes
                        print(f'cam{i} video cell {vid_id} is not valid')
                        vid_set.append(None)
                    else:
                        vid_set.append(vid_id)
            
            # append dict and check how many vid_id we have
            vcount = sum([1 for vid in vid_set if vid])
            if daet in vid_dict.keys():   # warn if multiple entries have same daet
                print(f'[warning] Multiple {daet} entries')
            if vcount == ncams:
                vid_dict[daet] = vid_set
            elif vcount == 0:
                vid_dict[daet] = None
                print(f"[warning] No valid video for {daet}")
            else:
                vid_dict[daet] = vid_set
                print(f'[warning] Missing {ncams-vcount} videos in the notes for {daet}')

    except KeyError as e:
        print(f'Key error when reading video sets: {e}')
        return None
    
    return vid_dict

def checkVideoExistence(PPATH_RAW=None, vid_dict:dict=None) -> dict[str,list[bool]]:
    if not vid_dict: return
    PPATH_RAW = PPATH_RAW or pm.PPATH_RAW
    existence_dict = {}
    for daet, vid_set in vid_dict.items():
        existence = []
        if not vid_set:
            continue
        for i, vid_id in enumerate(vid_set):
            if not vid_id or vid_id < 0: 
                continue
            vid_filename        = f'C{str(vid_id).zfill(4)}.{vid_type}'
            alt_vid_filename    = f'C{str(vid_id).zfill(5)}.{vid_type}'
            target = os.path.join(PPATH_RAW, f'cam{i+1}', vid_filename)  
            alt_target = os.path.join(PPATH_RAW, f'cam{i+1}', alt_vid_filename)  # if we have C00123.mp4
            if os.path.exists(target):
                existence.append(True)
            else:
                if  os.path.exists(alt_target):
                    print(f'[warning] found a file with 5-zero padding')
                    existence.append(True)
                else:
                    print(f'Specified video cannot be found: {target}')
                    existence.append(False)

        existence_dict[daet] = existence

    return existence_dict

def configSync(base_header=base_header, cam_header=xlsx_cam_header, override_skip=False, aud_test_len=60, task:Task=None):
    '''calls syncLED and syncAud'''
    task = task or curr_task
    h = base_header + cam_header
    df = readExpNote(pm.PPATH_RAW, header = h)
    vid_path = []
    cfg_path = []
    calib_idx = []
    starts_aud = [] # stores audio sync info for comparison
    animal, date = pm.animal, pm.date
    
    # log
    wood = Wood(pm.data_path)
    wood.start(step='ConfigSync',details=f'SYNC[{aud_test_len=}{", OverrideSkip" if override_skip else ""}] | {task=}')

    for _, row in df.iterrows():
        experiment, task = str(row["Experiment"]), str(row["Task"]).replace(' ', '')
        if row['VOID'] == 'T':
            print(f'Void trial skipped: {experiment}, {task}')
            continue        # allows u to skip a trial
        if task != Task.All and not any([sub in experiment.lower() for sub in task_match[task]]):
            print(f'Less interesting task skipped: {experiment}, {task}')
            continue

        vid_idx = []
        try:        # check we have enough videos to proceed & get the vid index
            missing_count = 0
            for i in range(ncams):
                cam_num = row[cam_header[i]]
                if cam_num in list_skipped_file_name or cam_num=='NaN':
                    # camoff.append(-1)
                    # print(f'Missing video in {experiment}-{task} cam{i+1}')
                    missing_count += 1
                    vid_idx.append(-1)
                    continue
                else:
                    vid_idx.append(cam_num)
            if missing_count >= 3:
                print(f'Crucial missing videos in {experiment}-{task}!')
                continue # to next row
        except Exception as e:
            print(f'Error when fetching video file names from xlsx. Check header. Msg: {e}')
            # exit('We dont know why but have to exit')
            return

        calib = True if "calib" in experiment.lower() else False
        task_root_path = os.path.join(pm.data_path, 'SynchronizedVideos', f'{date}-{animal}-{experiment}-{task}') 
        sync_config_path = os.path.join(task_root_path, f"sync_config_{experiment}_{task}.json")

        vid_path.append(task_root_path)             # global var pointing to task root folders
        cfg_path.append(sync_config_path)
        if calib:
            calib_idx.append(len(vid_path) - 1)
            os.makedirs(os.path.join(task_root_path), exist_ok = True)
        else:
            os.makedirs(os.path.join(task_root_path, 'L'), exist_ok = True)
            os.makedirs(os.path.join(task_root_path, 'R'), exist_ok = True)
        
        if os.path.exists(task_root_path) and os.path.exists(os.path.join(task_root_path,'.skipDet')):
            if override_skip:
                print(f'Will overwrite sync results {os.path.basename(task_root_path)}...')
            else:
                print(f'Start frames are already detected in {os.path.basename(task_root_path)}, skipped')
                starts_aud.append([])
                continue

        print(f'Testing start frame for {experiment}-{task}...')

        vids = []
        for cam in range(1, ncams+1):
            cam_folder = os.path.join(pm.PPATH_RAW, f"cam{cam}")
            n = int(vid_idx[cam-1])
            if n == -1:     # we ensured at least 2 vids previously
                continue

            cam_vid_name = f"C{n:04}.mp4"
            cam_video_path = os.path.join(cam_folder, cam_vid_name)
            
            vids.append(cam_video_path)

        try:
            sync_results = SyncAud.sync_videos(vids, fps=119.88, duration=aud_test_len, start=0)
            SyncAud.save_synced_waveforms(sync_results, sr=48000, fps=119.88, duration=10, tgt_path=os.path.join(pm.data_path, 'SynchronizedVideos\\SyncDetection'))
            starts_aud.append([i[-1] for i in sync_results.values()])
        except Exception as e:
            raise RuntimeError(f'Error in SyncAud: {e}')
    print(vid_path)
    print(cfg_path)
    print(starts_aud)

    print('Audio sync complete. Now detecting LED frames...')
    valid_row_idx = -1
    for _, row in df.iterrows():            # YES. here copied the loop above
        experiment, task = str(row["Experiment"]), str(row["Task"]).replace(' ', '')
        if row['VOID'] == 'T':
            print(f'Void trial skipped: {experiment}, {task}')
            continue        # allows u to skip a trial
        if task != Task.All and not any([sub in experiment.lower() for sub in task_match[task]]):
            print(f'Less interesting task skipped: {experiment}, {task}')
            continue

        valid_row_idx += 1

        vid_idx = []
        try:        # check we have enough videos to proceed & get the vid index
            missing_count = 0
            for i in range(ncams):
                cam_num = row[cam_header[i]]
                if cam_num in list_skipped_file_name or cam_num=='NaN':
                    # camoff.append(-1)
                    # print(f'Missing video in {experiment}-{task} cam{i+1}')
                    missing_count += 1
                    vid_idx.append(-1)
                    continue
                else:
                    vid_idx.append(cam_num)
            if missing_count >= 3:
                print(f'Crucial missing videos in {experiment}-{task}!')
                continue # to next row
        except Exception as e:
            print(f'Error when fetching video file names from xlsx. Check header. Msg: {e}')
            # exit('We dont know why but have to exit')
            return

        calib = True if "calib" in experiment.lower() else False
        task_root_path = vid_path[valid_row_idx] 
        sync_config_path = cfg_path[valid_row_idx]      # though indexing with intermediate, the two mainloops should enter in same order
        
        if os.path.exists(task_root_path) and os.path.exists(os.path.join(task_root_path,'.skipDet')):
            if override_skip:
                print(f'Will overwrite {os.path.basename(task_root_path)}...')
            else:
                print(f'Start frames are already detected in {os.path.basename(task_root_path)}, skipped')
                continue

        print(f'Testing start frame for {experiment}-{task}...')

        sync_param = [] # storing info for sync, every set of videos

        # here is main loop to test LED frames for one row
        for cam in range(1, ncams+1):
            cam_folder = os.path.join(pm.PPATH_RAW, f"cam{cam}")    # TODO change to configurable regex
            n = int(vid_idx[cam-1])
            if n == -1:     # we ensured at least 2 vids previously
                continue

            cam_vid_name = f"C{n:04}.mp4"
            cam_video_path = os.path.join(cam_folder, cam_vid_name)

            if not calib:
                if cam in camL:
                    new_video_name = 'L\\' + f"{date}-{animal}-{experiment}-{task}-cam{cam}.mp4"
                elif cam in camR:
                    new_video_name = 'R\\' + f"{date}-{animal}-{experiment}-{task}-cam{cam}.mp4"
            else:   # calibration has other logic
                new_video_name = f"{date}-{animal}-{experiment}-{task}-cam{cam}.mp4"
            
            # here testing start frame based on LED
            if os.path.exists(cam_video_path):
                if not calib:
                    try:
                        start_frame = Sync.find_start_frame(
                            cam_video_path, ROIs[cam], THRES, LEDs[cam],os.path.join(pm.data_path,'SynchronizedVideos\\SyncDetection'))
                    except Exception as e:
                        raise RuntimeError(f'Error in SyncLED: {e}')
                else: 
                    start_frame = -1
                sync_param.append({
                    "path": cam_video_path,
                    "roi": ROIs[cam],
                    "LED": LEDs[cam],
                    "start": start_frame,
                    "output_name": new_video_name
                })
            else:
                raise FileNotFoundError(
                    f"Failed when looking for start frame: expected video {cam_video_path} of cam{cam} not found.")
            
        # Cross-validation w/ audio sync
        starts = [i['start'] for i in sync_param]
        print(f'Start frames: {starts}')
        sa = starts_aud[valid_row_idx]
        assert len(sa)>0, f'There must be sth wrong in skipping mechanism with {experiment}, {task}'
        # print(starts, sa)
        starts, status = syncCrossValidation(starts=starts, starts_aud=sa)

        wng = {-1: "Two videos missing and two other valid ones deviate. Skipping trial.",
               -2: "Two or more videos deviate from audio sync. Skipping trial.",
               }
        if starts is None:
            print(f'[Warning] {wng[status]}')
            continue

        # Update cam_videos with corrected start frames
        for i in range(len(sync_param)):
            sync_param[i]['start'] = starts[i]
        print(f'Corrected start frames: {starts}')
    
        # Write config.json for this set of videos
        config = {
            "videos": sync_param,
            "threshold": THRES,
            "output_size": OUTPUT_SIZE,
            "output_dir": task_root_path,
            "detected": "T"
        }
    
        with open(sync_config_path, "w") as f:
            json.dump(config, f, indent=4)
    
        # empty .skip file to mark the folder as already processed
        with open(os.path.join(task_root_path, '.skipDet'), 'w') as f:  
            pass
    
    wood.done('ConfigSync')
    return vid_path, cfg_path, calib_idx

def syncCrossValidation(starts: list, starts_aud: list):
    '''Compute offset estimate from valid LED starts'''
    assert len(starts)==len(starts_aud), 'starts and starts_aud must have same length'

    valid_idx = [i for i, s in enumerate(starts) if s != -1]
    if valid_idx:
        offsets = [starts[i] - starts_aud[i] for i in valid_idx]
        offset_est = sorted(offsets)[len(offsets)//2]  # median offset
    else:
        offset_est = 0  # default; will be overridden in 4-missing case

    missing_idx = [i for i, s in enumerate(starts) if s == -1]
    num_missing = len(missing_idx); print(0)
    
    if len(starts)<4:
        if len(starts) - num_missing < 2:
            return starts_aud, None
        else:
            deviations = [abs(starts[i] - (offset_est + starts_aud[i])) for i in range(2)]
            num_deviations = sum(dev > THRES_ERROR for dev in deviations)
            if len(starts) - num_missing - num_deviations < 2:
                return None, -2
            else:
                for i in range(len(starts)):
                    if abs(starts[i] - (offset_est + starts_aud[i])) > THRES_ERROR:
                        starts[i] = offset_est + starts_aud[i]
                return starts, None

    if num_missing > 0:
        print(1)
        if num_missing == 1:
            # 1 missing: fill it from audio sync
            for i in missing_idx:
                starts[i] = offset_est + starts_aud[i]
                deviations = [abs(starts[i] - (offset_est + starts_aud[i])) for i in range(4)]
                num_deviations = sum(dev > THRES_ERROR for dev in deviations)
                if num_deviations == 1:
                    print('Warning: 1 missing start and 1 deviation found')
                    for i in range(4):
                        if abs(starts[i] - (offset_est + starts_aud[i])) > THRES_ERROR:
                            starts[i] = offset_est + starts_aud[i]
                elif num_deviations > 1:
                    print(f'Start LED {starts}; start audio {starts_aud}')
                    print(f'Valid index {valid_idx}; Missing index {missing_idx}, deviations {deviations}')
                    return None, -1
        elif num_missing == 2:
            # Check if valid ones are within threshold
            deviations = [abs(starts[i] - (offset_est + starts_aud[i])) for i in valid_idx]
            if all(dev <= THRES_ERROR for dev in deviations):
                for i in missing_idx:
                    starts[i] = offset_est + starts_aud[i]
            else:
                print(f'Start LED {starts}; start audio {starts_aud}')
                print(f'Valid index {valid_idx}; Missing index {missing_idx}, deviations {deviations}')
                print("Warning: Two videos missing and valid ones deviate. Skipping trial.")
                return None, -1
        elif num_missing == 3:
            print("Warning: Three videos missing start detection. Filling missing with the only valid start.")
            for i in missing_idx:
                starts[i] = offset_est + starts_aud[i]
        elif num_missing == 4:
            print("Warning: All videos missing LED start detection. Filling with audio sync and shifting to ensure >=1.")
            starts = [offset_est + s_aud for s_aud in starts_aud]
            min_start = min(starts)
            if min_start < 1:
                shift = 1 - min_start
                starts = [s + shift for s in starts]
    else:
        # No missing: check deviations for each video
        deviations = [abs(starts[i] - (offset_est + starts_aud[i])) for i in range(4)]
        num_deviations = sum(dev > THRES_ERROR for dev in deviations)
        if num_deviations == 1:
            for i in range(4):
                if abs(starts[i] - (offset_est + starts_aud[i])) > THRES_ERROR:
                    starts[i] = offset_est + starts_aud[i]
        elif num_deviations >= 2:
            return None, -2
    
    return starts, None


def syncVid(vid_path, cfg_path):
    try:
        for i in range(0, len(cfg_path)):
            if not os.path.exists(os.path.join(vid_path[i],'.skipSync')):
                with open(cfg_path[i]) as f:
                    Sync.process_videos(json.load(f))
                with open(os.path.join(vid_path[i], '.skipSync'), 'w') as f:  
                    pass
            else:
                print(f'Videos are already cooked in {vid_path[i]}, skipped')
    except Exception as e:
        raise RuntimeError(f"Failed synchronizing videos: {e}")

    print('=====Videos synchronized=====\n')

def runDLC(vid_path, shuffle=None, side=None):
    # DLC part. Can anyone send me the Dirt Rally DLCs??
    import deeplabcut # type: ignore
    print('DeepLabCut now loaded')
    # better logic needed here
    wood = Wood(pm.data_path)
    wood.start('DLC')

    if shuffle is None:
        shuffle = {'L':1, 'R':1}
        # shuffle = [1, 1]
    if side is None:
        side  = ['L', 'R']

    for i, vid in enumerate(vid_path):
        if i in pm.calib_idx:
            continue        # you dont want yourself to be tracked

        print(f'\nDLC analyzing {os.path.basename(vid)}...')
        try:
            for p in side:
                if not os.path.exists(os.path.join(vid, p, '.skipDLC')):
                    print('=================NEW DLC ANAL=================\n(not *that* anal)')
                    deeplabcut.analyze_videos(
                        pm.dlc_cfg_path[p], 
                        os.path.join(vid,p), 
                        videotype=vid_type,           
                        #trainingsetindex=,    
                        shuffle=shuffle[p],
                        cropping=None,
                        # dynamic=(True, 0.5, 10),         #TODO and make this configurable
                        auto_track=False,
                        engine=deeplabcut.Engine.TF,
                        )
                    with open(os.path.join(vid, p, '.skipDLC'), 'w') as f:  
                        pass
                else:
                    print(f'Videos are already screwed in {vid}\\{p}, skipped\n')
        except Exception as e:
            raise RuntimeError(f'Main script: Failed in DLC analyse:\n{e}')
        for p in side:
            deeplabcut.filterpredictions(
                pm.dlc_cfg_path[p], 
                os.path.join(vid,p), 
                shuffle = shuffle[p],
                save_as_csv=True,
                videotype=vid_type,
                filtertype="median",
                #filtertype="arima",
                #p_bound=0.01,
                #ARdegree=3,
                #MAdegree=1,
                #alpha=0.01
                )
            # deeplabcut.create_labeled_video(dlc_cfg_path[p], os.path.join(vid,p), videotype = vid_type, draw_skeleton = True)
    print('=====2D analyse finished=====\nDLC is happy. Are *you* happy?\n')
    wood.done('DLC')

def copyToGoogle(vid_path):
    kids = []
    for vid in vid_path:
        if "calib" in vid.lower():
            continue
        try:
            for p in ['L', 'R']:
                if not os.path.exists(os.path.join(vid, p, '.inColab')):
                    pth = Path(vid)/p
                    for f in pth.glob('*.mp4'):
                        fr = str(f.resolve())
                        fr = fr.replace(r'\\share.files.pitt.edu\RnelShare', 'P:')
                        shutil.copy(fr, os.path.join(model_path_colab[p], 'videos'))
                        b = os.path.basename(fr)
                        kids.append(os.path.join(model_path_colab[p], 'videos', b.split('.mp4')[0]))
                        print(f'Sent {kids[-1]} to Google Drive')
                    with open(os.path.join(vid, p, '.inColab'), 'w'):
                        pass
                else:
                    print(f'Skipped copied files {vid}/{p}')
        except Exception as e:
            raise e        
    return kids # cuz i think it's like sending kids to school

def pickupFromGoogle(animal, date):
    for p in ['L','R']:
        pth = Path(model_path_colab[p])/'videos'
        print(f'Seeking h5 in {str(pth.resolve())}')
        for f in pth.glob('*_filtered.h5'):
            fr = str(f.resolve())
            fr_sub = re.sub('DLC_resnet(101|50)_(TS|BBT)-(L|R).*shuffle1_\d+0000_filtered','',fr)
            fr_cam = re.search('-cam\d\.h5',fr_sub).group().replace('.h5', '')
            home = os.path.join(pm.data_path, 'SynchronizedVideos', os.path.basename(fr_sub).split('-cam')[0], p)
            if not os.path.exists(os.path.join(home, '.fromColab')):
                valid_cam = (int(fr_cam[-1]) in camL) if p=='L' else (int(fr_cam[-1]) in camR)
                if valid_cam and date in fr and animal in fr:
                    home = os.path.join(pm.data_path, 'SynchronizedVideos', os.path.basename(fr_sub).split('-cam')[0], p)          
                    try:
                        shutil.copy(fr, home)   # Keep _filtered in name to meet detection criteria in setupAnipose()
                        with open(os.path.join(home, '.skipDLC'), 'w') as f:
                            pass
                        print(f'Pickep up {os.path.basename(fr)} from Google Drive')
                    except Exception as e:
                        raise ValueError(f'Failed when copying {fr} from google drive:\n{e}')
                else:
                    print(f'Trashed {os.path.basename(fr)}, {fr_cam}, {valid_cam}')
                #with open(os.path.join(home, '.fromColab'), 'w') as f:
                            #pass
            else:
                print(f'Skipped copied folder {home}')

# Now organize everything for anipose.
def setupAnipose(ani_base_path, vid_path, ignore_sync=True):
    """
    Organizes the data structure for Anipose 3D pose estimation.
    Args:
        ani_base_path (str): Path to the anipose project folder.
        vid_path (list): Paths to synchronized video folders.
        Ref (list, optional): Reference points for calibration (default: Ref).
        add_ref (bool, optional): Whether to add reference points.
    """
    print('\nOrganizing for anipose')
    mc = ani_cfg_mothercopy
    shutil.copy(mc, os.path.join(ani_base_path, 'config.toml'))
    for vid in vid_path:
        if not os.path.exists(os.path.join(vid,'.skipSync')):
            if not ignore_sync:
                raise ValueError(f'Folder not marked as synchronized:\n{vid}')
            else:
                print(f'Folder not marked as synchronized:\n{vid}')
                continue
        trial_path = os.path.join(ani_base_path, os.path.basename(vid))
        os.makedirs(os.path.join(trial_path, 'calibration'), exist_ok = True)
        shutil.copy(ani_calib_mothercopy, os.path.join(trial_path, 'calibration', 'calibration.toml'))
        
        os.makedirs(os.path.join(trial_path, 'videos-raw'), exist_ok = True)    
        os.makedirs(os.path.join(trial_path, 'pose-2d-filtered'), exist_ok = True)
        for pos in ['L', 'R']:
            p = Path(vid) / pos
            for f in p.glob('*.mp4'):
                fr = str(f.resolve())
                fr = fr.replace(r'\\share.files.pitt.edu\RnelShare', 'P:')
                if not os.path.exists(os.path.join(trial_path, 'videos-raw', f.name)):
                    shutil.copy(fr, os.path.join(trial_path, 'videos-raw')) # copying is super inefficient
            for f in p.glob('*_filtered.h5'):
                # shutil.move(f.resolve(), os.path.join(trial_path, 'pose-2d-filtered'))
                cam = str(f.resolve())
                cam = int(cam.split('DLC_resnet')[0][-1])
                out_path = f.name
                out_path = os.path.join(trial_path, 'pose-2d-filtered', out_path)
                out_path = re.sub('DLC_resnet(101|50)_(TS|BBT).*shuffle\d{1,2}_\d+0000_filtered','',out_path)
                fr = str(f.resolve())
                fr = fr.replace(r'\\share.files.pitt.edu\RnelShare', 'P:')
                shutil.copy(fr, out_path)
                print(f'h5 copied {os.path.basename(fr)}')
    
def runAnipose(ani_base_path:str=None, run_combined = False):
    """
    Runs Anipose pipeline for triangulation and visualization.
    Args:
        ani_base_path (str): Path to the anipose project folder.
        run_combined (bool): If True, runs 'label-combined' after triangulation.
    """
    ani_base_path = pm.ani_base_path if not ani_base_path else ani_base_path
    wood = Wood(pm.data_path)
    wood.start('anipose')
    try:
        print('Activating new conda env, could take a while...')
        cmd = ['conda', 'activate', ani_env_name, '&&', 'P:', '&&', 'cd', ani_base_path, '&&', 'anipose', 'triangulate', '&&', 'anipose', 'label-3d']
        subprocess.run(cmd, shell=True, check=True)
        #if input('Run label-combined? y/[n]:') == 'y':
        if run_combined:
            cmd = ['conda', 'activate', 'anipose_3d', '&&',
                    'P:', '&&', 'cd', ani_base_path, '&&',
                    'anipose', 'label-combined', '--start', '0.5', '--end', '0.6']
            result = subprocess.run(cmd, shell=True, check=True)
            print(result.stderr)
        else:
            return
    except Exception as e:
        raise RuntimeError(f'Failed in anipose analysing: {e}')
    finally:
        wood.done('anipose')

def two_way_shortcuts(path1, path2):
    """Creates two-way shortcuts"""
    if not system() == 'Windows':
        return
    shell = win32com.client.Dispatch("WScript.Shell")
    
    # Define shortcut paths
    shortcut1_path = os.path.join(path1, os.path.basename(path2) + ".lnk")
    shortcut2_path = os.path.join(path2, os.path.basename(path1) + ".lnk")

    # Create shortcut from path1 → path2
    shortcut1 = shell.CreateShortcut(shortcut1_path)
    shortcut1.TargetPath = path2
    shortcut1.WorkingDirectory = path2
    shortcut1.Save()

    # Create shortcut from path2 → path1
    shortcut2 = shell.CreateShortcut(shortcut2_path)
    shortcut2.TargetPath = path1
    shortcut2.WorkingDirectory = path1
    shortcut2.Save()

    print(f"Shortcut created: {shortcut1_path} → {path2}")
    print(f"Shortcut created: {shortcut2_path} → {path1}")

def sendToCalib(vid_path_: str, folder_name='Calib'):
    '''for vp, f in vid_path_, folder_name:
            fname = os.path.join(pm.ani_base_path, f, 'calibration')
            os.makedirs(fname, exist_ok=True)
            for v in os.listdir(vp):
                if vid_type in v:
                    shutil.copy(os.path.join(vp, v), fname)'''
    fname = os.path.join(pm.ani_base_path, folder_name, 'calibration')
    os.makedirs(fname, exist_ok=True)
    for v in os.listdir(vid_path_):
        if vid_type in v:
            shutil.copy(os.path.join(vid_path_, v), fname)
            print(f'Copied {v}')
    
def runCalibration():
    shutil.copy(ani_cfg_mothercopy, pm.ani_base_path)
    cmd = ['P:', '&&', 'cd', pm.ani_base_path, '&&',
            'anipose', 'calibrate']
    result = subprocess.run(cmd, shell=True, check=True)
    print(result.stderr)

def collectCalib():
    for dirpath, dirnames, filenames in os.walk(pm.ani_base_path):
            if "calibration" in dirnames:
                calibration_path = os.path.join(dirpath, "calibration", "calibration.toml")
                if os.path.isfile(calibration_path):
                    parent_folder = os.path.basename(dirpath)
                    shutil.copy(calibration_path, os.path.join(r'C:\Users\mkrig\Documents\Python Scripts\calib history', f'calibration-{parent_folder}.toml'))
                    shutil.copy(calibration_path, r'C:\Users\mkrig\Documents\Python Scripts')

def collectCSV():
    src = Path(pm.ani_base_path)
    dst = Path(pm.data_path) / 'clean'
    dst.mkdir(parents=True, exist_ok=True)
    csvs = list(src.rglob('*.csv'))

    if not csvs:
        print('No CSV found. Nothing is copied.')
        return
    
    for f in csvs:
        tgt = dst / f.name
        if tgt.exists():
            if filecmp.cmp(f, tgt, shallow=False):
                print(f'Skipped existing CSV: {f.stem}')
                continue
            stem, suffix = f.stem, f.suffix
            i = 1
            while True:     # keep all the versions and rename new ones
                tgt_new = dst / f"{stem}_{i}{suffix}"
                if not tgt_new.exists():
                    tgt = tgt_new
                    break
                i += 1

        shutil.copy(f, tgt)
        print(f'Copied CSV: {f.stem}')

if __name__ == '__main__':
    updateOffset(list(CAM_OFFSETS.values()))        #FIXME make it able to run standalone
    dataSetup()
    two_way_shortcuts(pm.data_path, pm.PPATH_RAW)

    pm.vid_path, pm.cfg_path, pm.calib_idx = configSync(pm.PPATH_RAW, pm.data_path)
    if pause_before_sync:
        while not input('Paused before sync. Input "y" to continue\n> ')=='y':
            pass
    syncVid(pm.vid_path, pm.cfg_path)
    
    if pause_before_dlc:
        while not input('Paused before running deeplabcut. Input "y" to continue\n> ')=='y':
            pass

    # now move everything to colab
    '''    kids = copyToGoogle(pm.vid_path)
    while not input('Paused for Colab. Input "continue" after Colab is done.\n> ')=='continue':
        pass
    print(kids)
    pickupFromGoogle(pm.animal, pm.date)'''

    runDLC(pm.vid_path)
    setupAnipose(pm.ani_base_path, pm.vid_path)
    runAnipose(pm.ani_base_path)
    
    print('Congrats on getting heeeeeeere!')
    print(f'Total time consumed: {int((time.time() - pstart_time) // 60)} mins {round((time.time() - pstart_time) % 60, 1)} secs')

