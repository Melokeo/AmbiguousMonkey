"""Script to recursively check video fps in a directory against preset values, 
in case you left wrong fps (59.94) during recording."""

import os, subprocess, json

TARGET_FPS = [119.88, 120]  # preset frame rate
ROOT = r"P:\projects\monkeys\Chronic_VLL\DATA\FUSILLO\2025\08"  # change to target folder

def get_fps(path):
    cmd = [
        r"C:\ffmpeg\bin\ffprobe.exe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "json", path
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        return None
    data = json.loads(out.stdout)
    try:
        rate = data["streams"][0]["r_frame_rate"]
        num, den = map(float, rate.split('/'))
        return num / den if den != 0 else None
    except Exception:
        return None

bad_videos = []
for root, _, files in os.walk(ROOT):
    for f in files:
        if f.lower().endswith(('.mp4', '.mov', '.mkv', '.avi', '.wmv', '.flv')):
            p = os.path.join(root, f)
            fps = get_fps(p)
            print(f"{os.path.basename(p):<50}: {fps}", end='\r')
            if fps is None or all(abs(fps - target) > 0.01 for target in TARGET_FPS):
                bad_videos.append((p, fps))

if bad_videos:
    print("Non-matching videos:")
    for path, fps in bad_videos:
        print(f"{path}  ->  {fps}")
else:
    print("All match preset frame rate.")
