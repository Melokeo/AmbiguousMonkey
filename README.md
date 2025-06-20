# Ambiguous Monkey

A fully rewritten deeplabcut+anipose data managing and processing package

Mel

2025.6

![IMG_2740](https://github.com/user-attachments/assets/038a6a96-710f-45dd-b5cb-3c90e1013809)
## Overview

Currently it runs as separate sub-modules.

...

## Dependency

See `amm-env.yaml`.

## Pipeline

Code examples are in `ammonkey_example.py`. Here explains the ideas how it works

### Some terms

- **DAET** refers to a combination of Date-Animal-Experiment-Task, used as a unique identifier of each experiment entry.
- **Raw path** is the path where raw data is dumped. 
  - Must contain string `'DATA_RAW'`.  This behavior can be changed by modifying `.core.expNote.getDataPath()`.
  - Must follow `DATA_RAW/(animal_name)/yyyy/mm/dd/yyyymmdd`. This is parsed in `ExpNote._parsePathInfo()`
  - Data in the path should be kept intact and not allowed to modify for integrity.
- **Data path** is the path where all processed data will appear.
  - Converted from raw path by just replacing `DATA_RAW` -> `DATA`.
- dlc == deeplabcut
- ani == anipose

### Data setup

- Create date folder in data path using `dataSetup(raw_path | data_path)`
  - Create subfolders: SynchronizedVideos, anipose, clean
  - Create two-way shortcuts between raw and data path

### Synchronization

- Need an object `VidSynchronizer()`
- Setup sync detection
  - ROI for LED detection
  - LED color (for color masking)
- Run sync `results = synchronizer.syncAll()`
  - returns a dict containing success statuses

### DeepLabCut

- Need an object `DLCProcessor()`

  - Create from note + model dict
  - OR create from presets: `createProcessor_{task}()`

- Video dlc-model assignment is determined by model_dict

  ```python
  from ammonkey.core.dlc import CamGroup, DLCModel
  
  # format
  model_dict: dict[CamGroup, DLCModel]
  
  # eg
  model_dict = {
      CamGroup.Left: modelPreset('TS-L'),
      CamGroup.Right: modelPreset('TS-R'),
  }
  ```

- Run dlc using `DLCProcessor.batchProcess()`

- After dlc analysis the results (.h5 files) will be collected to `SynchronizedVideos/{DAET}/DLC/{model_set_name}`

  - `model_set_name` is named according to model_dict and process date. eg. TS-L + TS-R => TS-LR-yyyymmdd_0000
  - last 4 digits of model_set_name is from md5 of the models serving as identifier

- Current model_set_names

  | Host  | ID   | From models             |
  | ----- | ---- | ----------------------- |
  | WS120 | 7637 | TS-L[1476] + TS-R[4237] |
  | WS120 | 5608 | BBT[5608]               |
  | WS120 |      | Brinkman[]              |



### Anipose

- Need `AniposeProcessor()`
  - Create from note + model_set_name
  - currently no library for model_set_name so you'll need to type in.
- Setup anipose structure
- run anipose triangulate

### Finalize

use `violentCollect()` to collect csvs into folder `clean`

# Tech Details

Below are module-specific docs generated by chatGPT.

## ExpNote / DAET

### 1. Purpose  

`ExpNote` and `DAET` together provide a lightweight, hash-friendly way to label, load, and query experimental video-note spreadsheets. `DAET` is an **immutable identifier** (*Date-Animal-Experiment-Task*), while `ExpNote` is a **high-level interface** that turns an Excel sheet plus a folder tree into easily filterable Python objects.:contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1}  

---

### 2. Key Concepts  

| Concept     | What it means                                                |
| ----------- | ------------------------------------------------------------ |
| **DAET**    | A frozen dataclass stringified as `YYYYMMDD-Animal-Experiment-Task`; unique & hashable. |
| **Task**    | Enum describing experiment categories (`TS`, `BBT`, `BRKM`, `PULL`, `CALIB`, `ALL`). |
| **ExpNote** | Loader/manager that converts an Excel notes file into DAET-centric records and video paths. |

---

### 3. Quick-start Example  

