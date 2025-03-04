# monkeyUnity

Mel Xu, Feb 2025

Rehab Neural Engineering Labs, RNEL, University of Pittsburgh

*These codes haven't been made transplantable yet. It only works on one specific computer. Uploading it here is just for deposition*

## Overview

Scripts unifying workflow as *Qin Shi Huang* did when unifying the six states.

Digitally immortalize your monkeys in all their moving glory.

| Script               | Description                                                  |
| -------------------- | ------------------------------------------------------------ |
| `monkeyGUIv3_2.py`   | A pipeline GUI for data management and processing by calling `monkeyUnityv1_6.py` |
| `monkeyUnityv1_6.py` | Where the automation happens. Support command line usage.    |
| `VidSyncLEDv2_3.py`  | Synchronize videos according to LED status in ROI            |
| `ROIConfig-full.py`  | A little helper script to select ROIs for LED detection      |
| eventMarker          | A PyQt5-based video player with up to 5 marker sets, by which one can mark movement events |

![IMG_2740](https://github.com/user-attachments/assets/038a6a96-710f-45dd-b5cb-3c90e1013809)


# `monkeyGUIv3_2`

## Usage

start environment `monkeyUnity` from Anaconda, if `conda` doesn't work in cmd.

```bash
conda activate monkeyUnity
cd "Documents\Python Scripts"
python monkeyGUIv3_2.py
```

And you should see the app.

Typical usage:

### Tab Data Setup

1. Be sure that the experiment notes are filled, especially columns in `['Experiment Number', 'Experiment', 'Task', 'Camera files \n(1 LR)','Camera files \n(2 LL)', 'Camera files (3 RR)', 'Camera files (4 RL)', 'VOID']`
2. Set **`data path`**, 3 ways: input and enter; browse; click **"`Today`"** if processing today's data. You should see a scroll area updated below with info panes about tasks from the data. eg, TS-1, TS-2, TS-3.
3. Click "**`Setup Data Folder`**" **TWICE**. This calls `mky.dataSetup()` and updates internal path variables.

### Tab Video Sync

1. Go through all the four "**`Check ROI`**" to confirm LEDs are in the ROI area. This calls `ROIConfig.show_saved_rois()`
   - If not, click "**`Set ROI`**" and draw the LED area. Also change the LED color (Y=Yellow, G=Green) if needed. Color will affect HSV mask applied in detection.
   - Currently sync must have 4 cams. Can be implemented later. The checkboxes are reserved for that.
2. Click "**`Detect LED`**". **Don't click more than once** since I didn't write a good thread handling here.
3. You can check `\SynchronizedVideos\SyncDetection` to confirm detection.
4. Click "**`Run Sync`**". **Don't click more than once** since I didn't write a good thread handling here.

### Tab DeepLabCut

1. Switch the radio button to local or Colab
2. Check model folder for left and right cam groups are what you need
3. Run DLC
   - Local: There's only one button that looks like a run button
   - Colab
     - Click "**`Move .. to Colab`**". Wait for the videos to be copied to google drive.
     - Go to Colab and run DLC there.
     - Come back after done in Colab, click "**`Fetch .. Colab`**". Wait for the script to pickup *.h5 from google drive. It runs according to animal and date, as given by data path (`self.PPATH_RAW `, `mky.PPATH_RAW`).

### Tab Anipose

1. Check the .toml file is what you need. It will be then copied to the data folder.
2. Click the checkbox if you need to run `label-combined`
3. Click **`Setup anipose folder`**. Wait for it to make files.
4. Click **`Run anipose!`**. Check progress in cmd.

### Bypass usage

If started midway (ie, ran halfway and restarted the GUI) (eg. closed the GUI during Colab processing):

- Before running anything in tab "DLC" or "anipose", click **Detect LED** in Tab Video Sync. This updates internal `self.vid_path`, or it might raise AttributeError.

- If you want to re-run any step, delete corresponding checkpoint files:

  | Checkpoint        | File               | Location                                                     | Appear after                                            |
  | ----------------- | ------------------ | ------------------------------------------------------------ | ------------------------------------------------------- |
  | Setup data folder | Folder in `\DATA\` | -                                                            | -                                                       |
  | Detect LED        | .skipDet           | `SynchronizedVideos\*task*`, each task (4 vids) has a file   | once a set of 4 vids are detected                       |
  | Run Sync          | .skipSync          | `SynchronizedVideos\*task*`, each task (4 vids) has a file   | once a set of 4 vids are sync-ed                        |
  | DeepLabCut        | .skipDLC           | `SynchronizedVideos\*task*\L` or `SynchronizedVideos\*task*\R`, every 2 vids have a file | once DLC processed **two** of the videos in same folder |
  | Move to Colab     | .inColab           | `SynchronizedVideos\*task*\L` or `SynchronizedVideos\*task*\R`, every 2 vids have a file | once all videos in the folder are copied                |
  | Setup anipose     | -                  | it moves videos (not copy) so won't run twice.               | -                                                       |
  | anipose           | -                  | anipose skips processed tasks itself                         | -                                                       |

## Component Hierarchy

No, no MVC/MVVM. Hope you don't debug it.

If, unfortunately, someone is debugging,

- If it's interaction or GUI problem, refer to the tree below:

  - Go to the problematic tab and find the problematic component

  - navigate in source code to its connected function

  - debug there

- If it's business / data processing problem, refer to the tree below:

  - Loop up what function is called

  - go to corresponding .py file under `C:\Users\rnel\Documents\Python Scripts`

    | Module               | Source               |
    | -------------------- | -------------------- |
    | `mky`                | `monkeyUnityv1_5.py` |
    | `ROIConfig`          | `ROIConfig.py`       |
    | `Sync` used in `mky` | `VidSyncLEDv2_3.py`  |

```scss
PipelineGUI (QMainWindow) ── initUI(), setupConnections()
│
├── main_widget (QWidget) ── initUI()
│   └── layout (QVBoxLayout)
│       ├── tabs (QTabWidget) ── adjust_tab_height()
│       │   ├── setup_tab (QWidget) ── createSetupTab()
│       │   │   └── data_setup_grp (QGroupBox) ── dataSetup()
│       │   │       ├── raw_path (QLineEdit) ── update_raw_path()
│       │   │       ├── btn_browse_raw (QPushButton) ── browseRawPath()
│       │   │       ├── btn_today (QPushButton) ── setPathToday()
│       │   │       ├── btn_path_refresh (QPushButton) ── pathRefresh()
│       │   │       ├── btn_data_setup (QPushButton) ── dataSetup()
│       │   │       ├── animal_list (QLineEdit)
│       │   │       └── non_void_scroll_area (QScrollArea) ── displays task info
│       │   │           ├── populateNonVoidRows() ── Updates experiment display
│       │   │           └── data_setup_grp (QGroupBox)
│       │   │
│       │   ├── sync_tab (QWidget) ── createSyncTab()
│       │   │   ├── roi_table (QTableWidget) ── populateROITable()
│       │   │   ├── btn_sync_detect (QPushButton) ── btnDetect() → ConfigSyncWorker (run)
│       │   │   ├── btn_sync_run (QPushButton) ── btnRunSync() → RunSyncWorker (run)
│       │   │   └── sync_cam_btn_set, sync_cam_btn_check (QPushButton) ── setROI(), checkROI()
│       │   │
│       │   ├── dlc_tab (QWidget) ── createDLCTab()
│       │   │   ├── local_dlc (QRadioButton) ── dlc_pane_stat_chg()
│       │   │   ├── colab_dlc (QRadioButton) ── dlc_pane_stat_chg()
│       │   │   ├── btn_toColab (QPushButton) ── toColab() → ToColabWorker (run)
│       │   │   ├── btn_fromColab (QPushButton) ── fromColab() → FromColabWorker (run)
│       │   │   └── btn_run_dlc (QPushButton)
│       │   │
│       │   ├── anipose_tab (QWidget) ── createAniposeTab()
│       │   │   ├── btn_setup_ani (QPushButton) ── setupAnipose() → SetupAniposeWorker (run)
│       │   │   └── btn_run_ani (QPushButton) ── runAnipose() → RunAniposeWorker (run)
│       │   │
│       │   └── tool_tab (QWidget) ── createToolTab()
│       │       ├── edt_xlsx_path (QLineEdit)
│       │       └── btn_xlsx_fill (QPushButton) ── fillExpNote()
│       │
│       └── log_area (QTextEdit) ── logMessage()

Workers (Threads for Background Tasks)
│
├── ConfigSyncWorker ── run() calls mky.configSync()
├── RunSyncWorker ── run() calls mky.syncVid()
├── ToColabWorker ── run() calls mky.copyToGoogle()
├── FromColabWorker ── run() calls mky.pickupFromGoogle()
├── SetupAniposeWorker ── run() calls mky.setupAnipose()
└── RunAniposeWorker ── run() calls mky.runAnipose()
```



# `monkeyUnity` v1.6 Duckumentation 🐒💥

> The former command line version

A script unifying workflow as *Qin Shi Huang* did when unifying the six states.

Digitally immortalize your monkeys.

But WHY ARE YOU EVEN READING THIS?

v 1.1, written Feb 8 2025 by **Mel**

## TLDR

- When writing experiment notes:

  - DO Fill "Experiment", "Task", "Video # From";
  - "Video # From" should be written as `C####` **strictly** #### is from **cam1** video filename
  - If trial is bad, drag to right-most and put a `T` in "VOID"

- Before running the script:

  1. In the source code (yes, modify that), set `PPATH_RAW` to today's folder, begin with `P:\`, end with `YYYYMMDD`; remember to keep magical `r` in front of the string;

  2. Change `CAM_OFFSETS` to today's starting video number in cam1~4, respectively.

  3. Run `conda activate monkeyUnity` in cmd and call `monkeyUnityv1_5` there. Use Anaconda if `conda` doesn't work.

     ```
     conda activate monkeyUnity
     cd "Documents\Python Scripts"
     python monkeyUnityv1_5.py
     ```

## What it does

This script:

1. Sets up the directory structure for your **raw and processed monkey data**, as well as a two-way shortcut for quick teleport.
2. Reads experiment notes from Excel like a very specialized psychic.
3. Synchronizes multi-camera video recordings via `VidSyncLEDv2`.
4. Analyzes videos with **DeepLabCut** (DLC), but no, it won’t get you game DLCs.
5. Prepares everything for **Anipose**. Include adding fake, fixed ref points through `h5rewrite1`.
6. Processes 3D pose data so your monkeys can be immortalized in all their moving glory.

## Configurable Variables Explained

| Var                                    | Notes & restrictions                                         |
| -------------------------------------- | ------------------------------------------------------------ |
| `PPATH_RAW`                            | path to data to be processed. Remember keep it raw string `r' '` or deal with `\` yourself. Or you'll see. |
| `ANIMALS`                              | recognized animal name list. If none of the names is included in `PPATH_RAW`, it raises `ValueError`. |
| `HEADER_KEY`                           | is what will be searched in the xlsx file. The 1st line containing `HEADER_KEY` will be recognized as header line in `readExpNote()`. |
| `ROIs`                                 | is a dict, whose item is passed to `SyncVidLEDv2.find_start_frame()`. It's where it detects pixel intensity. |
| `LEDs`                                 | is like above, passed to sync to determine which channels are to be used for detection. `Y` for yellow LED, `G` for green. |
| `THRES`                                | is threshold of intensity determining if LED is lit. Yes, one threshold for all, for now. |
| `OUTPUT_SIZE`                          | determines output video size, passed to `ffmpeg`. Not recommend to change; it's not tested. But reduce this makes everything faster, though. |
| `CAM_OFFSETS`                          | No need to change now. The script is updating it according to exp notes. |
| `ani_cfg_mothercopy`                   | by default it's `r"C:\Users\rnel\Documents\Python Scripts\config.toml"`. This file will be copied to anipose project. |
| `ani_cfg_mothercopy_add_ref`           | by default it's `r"C:\Users\rnel\Documents\Python Scripts\config-ref.toml"`. This file has info about artificial ref points Fx1~3. |
| `camL` `camR`                          | are definition of L and R naming in folder creations.        |
| `pause_before_sync` `pause_before_dlc` | Set it to`True` if you want a moment to question your life choices before moving on to output sync videos, or DeepLabCut. |
| `Ref`                                  | the position of reference points in 4 cams. Tulip `(x,y,1)` where 1 is possibility. |
| `add_ref`                              | whether you want to fake ref points in DLC outputs or not.   |
| `SCALE_FACTOR`                         | will be multiplied to elements in `Ref`  in case you find the `Ref` is in wrong resolution. |

## Rule Misc for Running the Script

1. If the console asks *`Input y to continue`* more than once, answer only the first. 
   - The second voice is not part of the script.

2. If the video sync is reported to take 6 minutes and 66 seconds, **terminate immediately**. Restart your system. **Do not look at the generated files**.

3. Remember: the synchronization is **very robust**. You shall never see a footage **from an angle you did not record**.
4. If you hear an NHP laughing when working at night, check `data_path/backup/temp/` for `.wav` file.
   - If it exists, play white noise until the file is gone;
   - If not, it's just *fatigue*.
5. If a monkey’s name appears in output `data_path` that isn’t in `ANIMALS`, **leave**. **Report it to your supervisor immediately**. 
6. Anipose projects 3D coords to videos correctly. If the reconstruction includes a silhouette not matching the monkey, **refer to Rule 5**.
7. When a coworker shows up and mentions breaking a tweezer, discreetly confirm whether their badge features a **purple barcode**.
   - If there isn't one, **switch the topics**. The badge has been recalled by ██████ last week.
8. Never overload the script with over 12 trials.
   - The 13th time it processes *you* instead.

## Dependencies

This script will need to run in env: `conda activate monkeyUnity`, an env derived (actually copied) from DLC_GPU on this computer (hope you know which one).

Non-standard libs included in the environment: `pandas`, `deeplabcut`, `anipose`;

Two homemade scripts: `VidSyncLEDv2` to sync vids based on LED; `h5rewrite1` to add fixed reference points into DLC outputs. Stored in `C:\Users\rnel\Documents\Python Scripts`. This path is appended to PATH before import.

The script will start a new conda env as `conda activate anipose_3d` due to some unsolvable conflicts, just to run anipose.

## Data Structure

### Input data from experiment

Change variable `PPATH_RAW` to tell the script what to process. Raw data should live here:

- `P:\*whatever*\DATA_RAW\{ANIMAL}\YEAR\MONTH\YYYYMMDD`

e.g.

- `P:\projects\monkeys\Chronic_VLL\DATA_RAW\PICI\2025\02\20250206`

`{ANIMAL}` is monkey name being tested and should be in constant array `ANIMALS`, or it will trigger defense against invasion of evil monkeys.

`YYYYMMDD` can be written as `YYMMDD` as well. It's ok. For now. The script doesn't detect date format.

What should be under `PPATH_RAW` are xlsx plus cam folders:

```
DATA_RAW(date)
│── cam1
│   ├── C####.mp4
│── cam2
│   ├── C####.mp4
│── cam3
│   ├── C####.mp4
│── cam4
│   ├── C####.mp4
│── {ANIMAL}_{date}.xlsx
```



- `{ANIMAL}_{DATE}.xlsx` This **date** **should strictly match** base-name date in `PPATH_RAW`!
- vids `C####.mp4`, must have a letter followed by numbers, must be mp4

Note that **only** the format `cam[1-4]` can be recognized. Relative to the monkey facing, left back is 1, then 2, 3, 4 goes clockwise.

If you see the command line is giving super fast outputs, check if you mess the folder name.

### Output data in DATA

The script's output path is generated by substituting `DATA_RAW` to `DATA` and keeping everything else. Under the path there will be:

```
{date}
│── SynchronizedVideos
│   ├── {date}-{animal}-{experiment}-{task}
│   │   ├── L
│   │   ├── R
│   │   ├── .skipDet
│   │   ├── .skipSync
│   │   ├── sync_config_{experiment}-{task}-####.json
│── anipose
│   ├── {date}-{animal}-{experiment}-{task}
│   │   ├── calibration
│   │   ├── pose-2d-filtered
│   │   ├── pose-3d
│   │   ├── videos-3d
│   │   ├── videos-combined
│   │   ├── videos-raw
│   │   config.toml
```

- `SynchronizedVideos`
  - Videos disappear when running `setupAnipose()`. No panic, they are moved to `\anipose\videos-raw`.
- `anipose`
  - `config.toml` doesn't appear until script runs `setupAnipose()`. Copied from `C:\Users\rnel\Documents\Python Scripts`. If add_ref is set to `True`, it copies the file `config-ref.toml` that includes info for fixed points (artificial) `Fx1~3`, otherwise copies `config.toml`.

## Code structure

Written by ChatGPT4o. Hope you don't get lost in the code. I'm lost already.

```scss
Main Script (__main__)
├── updateOffset()          - Updates CAM_OFFSETS based on video filenames
├── _infoFromPath()         - Extracts animal and date info from path
├── dataSetup()             - Sets up necessary data folders
│   └── two_way_shortcuts() - Creates two-way shortcuts between folders
├── configSync()            - Reads experiment notes and configures sync
│   └── readExpNote()       - Reads experiment data from Excel
│   └── updateOffset()      - Adjusts camera offsets
├── syncVid()               - Synchronizes videos using Sync.process_videos()
├── copyToGoogle()          - Copies videos to Google Drive for Colab
├── pickupFromGoogle()      - Retrieves processed data from Google Drive
├── setupAnipose()          - Organizes data for Anipose processing
│   └── add_fixed_points()  - Adds reference points (from h5rewrite1)
├── runAnipose()            - Runs Anipose triangulation and labeling via subprocess
└── (Paused) Steps          - User interactions:
    ├── Pause before sync
    └── Pause before running DeepLabCut (DLC)
```



# `VidSyncLEDv2_3`

pass

# `ROIConfig`

pass

