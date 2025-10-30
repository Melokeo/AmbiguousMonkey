# can further connect to dlc & anipose.

import time
pstart_time = time.time()
# print('VidSyncLEDv2 running. Importing dependencies...')

from pathlib import Path
import cv2, subprocess, json, os
import numpy as np
import matplotlib.pyplot as plt

CHECK_FURTHEST = 4000
debug = False
show_plt = False
ffmpeg_path = r'C:\ffmpeg\bin\ffmpeg.exe'
ffprobe_path = r'C:\ffmpeg\bin\ffprobe.exe'
# if below doesnt work try ffmpeg with path above
#ffmpeg_path = 'ffmpeg'
#ffprobe_path = 'ffprobe'

if debug or show_plt:
    print(f'Alt: debug {debug}, show intensity plot {show_plt}')
# print('Sync ready.\n')

def get_video_info(path):
    cmd = [ffprobe_path, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=nb_frames,r_frame_rate', '-of', 'csv=p=0', path]
    try:
        frame_rate, nb_frames = subprocess.check_output(cmd).decode().strip().split(',')
        if nb_frames == 'N/A': raise NotImplementedError(f"nb_frames_str returns N/A. {nb_frames}")
        fps = eval(frame_rate)
        return int(nb_frames), fps
    except Exception as e:
        # print(nb_frames, frame_rate)
        raise RuntimeError(f"ffprobe failed: {e}")
    
def find_start_frame(path: str, roi: list[int]|tuple[int,...], threshold: int, LED: str, 
                  out_path: str = 'Detection Output', 
                  led_persist_sec: float = 0.033, 
                  led_persist_tolerance: float = 0.0,
                  led_duration_range: tuple[float, float] = (1.0, 1.0)) -> int:
    """
    params:
        path: video path
        roi: detection area [x, y, w, h]
        threshold: (0-255)
        LED: LED color ("Y" or "G")
        led_persist_sec: requirement of led lit duration
        led_persist_tolerance: noise level allowed in the lit duration. the lower the stricter.
    return:
        start_frame
    """
    roi = tuple(roi)
    x, y, w, h = roi
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"Video {path} cannot be opened.")
    
    # calculate required consecutive frames for persistence
    _, fps = get_video_info(path)  # you'll need this info
    required_frames = int(led_persist_sec * fps)
    consecutive_count = 0
    potential_start = None
    tolerance_frames = int(required_frames * led_persist_tolerance)
    min_frames = int(led_persist_sec * fps * led_duration_range[0])
    max_frames = int(led_persist_sec * fps * led_duration_range[1])
    # safety checks
    if min_frames <= 0:
        min_frames = 1
    if max_frames <= min_frames:
        max_frames = min_frames + 1
    if tolerance_frames < 0:
        tolerance_frames = 0

    hsv_ranges = {
        "Y": ([20, 100, 100], [30, 255, 255]),   
        "G": ([36, 100, 100], [77, 255, 255])    
    }
    
    lower, upper = hsv_ranges.get(LED, ([0,0,0], [0,0,0]))
    lower = np.array(lower, dtype=np.uint8)
    upper = np.array(upper, dtype=np.uint8)

    max_values = []
    start_frame = None
    detection_frame = None
    head = False

    furthest = 3000

    frame_count = 0 # will add 1 when returning !!
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        roi_area = frame[y:y+h, x:x+w]
        hsv = cv2.cvtColor(roi_area, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        
        # masking
        v_channel = cv2.bitwise_and(hsv[:,:,2], hsv[:,:,2], mask=mask)
        current_max = np.max(v_channel)
        max_values.append(current_max)

        # detection logic!
        if current_max >= threshold:
            if consecutive_count == 0:
                potential_start = frame_count
            consecutive_count += 1
            
            # check if we've reached minimum duration
            if consecutive_count >= min_frames and start_frame is None:
                # verify persistence within current window
                window_size = min(consecutive_count, max_frames)
                start_idx = frame_count - window_size + 1
                frames_below = sum(1 for i in range(start_idx, frame_count + 1) 
                                if max_values[i] < threshold)
                
                if frames_below <= int(window_size * led_persist_tolerance):
                    if potential_start == 0:
                        head = True
                    elif not head:
                        start_frame = potential_start
                        detection_frame = frame.copy()
                        cv2.rectangle(detection_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        break
        else:
            # only reset if we haven't started counting or if we're beyond tolerance
            if consecutive_count > 0:
                # count how many frames in current window are below threshold
                window_start = max(0, potential_start) if potential_start else 0
                window_end = min(len(max_values), frame_count + 1)
                current_frames_below = sum(1 for i in range(window_start, window_end) 
                                        if max_values[i] < threshold)
                
                tolerance_check = min(tolerance_frames, int(consecutive_count * led_persist_tolerance))
                if current_frames_below > tolerance_check:
                    consecutive_count = 0
                    potential_start = None
            
            if head:
                head = False

        frame_count += 1
        if frame_count % 500 == 1:
            print(frame_count, end=' | ')
        if frame_count > furthest:
            plt.figure(figsize=(12, 6))
            plt.plot(max_values, '.-', 
                    color='green' if LED == 'G' else (0.84, 0.69, 0.59),
                    label='Brightness')
            # plt.show()
            # raise ValueError(f'No lit frame detected in {path} within {furthest} frames!')
            print(f'[WARNING] No lit frame found in {path} within {furthest} frames!')
            break

    cap.release()

    # visualize
    if detection_frame is not None:
        plt.figure(figsize=(12, 6))
        plt.plot(max_values, '.-', 
                color='green' if LED == 'G' else (0.84, 0.69, 0.59),
                label='Brightness')

        plt.axhline(threshold, color='red', linestyle='--', label='Threshold')
        if start_frame is not None:
            plt.axvline(start_frame, color='blue', linestyle='--', label='Start Frame')
            print(f'From {os.path.basename(path)} detected LED lit at frame {start_frame}')
        color = (0, 255, 0) if LED == 'G' else (214, 177, 150)
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
        cv2.imwrite(os.path.join(out_path,f'detection_result_{os.path.basename(path).split(".")[0]}_{start_frame+1}.jpg'), frame)
        plt.title(f"Brightness Analysis ({LED} LED)")
        plt.xlabel("Frame Number")
        plt.ylabel("Brightness Value")
        plt.legend()
        plt.savefig(os.path.join(out_path,f'brightness_plot_{os.path.basename(path).split(".")[0]}_{start_frame+1}.jpg'))
        plt.close()

    return start_frame+1 if start_frame is not None else -1

def process_videos(cfg):
    global start_time
    os.makedirs(cfg.get('output_dir', 'output'), exist_ok=True)
    meta:list[dict] = []
    for vc in cfg['videos']:
        total_frames, fps = get_video_info(vc['path'])
        print(f"Probed {os.path.basename(vc['path'])} with {total_frames} frames @ {fps} fps")
        if cfg.get('detected', 'F') == 'T':
            start_frame = int(vc['start'])
            if start_frame == -1:
                raise ValueError('Detection recorded but start frame not valid (NaN or -1)')
        else:
            start_frame = find_start_frame(vc['path'], vc['roi'], cfg['threshold'], vc['LED'])
        meta.append({**vc, 'total_frames': total_frames, 'fps': fps, 'start_frame': start_frame})  
        print(f"You've spent {int((time.time() - pstart_time) // 60)} mins {round((time.time() - pstart_time) % 60, 1)} secs here.")

    output_frames = min(m['total_frames'] - m['start_frame'] for m in meta)
    
    # print(f'{m["start_frame"]}')
    if output_frames <= 0: raise ValueError("Frame count mismatch.")
    for m in meta:
        # out_path = os.path.join(cfg.get('output_dir', 'output'), m['output_name'])
        out_path:Path = Path(cfg.get('output_dir', 'output')) / m['output_name']
        if not (op:=out_path.parent).exists():
            op.mkdir()
        start_time = m['start_frame'] / m['fps']
        ffmpeg_cmd_cpu = [
                      ffmpeg_path, 
                      '-y', 
                      '-i', m['path'], 
                      '-ss', f'{start_time:.6f}', 
                      '-frames:v', f'{output_frames}', #str(output_frames),
                      '-vf', f"scale={cfg['output_size'][0]}:{cfg['output_size'][1]}",
                      '-c:v', 'libx264', 
                      '-preset', 'fast', 
                      '-movflags', '+faststart',
                      '-crf', '18', 
                      str(out_path)
                      ]
        # following cmd uses GPU accel. 
        # but recently the 4070s doesn't want to work and it falls back to CPU for unknown reason
        ffmpeg_cmd_gpu_nvenc = [
                        ffmpeg_path,
                        '-y',
                        '-i', m['path'],
                        '-ss', f'{start_time:.6f}',
                        '-frames:v', f'{output_frames}',
                        '-vf', f'hwupload_cuda,scale_cuda={cfg["output_size"][0]}:{cfg["output_size"][1]}',
                        '-c:v', 'h264_nvenc',
                        '-preset', 'fast',
                        '-movflags', '+faststart',
                        '-b:v', '5M',
                        str(out_path)
                    ]
        # following cmd strictly sets frame-precise length
        # but it makes videos de-sync for unknown reason.
        '''ffmpeg_cmd = [
            'C:\\ffmpeg\\bin\\ffmpeg',
            '-y',
            '-i', m['path'],
            '-vf', f"select='between(n\\,{m['start_frame']}\\,{m['start_frame'] + output_frames - 1})',setpts=N/FRAME_RATE/TB,hwupload_cuda,scale_cuda={cfg['output_size'][0]}:{cfg['output_size'][1]}",
            '-c:v', 'h264_nvenc',
            '-preset', 'fast',
            '-movflags', '+faststart',
            '-b:v', '5M',
            out_path
        ]'''
        print(f"Now trimming video to {out_path.stem}")
        # print(ffmpeg_cmd)
        if not debug:
            try:
                result = subprocess.run(ffmpeg_cmd_gpu_nvenc, check=True, stderr=subprocess.PIPE)
            except Exception as e:
                print(f'Failed running ffmpeg w/ nvenc: {e}')
                print('Falling back to cpu processing...')
                try:
                    subprocess.run(ffmpeg_cmd_cpu, check=True, stderr=subprocess.PIPE)
                except Exception as e:
                    raise RuntimeError(f'Failed running ffmpeg: {e}')
            # print(result.stderr)
        print(f"You've spent {int((time.time() - pstart_time) // 60)} mins {round((time.time() - pstart_time) % 60, 1)} secs here.\n")

if __name__ == "__main__":
    # paths = ['',]

    try:
        with open(r"P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025\03\20250310\SynchronizedVideos\Calib\sync_config_Calib.json") as f:
            process_videos(json.load(f))
        print('Processed all.') #Enjoy your miserable day.')
    except Exception as e:
        print(f"Failed: {e}")
