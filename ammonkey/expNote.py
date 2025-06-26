'''class ExpNote: reads, processes and stores experiment notes'''

import logging
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd
from enum import Enum, auto

from .fileOp import getDataPath
from .daet import DAET, Task
from ..utils.statusChecker import chk_dict

logger = logging.getLogger(__name__)

@dataclass
class ExpNote:
    """
    Load and manage experiment notes from Excel with DAET-based interface.
    """
    path: Path | str
    header_key: str = 'Experiment'
    cam_headers: list[str] = field(default_factory=lambda: [
        'Camera files \n(1 LR)', 'Camera files \n(2 LL)', 
        'Camera files (3 RR)', 'Camera files (4 RL)'
    ])
    skip_markers: list[str] = field(default_factory=lambda: ['x', '-', 'NaN'])
    video_extension: str = 'mp4'
    
    # computed fields
    df: pd.DataFrame = field(init=False)
    animal: str = field(init=False)
    date: str = field(init=False)
    data_path: Path = field(init=False)
    _task_patterns: dict[Task, list[str]] = field(init=False, default_factory=lambda: {
        Task.BBT: ['bbt'], Task.BRKM: ['brkm', 'brnk', 'kman'],
        Task.PULL: ['pull', 'puul'], Task.TS: ['touchscreen', 'touch screen', 'ts'],
        Task.CALIB: ['calib'], Task.ALL: ['']
    })  # shouldnt use this

    def __post_init__(self):
        self.path = Path(self.path)
        self.animal, self.date = self._parsePathInfo()
        
        xlsx_path = self.path / f'{self.animal}_{self.date}.xlsx'
        if not xlsx_path.exists():
            raise FileNotFoundError(f'Notes file not found: {xlsx_path}')
        
        self.df = self._loadDataFrame(xlsx_path)   

        self.data_path = getDataPath(self.path) 
        if not self.data_path.exists():
            logger.warning(f'data_path does not exist {self.data_path}')

        self._daets: dict[str, DAET] = {}
        self._buildDaetIdx()
    
    def _buildDaetIdx(self):
        '''build index from df'''
        for _, r in self.df.iterrows():
            try:
                daet = DAET.fromRow(r, self.date, self.animal)
                if not str(daet) in self._daets.keys():
                    self._daets[str(daet)] = daet
                else:
                    logger.error(f'!! Duplicative daet: {str(daet)}')
            except ValueError as e:
                logger.error(f'Invalid DAET during build: {e}')

    def _parsePathInfo(self) -> tuple[str, str]:
        """extract animal and date from path structure"""
        parts = self.path.parts
        # flexible: try common patterns
        if len(parts) >= 4 and parts[-4].lower() in ['pici']: 
            return parts[-4], parts[-1]
        else:  # fallback - look for known animals
            animals = ['pici']
            animal = next((p for p in parts if p.lower() in animals), parts[-2])
            return animal, parts[-1]
    
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
            df['daet'] = df.apply(lambda r: DAET.fromRow(r, self.date, self.animal), axis=1)
            void_col = df.get('VOID', pd.Series('', index=df.index))
            df['is_void'] = void_col.astype(str).str.upper().isin(['T', 'TRUE', '1'])
            df['is_calib'] = df['Experiment'].astype(str).str.contains('calib', case=False, na=False)
            
            return df
        except Exception as e:
            raise RuntimeError(f'Failed loading {xlsx_path}: {e}')
        
    def _daetOrNumber(self, daet: DAET|None, no: int|None) -> DAET:
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
        return self.data_path / 'SynchronizedVideos' / str(daet)
    
    def getDaetDlcRoot(self, daet: DAET) -> Path:
        return self.data_path / 'SynchronizedVideos' / str(daet) / 'DLC'

    def getVidSetIdx(self, daet: DAET=None, no: int=None) -> list[int | None]:
        """get video IDs for DAET - crash-proof"""
        daet = self._daetOrNumber(daet, no)
        if not daet:
            return

        rec = self.getRow(daet)
        if rec is None:
            return []
        
        vids = []
        for hdr in self.cam_headers:
            val = rec.get(hdr)  # None if column missing
            
            # robust None/NaN/string checking
            if val is None or pd.isna(val) or str(val) in self.skip_markers:
                vids.append(None)
            else:
                try:
                    vids.append(int(val))
                except (ValueError, TypeError):
                    logging.warning(f'Invalid video ID "{val}" in {hdr} for {daet}')
                    vids.append(None)
        return vids

    def checkVideoExistence(self, daet: DAET=None, no: int=None) -> dict[int, bool]:
        """check if video files exist on disk for given DAET
        
        Returns:
            dict mapping **camera index** (0-based) to existence status
        """
        # handle no# inputs
        daet = self._daetOrNumber(daet, no)
        if not daet:
            return

        vid_set = self.getVidSetIdx(daet)
        if not vid_set:
            return {}
        
        existence = {}
        for cam_idx, vid_id in enumerate(vid_set):
            if vid_id is None:
                # don't include missing video entries in result
                continue
                
            vid_path = self.getVidPath(daet, cam_idx)
            existence[cam_idx] = not vid_path is None
            
        return existence

    def getVidPath(self, daet: DAET, cam_idx: int) -> Path | None:
        """get actual video file path for single DAET and camera index"""
        vid_set = self.getVidSetIdx(daet)
        if not vid_set or cam_idx >= len(vid_set):
            return None
            
        vid_id = vid_set[cam_idx]
        if vid_id is None:
            return None
            
        cam_folder = self.path / f'cam{cam_idx + 1}'
        if not cam_folder.exists():
            return None
        
        # try both 4-digit and 5-digit formats
        for digits in [4, 5]:
            vid_filename = f'C{vid_id:0{digits}d}.{self.video_extension}'
            vid_path = cam_folder / vid_filename
            if vid_path.exists():
                return vid_path
                
        return None
    
    def getVidSetPaths(self, daet: DAET) -> list[Path] | None:      #TODO has duplicate logic w/ above
        '''get video paths from note, or None for non-existing file'''
        vid_set = self.getVidSetIdx(daet)
        if not vid_set:
            return None
        
        vid_paths = []
        for i, vid_id in enumerate(vid_set):
            cam_folder = self.path / f'cam{i + 1}'
            if not cam_folder.exists():
                vid_paths.append(None)
            for digits in [4, 5]:
                vid_filename = f'C{vid_id:0{digits}d}.{self.video_extension}'
                vid_path = cam_folder / vid_filename
                if vid_path.exists():
                    vid_paths.append(vid_path)
                    break
            else: # file not found, append placeholding none
                vid_paths.append(None)

        return vid_paths

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
            cam_headers=self.cam_headers.copy(),
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
            cam_headers=self.cam_headers.copy(),
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
        matched_daets: list[DAET] = [
            daet for daet in self.daets 
            if any(daet.task_type==t 
                    for t in tasks)
        ]
        if not exclude:
            return self.dupWithWhiteList(matched_daets)
        else:
            return self.dupWithBlackList(matched_daets)
    
    # === pipeline status checkers ===
    def checkSync(self, daets:DAET|list[DAET]=None) -> int:
        '''Check if daet is synced'''
        if not daets:
            daets:list[DAET] = self.getValidDaets()
        if isinstance(daets, DAET):
            daets:list[DAET] = [daets]
        ...

    def getAllTaskTypes(self) -> list[Task]:
        '''get all tasks found in this note'''
        tasks = {
            daet.task_type
            for daet in self.daets
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

    def __repr__(self) -> str:
        return f'ExperimentNotes({self.animal} {self.date} with {len(self.df)} entries)'
    
def mian() -> None:
    '''xiang chi mian le [usage example]'''
    # test with actual file
    raw_path = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\04\20250403'
    
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
            void_status = " [VOID]" if rec['is_void'] else ""
            calib_status = " [CALIB]" if rec['is_calib'] else ""
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
        from pathlib import Path
        p = Path(raw_path)
        print(f"  Path exists: {p.exists()}")
        if p.exists():
            xlsx_files = list(p.glob('*.xlsx'))
            print(f"  Excel files found: {[f.name for f in xlsx_files]}")

if __name__ == '__main__':
    mian()