```python
from pathlib import Path
from ammonkey.expNote import ExpNote, Task

root = Path(r'P:\projects\monkeys\DATA_RAW\Pici\2025\04\20250403')
notes = ExpNote(root)          # auto-parses animal/date and loads Excel
print(notes)                   # ➜ ExperimentNotes(Pici 20250403 with N entries)

# Access all DAETs
for daet in notes.daets:
    print(daet)

# Filter for a specific task
ts_df = notes.filterByTask(Task.TS)
print(ts_df[['daet', 'Experiment']])

# Get video existence map for the first valid entry
first_valid = notes.getValidDaets()[0]
print(notes.checkVideoExistence(first_valid))
```

------

### 4. Public API Summary

#### 4.1 `class DAET(date:str, animal:str, experiment:str, task:str)`

| Member                       | Description                               |
| ---------------------------- | ----------------------------------------- |
| `.d`                         | Alias for `str(daet)`                     |
| `.year`                      | Four-digit `int` year                     |
| `.isCalib`                   | `True` if `"calib"` in experiment         |
| `fromString(s)`              | Parse a `YYYYMMDD-Animal-Exp-Task` string |
| `fromRow(row, date, animal)` | Build from a Pandas row inside `ExpNote`  |

#### 4.2 `class ExpNote(path, *, header_key='Experiment', …)`

| Member                                              | Use                                    |
| --------------------------------------------------- | -------------------------------------- |
| `.daets` / `getDaets()`                             | List of all DAET objects in the sheet  |
| `getRow(daet)`                                      | Return Pandas row for a DAET           |
| `getVidSetIdx(daet)`                                | `[int                                  |
| `getVidPath(daet, cam_idx)`                         | Absolute `Path` to a single video file |
| `checkVideoExistence(daet)`                         | `{cam_idx: bool}` map of found files   |
| `filterByTask(task)`                                | DataFrame subset by `Task` enum        |
| `getValidDaets(min_videos=2, skip_void=True)`       | DAETs ready for processing             |
| `getSummary()`                                      | Dict with counts for quick reporting   |
| `dupWithWhiteList(list)` / `dupWithBlackList(list)` | Return filtered copies                 |

------

### 5. Typical Workflow

1. **Instantiate** `ExpNote` with the raw-data folder that contains an `Animal_Date.xlsx`.
2. **Inspect** `notes.getSummary()` to verify entry counts.
3. **Filter/Select** DAETs via `getValidDaets()` or `filterByTask()`.
4. **Locate Videos** by calling `getVidPath()` or `getVidSetPaths()`.
5. **Process** only when `checkVideoExistence()` confirms required files.

------

### 6. Error Handling & Logging

- Missing Excel columns raise `ValueError`; missing files log warnings but do not crash.
- Duplicate DAETs or malformed rows are reported through the module’s logger (`__name__`).
- Incorrect date formats in `DAET` raise `ValueError` at construction time.

------

### 7. Best Practices

- Keep Excel headers exactly matched; customize `header_key` only if the sheet layout differs.
- Use the `Task` enum everywhere instead of raw strings to avoid typos.
- Because `DAET` is frozen and hashable, it can be used as a dictionary key or set element safely across a session.
- For reproducibility across runs, store the *string* form of a DAET rather than relying on Python `hash()` values, which vary per interpreter session.

------

### 8. Version Compatibility

Both classes rely only on the Python ≥ 3.10 standard library plus **pandas** ≥ 1.5. If your workflow touches on video paths, ensure the folder layout remains:

```
root/
│  Animal_Date.xlsx
├─ cam1/
├─ cam2/
├─ cam3/
└─ cam4/
```

Any deviation requires overriding `cam_headers` or extending `getVidPath`.

## Video Synchronization

### 1. Purpose  

`sync.py` implements a complete pipeline to detect and correct timestamp offsets across multi-camera video sets using LED flashes and audio cues. It produces per-DAET JSON configs and optionally writes synchronized output videos. :contentReference[oaicite:0]{index=0}

---

### 2. Key Components  

| Class / Function      | Role                                                         |
| --------------------- | ------------------------------------------------------------ |
| **`SyncConfig`**      | Holds thresholds, durations, file extensions and flags for detection & override. |
| **`SyncResult`**      | Immutable record of LED starts, audio starts, corrected frames, status & message. |
| **`VidSynchronizer`** | Orchestrates detection (audio + LED), cross-validation, config writing, and final video sync. |
| **`syncVideos(...)`** | Convenience function: prepares folders, invokes `VidSynchronizer`, returns results. |

---

### 3. Quick-start Example  

```python
from ammonkey.expNote import ExpNote, Task
from ammonkey.sync import syncVideos, SyncConfig, CamConfig

