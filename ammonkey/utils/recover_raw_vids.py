'''util function to recover raw videos from sync dir to anipose videos_raw dir'''

from pathlib import Path
import shutil

from ammonkey.utils.ol_logging import set_colored_logger
lg = set_colored_logger(__name__)

def recover_raw_vids(ani_daet_dir: Path) -> list[Path]:
    date_root = _get_date_root(ani_daet_dir)
    daet = ani_daet_dir.name
    path_sync = date_root / 'SynchronizedVideos' / daet
    videos_raw_dir = ani_daet_dir / 'videos-raw'

    if not videos_raw_dir.exists():
        videos_raw_dir.mkdir(parents=True, exist_ok=True)
        lg.info(f'Created videos-raw dir: {videos_raw_dir}')

    if not path_sync.exists():
        raise FileNotFoundError(f'Sync dir not found: {path_sync}')
    
    subdirs = ['L', 'R']
    suffix = '.mp4'
    videos_to_copy = [
        vid for subdir in subdirs
        for vid in (path_sync / subdir).glob(f'*{suffix}')
    ]
    count = len(videos_to_copy)
    if count == 0:
        lg.warning(f'No raw videos found in sync dir: {path_sync}')
        return []
    lg.info(f'Found {count} raw videos in sync dir: {path_sync}')

    copied_videos = []
    for video in videos_to_copy:
        dest = videos_raw_dir / video.name
        if dest.exists():
            lg.info(f'{dest.name} already exists')
            continue
        else:
            lg.info(f'Copying to {dest}')
        shutil.copy(video, dest)
        copied_videos.append(dest)
        lg.info(f'Copied to {dest}')

    return copied_videos

def _get_date_root(path: Path) -> Path:
    '''return date dir, assume .../yyyymmdd/anipose/../.. in input path,
    arbitraty nesting, return .../yyyymmdd'''
    for parent in path.parents:
        if parent.name == 'anipose':
            return parent.parent
    raise ValueError(f'Couldn\'t find date root for path: {path}')

if __name__ == "__main__":
    target = r"P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025\04\20250404\anipose\20250404-Pici-Brinkman-1"
    copied = recover_raw_vids(Path(target))

    lg.info(f'Copied {len(copied)} videos:')
    for vid in copied:
        lg.info(f'\t{vid.name}')

# p = Path(r'P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025\03\20250331')
# date = '20250331'
# L = ['cam1', 'cam2']
# R = ['cam3', 'cam4']
# path_ani = p / 'anipose'
# path_sync = p / 'SynchronizedVideos'
# 
# def get_lr(fn: str):
#     if any(l in fn for l in L):
#         return 'L'
#     elif any(r in fn for r in R):
#         return 'R'
#     else:
#         return None
# 
# for d in path_ani.glob('*'):
#     if not date in d.name:
#         continue
#     vr = d / 'videos-raw'
#     if not vr.exists():
#         continue
#     for vid in vr.glob('*.mp4'):
#         lr = get_lr(vid.name)
#         if lr:
#             tgt = path_sync / d.name / lr / vid.name
#             if tgt.exists():
#                 print(f'{tgt} exists')
#                 continue
#             vid.rename(path_sync / d.name / lr / vid.name)
# 