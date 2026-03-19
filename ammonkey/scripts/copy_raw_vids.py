from pathlib import Path
from ammonkey import DAET
import shutil

PathLike = Path | str

def copy_raw_vids(sync_dir: PathLike, ani_dir: PathLike, 
                  ) -> None:
    sync_dir = Path(sync_dir)
    ani_dir = Path(ani_dir)

    for daet_dir in sync_dir.glob('*'):
        if not daet_dir.is_dir():
            continue
        try:
            DAET.fromString(daet_dir.name)
        except ValueError:
            continue

        raw_vid_dir = ani_dir / daet_dir.name / 'videos-raw'

        for s in ['L', 'R']:
            ss = daet_dir / s
            for vid in ss.glob('*.mp4'):
                # FIXME we have weird bugs here. it skipped TS-6, -9 but copied for other daets.
                # print(f'{vid} -> {raw_vid_dir}')
                print(shutil.copy2(vid, raw_vid_dir))

if __name__ == '__main__':
    sd = r'P:\projects\monkeys\Chronic_VLL\DATA\FUSILLO\2025\09\20250908\SynchronizedVideos'
    ad = r'P:\projects\monkeys\Chronic_VLL\DATA\FUSILLO\2025\09\20250908\anipose\fus-arm-20250925_7939'
    copy_raw_vids(sd, ad)