notes = ExpNote(r'P:\projects\monkeys\DATA_RAW\Pici\2025\04\20250403')
cam_cfg = CamConfig()                  # default camera ROIs & LED colors
sync_cfg = SyncConfig(override_existing=True)

# Run full sync for Task.BBT only
results = syncVideos(notes,
                     cam_cfg=cam_cfg,
                     sync_cfg=sync_cfg,
                     task=Task.BBT)

# Inspect outcomes
for res in results:
    print(f"{res.daet}: {res.status} — {res.message}")
```

------

### 4. Public API Summary

#### 4.1 `SyncConfig(...)`

- **`audio_test_duration`**: seconds for detection window
- **`led_threshold`**, **`cross_validation_threshold`**: pixel & frame-offset tolerances
- **`video_extension`**, **`output_size`**: format & resolution for output
- **`override_existing`**: reprocess existing detections/syncs

#### 4.2 `SyncResult`

- **`.daet`**: associated DAET
- **`.led_starts`**, **`.audio_starts`**, **`.corrected_starts`**: per-cam frame lists
- **`.status`**: `'success'`, `'warning'`, or `'failed'`
- **`.message`**: diagnostic text
- **`.config_path`**: JSON file location if created

#### 4.3 `VidSynchronizer`

- **`.setROI(daet=None, frame=500)`**: launch ROI selector for LED zones.
- **`.syncAll(task, skip_existing=True)`**: run detection + video sync for all valid DAETs.
- **`._runAudioSync(daets)`**, **`._runLEDSync(daet, audio_starts)`**: low-level detectors.
- **`._crossValidate(led_starts, audio_starts)`**: align LED vs audio, interpolate or flag errors.
- **`._createSyncConfig(...)`**: write per-DAET JSON for `SyncLED.process_videos`.

#### 4.4 `syncVideos(...)`

- Prepares folders via `dataSetup`
- Instantiates `VidSynchronizer` and runs ROI setup
- Returns list of `SyncResult` objects

------

### 5. Typical Workflow

1. **Prepare** raw folder with Excel notes (`ExpNote`) and camera subfolders.
2. **Import** and configure: instantiate `SyncConfig` (tuning thresholds) and optional `CamConfig`.
3. **Run** `syncVideos(notes, cam_cfg, sync_cfg, task)` to detect & sync.
4. **Review** console/log for `SyncResult` statuses.
5. **Inspect** generated JSON configs in each DAET’s `SynchronizedVideos` folder.
6. **Locate** final synced videos under `SynchronizedVideos/{group}/` subfolders.

------

### 6. Error Handling & Logging

- Uses `Wood` logger to write per-phase logs under `notes.data_path`.
- Falls back to audio-only if LED fails; marks as warning or failed based on deviation counts.
- Missing videos or ROI configs emit warnings but continue processing other cams.
- Exceptions during detection/sync produce a `SyncResult` with `status='failed'` and error message.

------

### 7. Best Practices

- **ROI Configuration:** call `.setROI()` once interactively before batch runs.
- **Threshold Tuning:** adjust `led_threshold` and `cross_validation_threshold` on a small sample to minimize false detections.
- **Data Organization:** maintain consistent camera folders (`cam1`–`cam4`) and file naming to match `ExpNote` conventions.
- **Idempotency:** use `override_existing=False` in `SyncConfig` to skip already processed entries.

------

### 8. Version Compatibility

- **Python ≥ 3.10**, **pandas ≥ 1.5**, plus dependencies for `SyncLED`, `SyncAud`, and `ROIConfig`.
- Relies on the same folder layout as `ExpNote`.
- Tested on Windows & Linux file paths but uses `pathlib` for cross-platform support.

## DLC Analysis

### 1. Purpose  

`dlc.py` defines `DLCModel` and `DLCProcessor` to run DeepLabCut pose estimation on synchronized video folders. `dlcCollector.py` adapts and merges per-model outputs into a single folder for downstream analysis. 

---

### 2. Key Components  

| Component                     | Role                                                         |
| ----------------------------- | ------------------------------------------------------------ |
| `initDlc()`                   | Lazy-imports DeepLabCut, sets `ready` flag.                  |
| `DLCModel`                    | Frozen dataclass wrapping model config; methods: `runOnce()`, `pee()`, path helpers. |
| `DLCProcessor`                | Orchestrates batch processing: loads sync roots, skips calibration, merges outputs. |
| `mergeDlcOutput(*folders)`    | Combines separate model outputs into a merged folder, writes combined `inherit.json`. |
| `copyH5(src, dst)`            | Copies filtered H5 files for merging.                        |
| `getDLCMergedFolderName(...)` | Generates merged folder names from per-model final names.    |

---

### 3. Quick-start Example  

```python
from ammonkey.expNote import ExpNote
from ammonkey.sync import syncVideos, Task
from ammonkey.dlc import initDlc, createProcessor_BBT

