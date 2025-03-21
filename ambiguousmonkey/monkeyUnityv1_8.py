'''
A Great Unity of monkey task pipeline
Run this in cmd with `conda activate monkeyUnity`
Mel
Feb 2025

v1.6: re-structured and tidied up data property
'''

import os, shutil, re, time
import pandas as pd
import json
from .utils import VidSyncLEDv2_3 as Sync
from .utils import VidSyncAudV2 as SyncAud
from pathlib import Path
import subprocess
import win32com.client

class PathMngr:
    def __init__(self, raw=None):
        self._PPATH_RAW = None
        self._vid_path = []
        self._cfg_path = []
        self._ani_base = None
        self._calib_idx = []
        if raw:
            self.PPATH_RAW = raw

    @property
    def PPATH_RAW(self):
        return self._PPATH_RAW
    
    @PPATH_RAW.setter
    def PPATH_RAW(self, v):
        if not v:
            raise ValueError('None occurred in PPATH_RAW.setter')
        if not os.path.exists(v):
           #  print(f"ValueError(f'PPATH_RAW.setter Path not found: {v}')")
           raise ValueError(f'PPATH_RAW.setter Path not found: {v}')
        else:
            self._PPATH_RAW = v
        print(f"[LOG] Updated PPATH_RAW to {v}")
    
    @property
    def data_path(self):
        return self._PPATH_RAW.replace('DATA_RAW', 'DATA') if self._PPATH_RAW else None

    @property
    def animal(self):
        pt = self._PPATH_RAW.split(os.sep)
        animal = next((p for p in pt if p in ANIMALS), None)
        if animal is None:
            raise ValueError(f"Check animal name in raw path. Recognized names: {ANIMALS}")
        return animal
    
    @property
    def date(self):
        return self._PPATH_RAW.split(os.sep)[-1]
    
    @property
    def vid_path(self):
        return self._vid_path
    
    @vid_path.setter
    def vid_path(self, v):
        if not isinstance(v, list):
            raise ValueError(f'(Internal) Passed invalid vid_path {v}')
        self._vid_path = v
    
    @property
    def cfg_path(self):
        return self._cfg_path
    
    @cfg_path.setter
    def cfg_path(self, v):
        if not isinstance(v, list):
            raise ValueError(f'(Internal) Passed invalid cfg_path {v}')
        self._cfg_path = v

    @property
    def ani_base_path(self):
        return os.path.join(self.data_path, 'anipose')
    
    @property
    def calib_idx(self):
        return self._calib_idx
    
    @calib_idx.setter
    def calib_idx(self, v):
        self._calib_idx = v
    
    def show(self):
        return f"""
        --- Path Summary ---
        Raw Path: {self.PPATH_RAW}
        Data Path: {self.data_path}
        Animal: {self.animal}
        Date: {self.date}
        Video Paths: {self.vid_path}
        --------------------
        """

pstart_time = time.time()
PPATH_RAW = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\03\20250303' # path of today's raw data (eg P:\....02\05\20250205\). keep the r in front.
pm = PathMngr(PPATH_RAW)
ANIMALS = ['Pici']
PATH_ANI_CFG = ''
PATH_ANI_CALIB = ''
HEADER_KEY = 'Experiment'#'Video # From' #'Task'
ROIs = {1: [550, 148, 75, 71], 2: [1277, 29, 119, 67], 3: [864, 302, 84, 77], 4: [1031, 379, 105, 71]}
LEDs = {1: "Y", 2: "G", 3: "G", 4: "G"}
THRES = 175
THRES_ERROR = 5    # max tolerable error b/w audio and LED sync results
OUTPUT_SIZE = [1920, 1080]
CAM_OFFSETS = {1: 0, 2: 459, 3: 567, 4: 608}
ani_cfg_mothercopy = r"C:\Users\rnel\Documents\Python Scripts\config.toml"
ani_cfg_mothercopy_add_ref = r"C:\Users\rnel\Documents\Python Scripts\config-ref.toml"
ani_calib_mothercopy = r"C:\Users\rnel\Documents\Python Scripts\calibration.toml"
Colab_path = r'G:\My Drive\MonkeyModels'
model_path_colab = {'L': r'G:\My Drive\MonkeyModels\TS-L-shaved', 'R': r'G:\My Drive\MonkeyModels\TS-R-shaved'}
camL = [1, 2]
camR = [3, 4]
list_skipped_file_name = ['x', '-']
pause_before_sync = True
pause_before_dlc = True
dlc_mdl_path = {
    'L': r'C:\Users\rnel\Desktop\DLC\Model\TS-L',
    'R': r'C:\Users\rnel\Desktop\DLC\Model\TS-R'
    }
dlc_cfg_path = {
    'L': r'C:\Users\rnel\Desktop\DLC\Model\TS-L\config.yaml',
    'R': r'C:\Users\rnel\Desktop\DLC\Model\TS-R\config.yaml'
    }
