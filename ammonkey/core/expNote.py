'''class ExpNote: reads, processes and stores experiment notes'''

import logging
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd
from enum import Enum, auto
import re
from typing import Iterator
import os, glob

from .fileOp import getDataPath
from .daet import DAET, Task, task_match
from .config import Config
from .camConfig import CamConfig

logger = logging.getLogger(__name__)

ANIMALS = Config.animals

@dataclass
class ExpNote:
    """
    Load and manage experiment notes from Excel with DAET-based interface.
    """
    path: Path
    header_key: str = 'Experiment'  # used when searching header line in note file
    skip_markers: list[str] = field(default_factory=lambda: ['x', '-', 'NaN'])
    video_extension: str = 'mp4'
    cam_config: CamConfig = None #type: ignore
    #TODO move these to a separate note adaptor

    # computed fields
    df: pd.DataFrame = field(init=False)
    animal: str = field(init=False)
    date: str = field(init=False)
    data_path: Path = field(init=False)
    _task_patterns: dict[Task, list[str]] = field(
        init=False, 
        default_factory= lambda: task_match,
    ) 

    def __post_init__(self):
        self.path = Path(self.path)
        if self.path.is_file() and self.path.name.endswith('.xlsx'):
            self.path = self.path.parent

        self.animal, self.date = self._parsePathInfo()

        xlsx_path = self.path / f'{self.animal}_{self.date}.xlsx'
        if not xlsx_path.exists():
            raise FileNotFoundError(f'Notes file not found: {xlsx_path}')
        
        self.cam_config = self.cam_config or CamConfig()
        self.cam_headers: list[str] = list(self.cam_config.headers_in_note.values())
        if '_N/A_' in self.cam_headers:
            logger.warning(f'One or more camera headers are empty in config, video reading may fail.')

        self.df = self._loadDataFrame(xlsx_path)   

        self.data_path = getDataPath(self.path) 
        if not self.data_path.exists():
            logger.warning(f'data_path does not exist {self.data_path}')

        self._daets: dict[str, DAET] = {}
        self._buildDaetIdx()
        self.renameDuplicateDaets()

        self._daets_by_task: dict[Task, list[DAET]] = {}
        for daet in self.daets:
            if daet.task_type is not None:
                self._daets_by_task.setdefault(daet.task_type, []).append(daet)
    
    @property
    def sync_path(self) -> Path:
        return self.data_path / 'SynchronizedVideos'
    
    @property
    def daets_by_task(self) -> dict[Task, list[DAET]]:
        return self._daets_by_task
    
    @property
    def has_calib(self) -> bool:
        '''whether this note obj contains at least one Task.CALIB entry'''
        return Task.CALIB in self.getAllTaskTypes()

    def _buildDaetIdx(self):
        '''build index from df'''
        for _, r in self.df.iterrows():
            try:
                daet = DAET.fromRow(r, self.date, self.animal)
                if not str(daet) in self._daets.keys():
                    self._daets[str(daet)] = daet
                else:
                    logger.warning(f'!! Duplicative daet: {str(daet)}')
            except ValueError as e:
                logger.error(f'Invalid DAET during ExpNote build: {e}')

    def _parsePathInfo(self) -> tuple[str, str]:
        """extract animal and date from path structure""" # fragile
        parts = self.path.parts
        # flexible: try common patterns
        if len(parts) >= 4 and parts[-4].lower() in ANIMALS: 
            return parts[-4], parts[-1]
        elif len(parts) >= 2:  # fallback - look for known animals
            animal = next((p for p in parts if p.lower() in ANIMALS), parts[-2])
            return animal, parts[-1]
        else:
            raise ValueError(f'Too less parts in path {self.path}')
    
    def _cleanXlsx(self, df: pd.DataFrame) -> pd.DataFrame:
        '''you never know what your colleagues dump into the notes.
        empty lines, duplicates, typos, missing columns, pasta from yesterday...
        namluepao quebulege heteidongsi'''
        df = df[
            df['Experiment'].notna() &
            df['Task'].notna() &
            (df['Experiment'].astype(str).str.strip() != '') &
            (df['Task'].astype(str).str.strip() != '')
        ].reset_index(drop=True)
        return df

    def _loadDataFrame(self, xlsx_path: Path) -> pd.DataFrame:
        """load xlsx with header detection and validation"""
        try:
            raw = pd.read_excel(xlsx_path, header=None)
            header_idx = raw[raw.apply(
                lambda r: r.astype(str).str.contains(self.header_key, na=False).any(), axis=1
            )].index[0]
            df = pd.read_excel(xlsx_path, header=header_idx)
            df = self._cleanXlsx(df)
            
            # validate required columns exist
            missing_base = [col for col in ['Experiment', 'Task'] if col not in df.columns]
            if missing_base:
                raise ValueError(f'Missing required columns: {missing_base}')
            
            # warn about missing camera columns
            missing_cams = [hdr for hdr in self.cam_headers if hdr not in df.columns]
            if missing_cams:
                logger.warning(f'Missing camera columns: {missing_cams}')
                raise KeyError(f'Check the experiment note file.')
                # add missing columns as empty
                for hdr in missing_cams:
                    df[hdr] = None
            
            # add computed columns
            df['daet'] = df.apply(lambda r: DAET.fromRow(r, self.date, self.animal), axis=1) # type: ignore
            void_col = df.get('VOID', pd.Series('', index=df.index))
            df['is_void'] = void_col.astype(str).str.upper().isin(['T', 'TRUE', '1'])
            df['is_calib'] = df['Experiment'].astype(str).str.contains('calib', case=False, na=False)
            
            return df
        except Exception as e:
            raise RuntimeError(f'Failed loading {xlsx_path}: {e}')
        
    def _daetOrNumber(self, daet: DAET|None, no: int|None) -> DAET | None:
        '''allows daet input by index'''
        if isinstance(daet, DAET):
            return daet
        elif daet is None and no is not None:
            try:
                daet = self.daets[no]
                return daet
            except IndexError as e:
                logger.error(f'ExpNote: daet index out of range. {e}')
                return None
        else:
            logger.error(f'ExpNote: need to specify either daet or index.')
            return None

    # === Core Interface ===
    
    @property
    def daets(self) -> list[DAET]:
        return self.getDaets()

    def getDaets(self) -> list[DAET]:
        """get all DAET identifiers"""
        return self.df['daet'].tolist()

    def getRow(self, daet: DAET) -> pd.Series | None:
        """get row for given DAET"""
        mask = self.df['daet'] == daet
        matches = self.df[mask]
        return matches.iloc[0] if not matches.empty else None
    
    def getDaetSyncRoot(self, daet: DAET) -> Path:
        return self.sync_path / str(daet)
    
    def getDaetSyncVidDirs(self, daet: DAET) -> list[Path]:
        sync_root = self.getDaetSyncRoot(daet)
        vid_dirs = [sync_root / g.value for g in self.cam_config.evolved_groups]
        return vid_dirs
    
    def getDaetDlcRoot(self, daet: DAET) -> Path:
        return self.getDaetSyncRoot(daet) / 'DLC'
    
    def getAniRoot(self) -> Path:
        return self.data_path / 'anipose'

    def getCleanDir(self) -> Path:
        return self.data_path / 'clean'

    def getVidSetIdx(self, daet: DAET|None = None, no: int|None = None) -> list[int|None]:
        """
        Get video IDs for a DAET, logging a warning for each invalid ID once.
        This is the single source of truth for video IDs.
        """
        daet = self._daetOrNumber(daet, no)
        if not daet:
            raise ValueError(f'DAET not found: {daet}')

        rec = self.getRow(daet)
        if rec is None:
            return []

        vids = []
        for hdr in self.cam_headers:
            val = rec.get(hdr)
            if val is None or pd.isna(val) or str(val).lower() in self.skip_markers:
                vids.append(None)
                continue
            try:
                vids.append(int(val))
            except (ValueError, TypeError):
                # annoying warning... :(
                logging.warning(f'Invalid video ID "{val}" in {hdr} for {daet}')
                vids.append(None)
        return vids

    def _find_vid_path(self, vid_id: int|None, cam_idx: int) -> Path|None:
        """Private helper to find a single video file path given an ID and camera index."""
        if vid_id is None:
            return None

        cam_folder = self.path / f'cam{cam_idx + 1}'
        if not cam_folder.is_dir():
            return None

        # Try both 4-digit and 5-digit formats
        for digits in [4, 5]:
            vid_filename = f'C{vid_id:0{digits}d}.{self.video_extension}'
            vid_path = cam_folder / vid_filename
            if vid_path.is_file():
                return vid_path
        return None

    def getVidSetPaths(self, daet: DAET) -> list[Path|None]:
        """Gets all video paths for a DAET"""
        vid_set = self.getVidSetIdx(daet)
        if not vid_set:
            return []
        
        # get all paths
        return [self._find_vid_path(vid_id, i) for i, vid_id in enumerate(vid_set)]

    def getVidPath(self, daet: DAET, cam_idx: int) -> Path|None:
        """Gets a single video file path"""
        vid_set = self.getVidSetIdx(daet)
        if not vid_set or not (0 <= cam_idx < len(vid_set)):
            return None
        
        return self._find_vid_path(vid_set[cam_idx], cam_idx)

    def checkVideoExistence(self, daet: DAET|None = None, no: int|None= None) -> dict[int, bool]:
        """Checks if video files exist in a row"""
        daet = self._daetOrNumber(daet, no)
        if not daet:
            raise ValueError(f'Invalid daet / number: {daet=}, {no=}')

        # calls getVidSetIdx only once, indirectly.
        vid_paths = self.getVidSetPaths(daet)
        return {cam_idx: path is not None for cam_idx, path in enumerate(vid_paths)}

    def getCalibs(self, skip_void: bool = True) -> list[DAET]:
        """get list of calibration DAETs
        
        Args:
            skip_void: whether to exclude void calibration entries
        """
        calib_df = self.df[self.df['is_calib']]
        
        if skip_void:
            calib_df = calib_df[~calib_df['is_void']]
        
        return calib_df['daet'].tolist()

    def filterByTask(self, task: Task) -> pd.DataFrame:
        """filter entries by task type"""
        if task == Task.ALL:
            return self.df.copy()
        
        patterns = self._task_patterns.get(task, [])
        if not patterns:
            return pd.DataFrame()
            
        pattern = '|'.join(patterns)
        mask = self.df['Experiment'].astype(str).str.contains(pattern, case=False, na=False)
        return self.df[mask].copy()

    def getValidDaets(self, min_videos: int = 2, skip_void: bool = True) -> list[DAET]:
        """get DAETs suitable for processing"""
        df = self.df.copy()
        if skip_void:
            df = df[~df['is_void']]
            
        valid_daets = []
        for daet in df['daet']:
            video_count = sum(1 for v in self.getVidSetIdx(daet) if v is not None)
            if video_count >= min_videos:
                valid_daets.append(daet)
                
        return valid_daets
    
    def hasDaet(self, daet_to_check:DAET):
        return daet_to_check in self.daets
    
    # === method to filter tasks ===
    def dupWithWhiteList(self, whitelist: list[DAET]) -> 'ExpNote':
        """create copy with only whitelisted DAETs"""
        # create new instance with same init params
        new_note = ExpNote(
            path=self.path,
            header_key=self.header_key,
            cam_config=self.cam_config,
            skip_markers=self.skip_markers.copy(),
            video_extension=self.video_extension
        )
        
        # filter dataframe to whitelist only
        whitelist_set = set(whitelist)
        new_note.df = self.df[self.df['daet'].isin(whitelist_set)].copy().reset_index(drop=True)
        
        # rebuild daet index for filtered data
        new_note._daets = {str(daet): daet for daet in whitelist if daet in self._daets}
        
        return new_note

    def dupWithBlackList(self, blacklist: list[DAET]) -> 'ExpNote':
        """create copy with blacklisted DAETs removed"""
        # create new instance with same init params
        new_note = ExpNote(
            path=self.path,
            header_key=self.header_key,
            cam_config=self.cam_config,
            skip_markers=self.skip_markers.copy(),
            video_extension=self.video_extension
        )
        
        # filter dataframe to exclude blacklist
        blacklist_set = set(blacklist)
        new_note.df = self.df[~self.df['daet'].isin(blacklist_set)].copy().reset_index(drop=True)
        
        # rebuild daet index for filtered data
        new_note._daets = {
            str(daet): daet 
            for daet in self._daets.values() 
            if daet not in blacklist_set
        }
        
        return new_note
    
    def applyTaskFilter(self, tasks:list[Task], exclude:bool=False) -> 'ExpNote':
        '''returns a duplicate of the ExpNote with filtered tasks. 
        by default include all tasks in list[Task].
        Exclude list[Task] if exclude==True'''
        if isinstance(tasks, Task):
            tasks = [tasks]
            
        matched_daets: list[DAET] = [
            daet for daet in self.daets 
            if any(daet.task_type==t 
                    for t in tasks)
        ]
        if not exclude:
            return self.dupWithWhiteList(matched_daets)
        else:
            return self.dupWithBlackList(matched_daets)
        
    def renameDuplicateDaets(self) -> None:
        """
        For any rows whose DAET (date-animal-experiment-task) repeats,
        append “ (1)”, “ (2)”, … to all Task entries with the same Experiment and Task name,
        then update the DAET field and rebuild the internal index.
        """
        for (exp, task), group in self.df.groupby(['Experiment', 'Task']):
            if len(group) > 1:
                for i, idx in enumerate(group.index, start=1):
                    new_task = f"{str(task).strip()} ({i})"
                    self.df.at[idx, 'Task'] = new_task
                    self.df.at[idx, 'daet'] = DAET(self.date, self.animal, exp.strip(), new_task) #type: ignore

        self._daets.clear()
        self._buildDaetIdx()
    
    # === pipeline status checkers ===
    def checkSanity(self, ignore_void:bool=True) -> bool:
        if not self.daets:
            return False

        for daet in self.daets:
            if self.is_daet_void(daet) and ignore_void:
                continue
            vid_ext = self.checkVideoExistence(daet=daet)
            if not all([v for v in vid_ext.values()]):
                logger.info(f'{daet}: {vid_ext}')
                return False
        return True

    def checkSync(self, daets:DAET|list[DAET]|None=None) -> int:
        '''Check if daet is synced'''
        if not daets:
            daets = self.getValidDaets()
        if isinstance(daets, DAET):
            daets = [daets]
        ...
        return 0

    def getAllTaskTypes(self) -> list[Task]:
        '''get all tasks found in this note'''
        tasks = {
            daet.task_type
            for daet in self.daets
            if daet.task_type is not None
        }
        return list(tasks)

    def getSummary(self) -> dict:
        """get processing summary"""
        return {
            'total_entries': len(self.df),
            'valid_entries': len(self.df[~self.df['is_void']]),
            'void_entries': len(self.df[self.df['is_void']]),
            'calibration_entries': len(self.df[self.df['is_calib']]),
            'processable_entries': len(self.getValidDaets())
        }
    
    def is_daet_void(self, daet:DAET|None = None, no:int|None = None) -> bool:
        if daet is None:
            if no is None:
                raise ValueError('is_daet_void: double None')
            else:
                daet = self._daetOrNumber(daet=daet, no=no)
                if daet is None:
                    raise ValueError('is_daet_void: returned None daet')
        rec = self.getRow(daet)
        if not rec is None:
            return rec['is_void']
        else:
            raise KeyError(f'is_daet_void: unknown daet {daet}')

    def __repr__(self) -> str:
        return f'ExperimentNotes({self.animal} {self.date} with {len(self.df)} entries)'


