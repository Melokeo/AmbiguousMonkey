# can further connect to dlc & anipose.

import time
pstart_time = time.time()
print('VidSyncLEDv2 running. Importing dependencies...')

import cv2, subprocess, json, os
import numpy as np
import matplotlib.pyplot as plt

CHECK_FURTHEST = 4000
debug = False
show_plt = True
if debug or show_plt:
    print(f'Alt: debug {debug}, show intensity plot {show_plt}')
print('Sync ready.\n')

def get_video_info(path):
    cmd = [r'C:\ffmpeg\bin\ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=nb_frames,r_frame_rate', '-of', 'csv=p=0', path]
    try:
        frame_rate, nb_frames = subprocess.check_output(cmd).decode().strip().split(',')
        if nb_frames == 'N/A': raise NotImplementedError(f"nb_frames_str returns N/A. {nb_frames}")
        fps = eval(frame_rate)
        return int(nb_frames), fps
    except Exception as e:
        # print(nb_frames, frame_rate)
        raise RuntimeError(f"ffprobe failed: {e}")
    
def find_start_frame(path, roi, threshold, LED, out_path='Detection Output'):
    """
    params:
        path: video path
        roi: detection area [x, y, w, h]
        threshold: (0-255)
        LED: LED color ("Y" or "G")
    return:
        start_frame
    """
    x, y, w, h = roi
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"Video {path} cannot be opened.")

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

    furthest = 4500

    frame_count = 0 # will add 1 when returning
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

        if current_max >= threshold and start_frame is None:
            if frame_count == 0:
                head = True
            elif not head:
                start_frame = frame_count
                detection_frame = frame.copy()
                cv2.rectangle(detection_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                break
        elif current_max <= threshold and head:
            head = False

        frame_count += 1
        if frame_count % 500 == 1:
            print(frame_count, end=' | ')
        if frame_count > furthest:
            plt.figure(figsize=(12, 6))
            plt.plot(max_values, '.-', 
                    color='green' if LED == 'G' else (0.84, 0.69, 0.59),
                    label='Brightness')
            plt.show()
            raise ValueError(f'No lit frame detected in {path} within {furthest} frames!')

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

    return start_frame+1 if start_frame is not None else -1

def process_videos(cfg):
    global start_time
    os.makedirs(cfg.get('output_dir', 'output'), exist_ok=True)
    meta = []
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

        #print(current_intensity)
    # metadata = [{**vc, 'total_frames': get_video_info(vc['path'])[0], 'fps': get_video_info(vc['path'])[1], 'start_frame': find_start_frame(vc['path'], vc['roi'], cfg['threshold'])} for vc in cfg['videos']]
    output_frames = min(m['total_frames'] - m['start_frame'] for m in meta)
    
    # print(f'{m["start_frame"]}')
    if output_frames <= 0: raise ValueError("Frame count mismatch.")
    for m in meta:
        #out_path = f"{cfg.get('output_dir', 'output')}/{os.path.basename(m['path']).rsplit('.', 1)[0]}_aligned.mp4"
        out_path = os.path.join(cfg.get('output_dir', 'output'), m['output_name'])
        start_time = m['start_frame'] / m['fps']
        ffmpeg_cmd = [r'C:\ffmpeg\bin\ffmpeg', '-y', '-i', m['path'], '-ss',
                      f'{start_time:.6f}', '-frames:v', str(output_frames),
                      '-vf', f"scale={cfg['output_size'][0]}:{cfg['output_size'][1]}",
                      '-c:v', 'libx264', '-preset', 'fast', '-movflags', '+faststart',
                      '-crf', '18', out_path]
        # following cmd uses GPU accel. 
        # but recently the 4070s doesn't want to work and it falls back to CPU for unknown reason
        ffmpeg_cmd = [
                        'C:\\ffmpeg\\bin\\ffmpeg',
                        '-y',
                        '-i', m['path'],
                        '-ss', f'{start_time:.6f}',
                        '-frames:v', f'{output_frames}',
                        '-vf', f'hwupload_cuda,scale_cuda={cfg["output_size"][0]}:{cfg["output_size"][1]}',
                        '-c:v', 'h264_nvenc',
                        '-preset', 'fast',
                        '-movflags', '+faststart',
                        '-b:v', '5M',
                        out_path
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
        print(f"Now trimming video to {os.path.basename(out_path)}")
        # print(ffmpeg_cmd)
        if not debug:
            result = subprocess.run(ffmpeg_cmd, check=True, stderr=subprocess.PIPE)
            # print(result.stderr)
        print(f"You've spent {int((time.time() - pstart_time) // 60)} mins {round((time.time() - pstart_time) % 60, 1)} secs here.\n")

if __name__ == "__main__":
    try:
        with open(r"C:\Users\rnel\Videos\sync_config_TS_1_0442.json") as f:
            process_videos(json.load(f))
        print('Processed all.') #Enjoy your miserable day.')
    except Exception as e:
        print(f"Failed: {e}")