# 1. Initialize DLC
initDlc()

# 2. Load experiment notes and synchronize videos
notes = ExpNote(r'P:\projects\monkeys\DATA_RAW\Pici\2025\04\20250403')
syncVideos(notes, task=Task.BBT)

# 3. Create processor for BBT and run batch DLC
processor = createProcessor_BBT(notes)
results = processor.batchProcess()  # dict of DAET → success flag
```

------

### 4. Public API Summary

#### `initDlc() → int`

Imports DeepLabCut; returns `1` on success, `0` on failure.

#### `class DLCModel`

- `.runOnce(vid_path, override_exist=True) → bool` — run DLC on one folder.
- `.md5_short`, `.final_folder_name` — unique identifiers.
- `.information() → list[str]` — diagnostic info.
- `.pee(vid_path)` — isolates output files, writes logs and `inherit.json`. 

#### `class DLCProcessor`

- `.analyzeSingleDaet(daet) → bool` — process one DAET.
- `.batchProcess(daets=None, min_videos=2) → dict[DAET, bool]` — loop over DAETs.

#### `mergeDlcOutput(*folders) → int`

Validates input folders, copies H5 files, writes merged `inherit.json`. 

------

### 5. Typical Workflow

1. **Call** `initDlc()` at startup.
2. **Instantiate** `ExpNote` and **synchronize** videos with `syncVideos()`.
3. **Create** a `DLCProcessor` via a factory (`createProcessor_TS/Pull/BBT/Brkm`).
4. **Run** `processor.batchProcess()` to perform DLC analysis.
5. **Find** merged outputs under `{DAET}/DLC/{merged_folder}`.

------

### 6. Error Handling & Logging

- Initialization errors and missing models log via Python `logging`.
- `runOnce()` logs and returns `False` on import errors, missing paths, or analysis failures.
- `mergeDlcOutput()` raises on nonexistent folders or invalid argument counts.
- All per-DAET logs and merged JSON live under `note.data_path / 'SynchronizedVideos'`.

------

### 7. Best Practices

- Always **lazy-import** DeepLabCut with `initDlc()` before running models.
- Use **processor factories** (`createProcessor_*`) to ensure consistent model presets.
- Skip calibration DAETs automatically; no extra filtering needed.
- Inspect JSON logs (`inherit.json`) for reproducibility rather than relying on in-memory hashes.

------

### 8. Version Compatibility

- Python ≥ 3.10
- DeepLabCut installed in the same environment
- pandas ≥ 1.5 (for `ExpNote`)
- Compatible with Windows & Linux via `pathlib`

## Anipose Processing & Finalization

### 1. Purpose  

`ani.py` automates camera-calibration, video preparation, and 3D triangulation via the Anipose CLI. `finalize.py` gathers all generated 3D-pose CSVs into a clean folder structure and logs the collection.   

---

### 2. Key Components  

| Component / Function                                   | Role                                                         |
| ------------------------------------------------------ | ------------------------------------------------------------ |
| `getH5Rename(file_name, stem_only=False)`              | Strip DLC postfix from H5 filenames                          |
| `insertModelToH5Name(...)`                             | *(stub)* Intended to inject model tag into H5 filename       |
| **`CalibLib`**                                         | Indexes historical calibration TOML files and finds closest match by date |
| **`AniposeProcessor`**                                 | Manages per-DAET folder setup, calibration copy, CLI calls (`calibrate`, `triangulate`), and log writing |
| `violentCollect(ani_path, clean_path)`                 | Copy all `*.csv` from `pose-3d` subfolders into a single `"clean"` directory |
| `writeProcedureSummaryCsv(note, ani_path, clean_path)` | *(stub)* Intended to summarize DAET procedures into a single CSV |

---

### 3. Quick-start Example  

```python
from pathlib import Path
from monkeylab.expNote import ExpNote
from monkeylab.ani import AniposeProcessor, CalibLib
from monkeylab.finalize import violentCollect