r"""def iter_notes(year_path: Path) -> Iterator[ExpNote]:
    re_date = re.compile(r'20\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])')
    for folder_mo in sorted(year_path.iterdir()):
        if not folder_mo.is_dir():
            continue
        for folder_date in sorted(folder_mo.iterdir()):
            if not re.search(re_date, folder_date.name):
                logger.info(f'skipped {folder_date.name} cuz not date')
                continue
            for note_file in folder_date.glob('PICI_????????.xlsx'):
                try:
                    yield ExpNote(note_file.parent)
                except RuntimeError as e:
                    logger.error(f'Loading xlsx failed {folder_date.name}')
                break
            else:
                logger.warning(f'No note found under {folder_date.name}')"""

def iter_notes(year_path: str | Path) -> Iterator[ExpNote]:
    '''assumes /path/to/project/<animal-name>/<yyyy>'''
    year_path = Path(year_path)
    animal_name = year_path.parent.name
    # if not : return

    year_path = str(year_path)
    re_date = re.compile(r'20\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])')
    for mo_name in sorted(os.listdir(year_path)):
        folder_mo = os.path.join(year_path, mo_name)
        if not os.path.isdir(folder_mo):
            continue
        for date_name in sorted(os.listdir(folder_mo)):
            folder_date = os.path.join(folder_mo, date_name)
            if not re_date.search(date_name):
                logger.info(f'skipped {date_name} cuz not date')
                continue
            pattern = os.path.join(folder_date, f'{animal_name}_????????.xlsx')
            matches = glob.glob(pattern)
            if matches:
                note_file = matches[0]
                try:
                    yield ExpNote(Path(os.path.dirname(note_file)))
                except RuntimeError:
                    logger.error(f'Loading xlsx failed {date_name}')
            else:
                logger.warning(f'No note found under {date_name}')

