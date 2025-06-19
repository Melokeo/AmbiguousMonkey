'''
scans all dates and check sync status
-- then run sync with default params for them
'''

from pathlib import Path
from tqdm import tqdm
import os, json

from diskcache import Cache

from ambiguousmonkey import monkeyUnityv1_8 as mky
from ambiguousmonkey.utils.pullAniAll import getAllDates, convertRawToData
from ambiguousmonkey.utils.silence import silence
from ambiguousmonkey.utils import VidSyncAudV2 as syncAud
from ambiguousmonkey.utils import VidSyncLEDv2_3 as syncLED

cache = Cache('syncDet')
problem_sync = []
not_4_set = []

def convertDataToRaw(data:list[Path]) -> list[Path]:
    return [Path(*[p.replace('DATA', 'DATA_RAW') if p == 'DATA' else p for p in path.parts]) for path in data]

def hasSkipSync(data_path:Path, daet:str) -> bool:
    target = Path(data_path) / 'SynchronizedVideos' / daet / '.skipSync'
    return target.exists()

def batchConfigSync(daet_to_process:list[tuple[Path, str,list]]) -> list[Path]:
    global problem_sync, not_4_set

    cfg_paths = []
    for pdat, daet, vid_set in daet_to_process:
        print('2' * 40)
        daet_root_path = pdat / 'SynchronizedVideos' / daet
        sync_cfg_path = daet_root_path / f"sync_config_{daet}.json"

        if "calib" in daet.lower():
            os.makedirs(daet_root_path, exist_ok=True)
        else:
            os.makedirs(daet_root_path/'L', exist_ok=True)
            os.makedirs(daet_root_path/'R', exist_ok=True)
        
        if (daet_root_path/'.skipDet').exists():
            print(f'Videos already marked as detected in {daet}')
            problem_sync.append(daet)
            continue
        
        praw = convertDataToRaw([pdat])[0]
        vid_set_path:list[Path] = []
        for i, vid_id in enumerate(vid_set):
            if vid_id is None: continue
            video_path = praw / f'cam{i+1}' / f'C{vid_id:04}.mp4'
            if not video_path.exists():
                print(f'Missing file in {daet}, skipping whole task')
                problem_sync.append(daet)
                vid_set_path = None
                break
            vid_set_path.append(video_path)    # case zfill(5)?
            
        if not vid_set_path:
            print(f'??? #1: {daet}')
            continue
        
        vid_set_path_str = [str(p) for p in vid_set_path]
        os.makedirs(pdat / 'SynchronizedVideos' / 'SyncDetection', exist_ok=True)
        try:
            sync_aud_result = syncAud.sync_videos(vid_set_path_str, fps=119.88, duration=75, start=0)
            syncAud.save_synced_waveforms(sync_aud_result, sr=48000, duration=50, tgt_path=str(pdat / 'SynchronizedVideos' / 'SyncDetection'))
        except Exception as e:
            print(f'Error running audio sync in {daet}: {e}')
            problem_sync.append(daet)
            continue
        starts_aud:list[int] = [i[-1] for i in sync_aud_result.values()]
        print(starts_aud)

        # now detect LEDs
        sync_LED_param = []
        for cam in range(1, 5):
            cam_folder = praw / f"cam{cam}"  # TODO change to configurable regex
            n = int(vid_set[cam-1] or -1)
            if n == -1:  continue

            cam_vid_name = f"C{n:04}.mp4"
            cam_video_path = cam_folder / cam_vid_name

            if not "calib" in daet.lower():
                if cam in mky.camL:
                    new_video_name = 'L\\' + f"{daet}-cam{cam}.mp4"
                elif cam in mky.camR:
                    new_video_name = 'R\\' + f"{daet}-cam{cam}.mp4"
            else:   # calibration has other logic
                new_video_name = f"{daet}-cam{cam}.mp4"
            
            # here testing start frame based on LED
            if os.path.exists(cam_video_path):
                if not "calib" in daet.lower():
                    try:
                        start_frame = syncLED.find_start_frame(
                            cam_video_path, 
                            mky.ROIs[cam], 
                            mky.THRES, 
                            mky.LEDs[cam], 
                            str(pdat / 'SynchronizedVideos' / 'SyncDetection')
                        )
                    except Exception as e:
                        raise RuntimeError(f'Error in SyncLED: {e}')
                else: 
                    start_frame = -1
                sync_LED_param.append({
                    "path": str(cam_video_path),
                    "roi": mky.ROIs[cam],
                    "LED": mky.LEDs[cam],
                    "start": start_frame,
                    "output_name": new_video_name
                })
            else:
                raise FileNotFoundError(
                    f"Failed when looking for start frame: expected video {cam_video_path} of cam{cam} not found.")
            
        starts_led = [i['start'] for i in sync_LED_param]
        if all(s == -1 for s in starts_led) and not "calib" in daet.lower():
            problem_sync.append(daet)
            continue
        print(f'Start frames: {starts_led}')

        determined_starts, status = mky.syncCrossValidation(starts_led, starts_aud)
        print(f'Corrected start frames: {determined_starts}')
        if determined_starts is None:
            print(f'[error] Failed to reach agreement on start frames for {daet}!')
            problem_sync.append(daet)
            continue
        if len(determined_starts) != 4:
            not_4_set.append(daet)

        for i in range(len(sync_LED_param)):
            sync_LED_param[i]['start'] = determined_starts[i]
        
        config = {
            "videos": sync_LED_param,
            "threshold": mky.THRES,
            "output_size": mky.OUTPUT_SIZE,
            "output_dir": str(daet_root_path),
            "detected": "T"
        }
    
        with open(str(sync_cfg_path), "w") as f:
            json.dump(config, f, indent=4)
        cfg_paths.append(sync_cfg_path)

        with open(sync_cfg_path.parent / '.skipDet', 'w') as f:
            pass

    return cfg_paths