# 1. Load notes and configure Anipose
notes = ExpNote(r'P:\projects\monkeys\DATA_RAW\Pici\2025\04\20250403')
processor = AniposeProcessor(note=notes, model_set_name='BBT-LR')

# 2. Prepare calibration files and root config
processor.setupCalibs()
processor.setupRoot()

# 3. Batch-setup 2D outputs and run triangulation
processor.batchSetup(use_filtered=True)
processor.calibrate()       # runs `anipose calibrate`
processor.triangulate()     # runs `anipose triangulate`

# 4. Collect all final CSVs
clean_dir = Path(r'P:\projects\monkeys\CLEAN_CSV')
violentCollect(processor.ani_root_path, clean_dir)
```

------

### 4. Public API Summary

#### `getH5Rename(file_name, stem_only=False) → str`

Remove auto-generated DLC postfix (`_DLC_resnet…_shuffle…`) from H5 filenames.

#### `class CalibLib(lib_path: Path)`

- `.updateLibIndex()` — scan `*.toml` calibration files into a date→list index.
- `.lookUp(date: int) → Path | None` — return exact or closest‐prior TOML; logs fallback.

#### `class AniposeProcessor(note, model_set_name, ...)`

- `.setupCalibs()` — copy each DAET’s raw videos into per-DAET calibration folders.
- `.setupRoot()` — copy `config.toml` and ensure `calibration.toml` exist in root.
- `.setupSingleDaet(daet, use_filtered, copy_videos)` — prepare H5, logs, and calibs for one DAET.
- `.batchSetup(use_filtered, copy_videos)` — run `setupSingleDaet` for all DAETs.
- `.calibrate()` / `.triangulate()` — invoke Anipose CLI via `subprocess`.
- `.pee(daet_root)` — append triangulation record to `scent.log`.

#### `violentCollect(ani_path: Path, clean_path: Path) → None`

Copy all CSVs under `ani_path/pose-3d` into `clean_path/{ani_name}` and write a timestamped log.

#### `writeProcedureSummaryCsv(...)`

*(to be implemented)* Summarize per-DAET processing steps into a master CSV.

------

### 5. Typical Workflow

1. **Instantiate** `ExpNote` and **create** `AniposeProcessor`.
2. **Populate** calibration library with `setupCalibs()`.
3. **Initialize** root with `setupRoot()`.
4. **Copy** filtered or unfiltered H5 and calibration files via `batchSetup()`.
5. **Run** Anipose CLI commands: `.calibrate()` then `.triangulate()`.
6. **Collect** final CSVs using `violentCollect()` (and later implement `writeProcedureSummaryCsv()`).

------

### 6. Error Handling & Logging

- Missing calibration folder raises `FileNotFoundError`.
- Fallback calibration selection logs a `WARNING`.
- Copy errors log via `logger.error` and continue.
- `violentCollect` skips existing CSVs; raises on invalid paths.

------

### 7. Best Practices

- **Pre-populate** `calib history` with well-named TOML files (`calibration-YYYYMMDD…`).
- **Run** `setupCalibs()` once per model set before any triangulation.
- **Verify** that `config.toml` and `calibration.toml` exist under `ani_root_path`.
- **Use** `use_filtered=True` to process only filtered 2D poses.
- **Implement** `writeProcedureSummaryCsv` to automate batch reporting.

------

### 8. Version Compatibility

- Python ≥ 3.10 (relies on `dataclasses`, `pathlib`, `subprocess`).
- Anipose CLI installed in specified `conda_env`.
- pandas ≥ 1.5 (for `ExpNote` integration).
- Compatible with Windows & POSIX paths via `pathlib`.

