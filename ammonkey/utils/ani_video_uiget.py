'''anipose vid maker with file select dialog'''

import tkinter as tk
from tkinter import filedialog # migrate to qt if integrating into main gui
from pathlib import Path    

from ammonkey.utils.ani_video_maker import ani_label_3d

from ammonkey.utils.ol_logging import set_colored_logger
lg = set_colored_logger(__name__)

def main() -> None:
    root = tk.Tk()
    root.withdraw()  # you dont want to see the window
    lg.info('tk window started')

    lg.info('Waiting for data dir selection...')
    data_dir = filedialog.askdirectory(title='Select Data Directory')
    if not data_dir:
        lg.warning('No directory selected, exiting.')
        return
    
    lg.info('Waiting for cfg selection...')
    cfg = filedialog.askopenfilename(
        title='Select config.toml (Cancel to skip)', 
        filetypes=[('TOML files', '*.toml')]
    )
    
    # lg.info('Waiting for video selection...')
    # video_dir = filedialog.askdirectory(
    #     title='Select Video File (Cancel to skip)', 
    # )
    
    ani_label_3d(
        data_dir=Path(data_dir),
        config_file=Path(cfg) if cfg else None,
        # video_raw_dir=Path(video_dir) if video_dir else None,
    )

if __name__ == "__main__":
    main()