add_ref = False
Ref = [
        {
            'Fx1': (564.7, 641.4, 1),
            'Fx2': (487.2, 641.1, 1),
            'Fx3': (487.7, 697.5, 1)
        },
        {
            'Fx1': (963, 821.1, 1),
            'Fx2': (881.4, 830.2, 1),
            'Fx3': (879.5, 889, 1)
        },
        {
            'Fx1': (576.1, 384.5, 1),
            'Fx2': (642.9, 405.7, 1),
            'Fx3': (647.3, 432.0, 1)
        },
        {
            'Fx1': (776.3, 372.7, 1),
            'Fx2': (851.5, 373.1, 1),
            'Fx3': (861.7, 408.9, 1)
        }]
SCALE_FACTOR = 1 # only scales ref
vid_type = 'mp4'
base_header = ['Experiment Number', 'Experiment', 'Task', 'VOID']
xlsx_cam_header = ['Camera files \n(1 LR)','Camera files \n(2 LL)', 'Camera files (3 RR)', 'Camera files (4 RL)']
first_run = True
filename_cam_head = ['x','x','x','x']

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
    '''data_path = os.path.join(
        pt[0] + os.sep, *pt[1:pt.index("DATA_RAW")], "DATA",
        *pt[pt.index("DATA_RAW"):]
        ) if "DATA_RAW" in pt else exit("DATA_RAW not found in path.")'''
    # make folders
    # if not os.path.exists(data_path):
    if True: #input(f'Will set up folder in {data_path}, input y to continue: ') == 'y':
        os.makedirs(pm.data_path, exist_ok = True)
        sub_dir = [
            '\\SynchronizedVideos',
            '\\anipose',
            '\\SynchronizedVideos\\SyncDetection'
            ]
        for sd in sub_dir:
            os.makedirs((pm.data_path + sd), exist_ok = True)
    else:
        # raise RuntimeError('Then why do you run this script??')
        pass

def _infoFromPath(PPATH_RAW):
    pt = PPATH_RAW.split(os.sep)
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

# sync videos
def configSync(base_header=base_header, cam_header=xlsx_cam_header):
    h = base_header + cam_header
    df = readExpNote(pm.PPATH_RAW, header = h)
    vid_path = []
    cfg_path = []
    calib_idx = []
    animal, date = _infoFromPath(pm.PPATH_RAW)
    for _, row in df.iterrows():
        experiment, task = row["Experiment"], str(row["Task"]).replace(' ', '')
        if row['VOID'] == 'T':
            print(f'Void trial skipped: {experiment}, {task}')
            continue        # allows u to skip a trial

        vid_idx = []
        try:        # check we have enough videos to proceed & get the vid index
            missing_count = 0
            for i in range(4):
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
            print(f'Start frames are already detected in {os.path.basename(task_root_path)}, skipped')
            continue

        print(f'Testing start frame for {experiment}-{task}...')

        sync_param = [] # storing info for sync, every set of videos

        # here is main loop to test LED frames
        for cam in range(1, 5):
            cam_folder = os.path.join(pm.PPATH_RAW, f"cam{cam}")
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
                    start_frame = Sync.find_start_frame(
                        cam_video_path, ROIs[cam], THRES, LEDs[cam],os.path.join(pm.data_path,'SynchronizedVideos\\SyncDetection'))
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
        vids = [i['path'] for i in sync_param]
        starts = [i['start'] for i in sync_param]
        print(f'Start frames: {starts}')
        sync_results = SyncAud.sync_videos(vids, fps=119.88, duration=30, start=0)
        SyncAud.save_synced_waveforms(sync_results, sr=48000, fps=119.88, duration=10, tgt_path=os.path.join(pm.data_path, 'SynchronizedVideos\\SyncDetection'))
        starts_aud = [i[-1] for i in sync_results.values()]

        starts, status = syncCrossValidation(starts, starts_aud)
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
    return vid_path, cfg_path, calib_idx

