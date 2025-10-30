from pathlib import Path

p = Path(r'P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025\03\20250331')
date = '20250331'
L = ['cam1', 'cam2']
R = ['cam3', 'cam4']
path_ani = p / 'anipose'
path_sync = p / 'SynchronizedVideos'

def get_lr(fn: str):
    if any(l in fn for l in L):
        return 'L'
    elif any(r in fn for r in R):
        return 'R'
    else:
        return None

for d in path_ani.glob('*'):
    if not date in d.name:
        continue
    vr = d / 'videos-raw'
    if not vr.exists():
        continue
    for vid in vr.glob('*.mp4'):
        lr = get_lr(vid.name)
        if lr:
            tgt = path_sync / d.name / lr / vid.name
            if tgt.exists():
                print(f'{tgt} exists')
                continue
            vid.rename(path_sync / d.name / lr / vid.name)