def iter_xlsx(root_dir: str, nesting_level: int = 2) -> Iterator[str]:
    """
    Scans a directory for .xlsx files at a specific nesting level.
    suddenly using os/glob because its much faster than Path.glob()
    """
    path_components = ['*'] * nesting_level + ['*.xlsx']
    search_pattern = os.path.join(root_dir, *path_components)
    all_paths = glob.glob(search_pattern)
    all_paths = [
        p for p in all_paths
        if not os.path.basename(p).startswith("~$")
        and len(os.path.basename(p).split('.')[-2].split('_')[-1])==8
    ]   # temp files
    all_paths.sort()
    return iter(all_paths)

def get_xlsx_dates(root_dir: str, nesting_level: int = 2) -> list[str]:
    """
    Scans a directory and returns a list of date strings from the filenames.
    ['yyyymmdd',  ...]
    """
    date_list = []
    for file_path in iter_xlsx(root_dir, nesting_level=nesting_level):
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]
        date_part = name_without_ext.split('_')[-1]
        # shoulg look like a date, this is fragile though
        if date_part.isdigit() and len(date_part) == 8:
            date_list.append(date_part)
            
    return date_list

def mian() -> None:
    '''xiang chi mian le [usage example]'''
    # test with actual file
    raw_path = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\04\20250403')
    
    try:
        # initialize notes
        notes = ExpNote(raw_path)
        print(f"Loaded: {notes}")
        print(f"Animal: {notes.animal}, Date: {notes.date}")
        print()
        
        # show summary
        summary = notes.getSummary()
        print("=== SUMMARY ===")
        for key, value in summary.items():
            print(f"{key}: {value}")
        print()
        
        # list all entries
        print("=== ALL DAETS ===")
        daets = notes.getDaets()
        for i, daet in enumerate(daets, 1):
            rec = notes.getRow(daet)
            void_status = " [VOID]" if rec['is_void'] else "" # type: ignore
            calib_status = " [CALIB]" if rec['is_calib'] else "" # type: ignore
            print(f"{i:2d}. {daet}{void_status}{calib_status}")
        print()
        
        # check video availability
        print("=== VIDEO STATUS ===")
        valid_daets = notes.getValidDaets(min_videos=1)  # at least 1 video
        
        for daet in valid_daets[:5]:  # show first 5 valid ones
            videos = notes.getVidSetIdx(daet)
            existence = notes.checkVideoExistence(daet)
            
            print(f"{daet}:")
            print(f"  Video IDs: {videos}")
            
            # show which files exist
            for cam_idx, vid_id in enumerate(videos):
                if vid_id is not None:
                    exists = existence.get(cam_idx, False)
                    status = "✓" if exists else "✗"
                    print(f"    Cam{cam_idx+1}: C{vid_id:04d}.mp4 {status}")
            
            # count valid videos
            video_count = sum(1 for v in videos if v is not None)
            file_count = sum(existence.values())
            print(f"  Videos: {video_count} noted, {file_count} files found")
            print()
        
        # filter by task type
        print("=== TASK FILTERING ===")
        for task in [Task.TS, Task.BBT, Task.CALIB]:
            filtered = notes.filterByTask(task)
            if not filtered.empty:
                print(f"{task.name}: {len(filtered)} entries")
                for daet in filtered['daet'].head(3):  # show first 3
                    print(f"  - {daet}")
        
        # show processable entries
        print("\n=== READY FOR PROCESSING ===")
        processable = notes.getValidDaets(min_videos=2, skip_void=True)
        print(f"Found {len(processable)} entries with ≥2 videos:")
        for daet in processable[:3]:  # show first 3
            videos = notes.getVidSetIdx(daet)
            video_count = sum(1 for v in videos if v is not None)
            print(f"  {daet} ({video_count} videos)")
            
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        print("Check if the Excel file exists at the expected location")
        
    except Exception as e:
        print(f"Error loading notes: {e}")
        print("This might help debug the issue:")
        
        # debug info
        p = Path(raw_path)
        print(f"  Path exists: {p.exists()}")
        if p.exists():
            xlsx_files = list(p.glob('*.xlsx'))
            print(f"  Excel files found: {[f.name for f in xlsx_files]}")

if __name__ == '__main__':
    mian()