def batchRunSync(cfg_paths: list[Path]) -> None:
    for pcfg in cfg_paths:
        try:
            with open(pcfg) as f:
                syncLED.process_videos(json.load(f))
            with open(pcfg.parent / '.skipSync', 'w') as f:
                pass
        except Exception as e:
            print(f'Error syncing video with cfg {pcfg.stem}')

@cache.memoize(expire=14400)
def getSyncStatus(praw:Path, pdat:Path) -> dict[str,bool]:
    with silence():
        print('Checking ' + str(praw))
        mky.pm.PPATH_RAW = str(praw)
        daets = mky.getTasksInDAET()
        if not daets: return None
        #print(daets)

        vid_dict = mky.getVideoSets()
        if not vid_dict:
            print(f'Error reading {str(praw.stem)}')
            return None
        # print(vid_dict)
        
        vid_exist_dict = mky.checkVideoExistence(vid_dict=vid_dict)
        # print(vid_exist_dict)

        synced_dict = {}
        for daet in daets:
            vid_set = vid_dict[daet]
            if not vid_set:     # means the cells are all empty / invalid in the note
                continue        
            if 0 < sum([1 for v in vid_set if v]) < 4:
                print(f'{daet} video set is not full')
            if 0 < sum([1 for v in vid_exist_dict[daet] if v]) < 4:
                print(f'{daet} video set has missing video file')
            
            synced_dict[daet] = hasSkipSync(pdat, daet)
    
    return synced_dict

def main() -> None:
    global problem_sync

    raw_dir = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
    raw_dir = Path(raw_dir)
    raws = getAllDates(raw_dir)
    datas = convertRawToData(raws)

    # good dates' list
    checked_good = []
    daet_to_process:list[tuple] = []

    #for praw, pdat in tqdm(list(zip(raws, datas)), desc='Scanning dates'):
    for praw, pdat in zip(raws, datas):
        with silence():
            mky.pm.PPATH_RAW = str(praw)
            vid_dict = mky.getVideoSets()
            if not vid_dict:
                print(f'Error reading {str(praw.stem)}')
                continue

            synced_dict = getSyncStatus(praw, pdat)
            if synced_dict is None:
                continue

        # get all daets without '.skipSync' marker
        problem_daets = [k for k,v in synced_dict.items() if not v]     
        if problem_daets:
            print('Not marked as synchronized:' + ', '.join(problem_daets))
            daet_to_process.extend((pdat, daet, vid_dict[daet]) for daet in problem_daets)
        else:
            checked_good.append(pdat.stem)
    
    print('=' * 40)
    print(f'Good dates: ' + ', '.join(checked_good))

    # ============ run sync ===============
    syncAud.THRES_PEAK = 1.1
    print('1'*40)
    # print(daet_to_process)
    try:
        cfg_paths = batchConfigSync(daet_to_process)
    finally:
        print('Problematic sync: ' + ', '.join(problem_sync))
        print('Not 4 video: ' + ', '.join(not_4_set))

    batchRunSync(cfg_paths)
                
if __name__ == '__main__':
    main()