def syncCrossValidation(starts: list, starts_aud: list):
    # Compute offset estimate from valid LED starts
    valid_idx = [i for i, s in enumerate(starts) if s != -1]
    if valid_idx:
        offsets = [starts[i] - starts_aud[i] for i in valid_idx]
        offset_est = sorted(offsets)[len(offsets)//2]  # median offset
    else:
        offset_est = 0  # default; will be overridden in 4-missing case

    missing_idx = [i for i, s in enumerate(starts) if s == -1]
    num_missing = len(missing_idx)
    
    if len(starts)<4:
        if num_missing >= 1:
            return starts_aud, None
        else:
            deviations = [abs(starts[i] - (offset_est + starts_aud[i])) for i in range(2)]
            num_deviations = sum(dev > THRES_ERROR for dev in deviations)
            if num_deviations == 1:
                return None, -2

    if num_missing > 0:
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

def runDLC(vid_path):
    # DLC part. Can anyone send me the Dirt Rally DLCs??
    import deeplabcut # type: ignore
    print('DeepLabCut now loaded')
    # better logic needed here

    for vid in vid_path:
        print(f'\nDLC analyzing {os.path.basename(vid)}...')
        try:
            for p in ['L', 'R']:
                if not os.path.exists(os.path.join(vid, p, '.skipDLC')):
                    print('=================NEW DLC ANAL=================\n(not *that* anal)')
                    deeplabcut.analyze_videos(dlc_cfg_path[p], os.path.join(vid,p), videotype = vid_type)
                    with open(os.path.join(vid, p, '.skipDLC'), 'w') as f:  
                        pass
                else:
                    print(f'Videos are already screwed in {vid}\\{p}, skipped\n')
        except Exception as e:
            raise RuntimeError(f'Main script: Failed in DLC analyse:\n{e}')
        for p in ['L', 'R']:
            deeplabcut.filterpredictions(dlc_cfg_path[p], os.path.join(vid,p), shuffle = 1, save_as_csv = True, videotype = vid_type)
            # deeplabcut.create_labeled_video(dlc_cfg_path[p], os.path.join(vid,p), videotype = vid_type, draw_skeleton = True)
    print('=====2D analyse finished=====\nDLC is happy. Are *you* happy?\n')

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
def setupAnipose(ani_base_path, vid_path, Ref = Ref, add_ref=False):
    """
    Organizes the data structure for Anipose 3D pose estimation.
    Args:
        ani_base_path (str): Path to the anipose project folder.
        vid_path (list): Paths to synchronized video folders.
        Ref (list, optional): Reference points for calibration (default: Ref).
        add_ref (bool, optional): Whether to add reference points.
    """
    global ani_cfg_mothercopy, ani_cfg_mothercopy_add_ref
    print('\nOrganizing for anipose')
    mc = ani_cfg_mothercopy_add_ref if add_ref else ani_cfg_mothercopy
    shutil.copy(mc, os.path.join(ani_base_path, 'config.toml'))
    for vid in vid_path:
        if not os.path.exists(os.path.join(vid,'.skipSync')):
            raise ValueError(f'Folder not marked as synchronized:\n{vid}')
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
                shutil.move(fr, os.path.join(trial_path, 'videos-raw'))
            for f in p.glob('*_filtered.h5'):
                # shutil.move(f.resolve(), os.path.join(trial_path, 'pose-2d-filtered'))
                cam = str(f.resolve())
                cam = int(cam.split('DLC_resnet')[0][-1])
                out_path = f.name
                out_path = os.path.join(trial_path, 'pose-2d-filtered', out_path)
                out_path = re.sub('DLC_resnet(101|50)_(TS|BBT).*shuffle1_\d+0000_filtered','',out_path)
                fr = str(f.resolve())
                fr = fr.replace(r'\\share.files.pitt.edu\RnelShare', 'P:')
                if add_ref:
                    #h5r.add_fixed_points(fr, out_path, cam, Ref)
                    pass
                else:
                    shutil.copy(fr, out_path)
                    print(f'h5 copied {os.path.basename(fr)}')
    
def runAnipose(ani_base_path, run_combined = False):
    """
    Runs Anipose pipeline for triangulation and visualization.
    Args:
        ani_base_path (str): Path to the anipose project folder.
        run_combined (bool): If True, runs 'label-combined' after triangulation.
    """
    try:
        print('Activating new conda env, could take a while...')
        cmd = ['conda', 'activate', 'anipose_3d', '&&', 'P:', '&&', 'cd', ani_base_path, '&&', 'anipose', 'triangulate', '&&', 'anipose', 'label-3d']
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

def two_way_shortcuts(path1, path2):
    """Creates two-way shortcuts"""
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
                    shutil.copy(calibration_path, os.path.join(r'C:\Users\rnel\Documents\Python Scripts\calib history', f'calibration-{pm.date}-{parent_folder}.toml'))
                    shutil.copy(calibration_path, r'C:\Users\rnel\Documents\Python Scripts')

if __name__ == '__main__':
    updateOffset(list(CAM_OFFSETS.values()))
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
    kids = copyToGoogle(pm.vid_path)
    while not input('Paused for Colab. Input "continue" after Colab is done.\n> ')=='continue':
        pass
    print(kids)
    pickupFromGoogle(pm.animal, pm.date)

    # runDLC(vid_path)

    '''Ref = [
        {k: tuple(SCALE_FACTOR * v for v in val) for k, val in obj.items()}
        for obj in Ref
    ] # scale Ref's'''
    setupAnipose(pm.ani_base_path, pm.vid_path, Ref, add_ref)
    runAnipose(pm.ani_base_path)
    
    print('Congrats on getting heeeeeeere!')
    print(f'Total time consumed: {int((time.time() - pstart_time) // 60)} mins {round((time.time() - pstart_time) % 60, 1)} secs')

