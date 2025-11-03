'''
setup anipose + run with CLI anipose
'''
import subprocess
import json
import shutil
import re
import os
import logging
from datetime import datetime
import bisect   # to lookup calibs
from dataclasses import dataclass
from pathlib import Path

from .expNote import ExpNote
from .daet import DAET
from .config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

dlc_postfix_pattern = re.compile(r'DLC_resnet\d+_[^_]+shuffle\d+_\d+(?:_filtered)?\.h5$')
LIB_HAND = Path.home() / 'Documents/Python Scripts/calib history/arm4'
LIB_ARM  = Path.home() / 'Documents/Python Scripts/calib history/hand2'

def getH5Rename(file_name:Path | str, stem_only:bool=False) -> str:
    '''get rid of dlc postfix'''
    if isinstance(file_name, Path):
        file_name = file_name.name
    new_postfix = '' if stem_only else '.h5'
    return re.sub(
        dlc_postfix_pattern, 
        new_postfix, 
        file_name
    )

def insertModelToH5Name(file_name:Path | str) -> str: 
    return ''

@dataclass
class CalibLib:
    lib_path: Path
    
    def __post_init__(self):
        '''index available calibs'''
        self.lib: dict[int, list[Path]] = {}
        self.updateLibIndex()
        
    def updateLibIndex(self):
        """index available calib files"""
        date_pattern = re.compile(r'\d{8}')
        if not self.lib_path.exists():
            raise FileNotFoundError(f'CalibLib: passed non-existing lib path {self.lib_path}')
        for calib in self.lib_path.glob('*.toml'):
            if not 'calibration' in calib.name:
                continue
            date_re = re.search(date_pattern, calib.name)
            if date_re:
                date = int(date_re.group())
            else:
                logger.debug(f'{calib.parent/calib.name} - calibration file without date')
                continue
            if date in self.lib.keys():
                self.lib[date].append(calib)
            else:
                self.lib[date] = [calib]
        if not self.lib.keys():   # no calib found
            pass
            #TODO implement first-run 

    def lookUp(self, date: int) -> Path | None:
        """look up calib file for given date, with fallback to closest prior date"""
        calibs = self.lib.get(date)
        if calibs: 
            return calibs[0]
        else:
            closest = self.getClosestBackward(date)
            if closest:
                logger.warning(f'calibLib: used fallback calib for {date} <- {closest}')
                return self.lib[closest][0]
            else:
                return None
        
    def getClosestBackward(self, target: int) -> int | None:
        """get closest date in the lib keys for given target"""
        keys = sorted(self.lib.keys())
        idx = bisect.bisect_right(keys, target) - 1
        return keys[idx] if idx >= 0 else None
        
    def __repr__(self):
        return f'CalibLib ({len(self.lib)} entries)'
    
BASE_DIR = Path(__file__).parent.parent # should be ammonkey/

@dataclass  
class AniposeProcessor:     #TODO will need to test behavior on duplicative runs
    note: ExpNote
    model_set_name: str
    conda_env: str = Config.anipose_env
    config_file: Path = None    #type:ignore
    calib_file: Path | None = None     
    calib_lib: CalibLib = None  #type:ignore

    def __post_init__(self):
        self.ani_root_path = Path(self.note.data_path) / 'anipose' / self.model_set_name
        if not self.calib_lib:
            self.calib_lib = self.getCalibLib(self.model_set_name)
        if not self.config_file:
            self.config_file = self.getCfgFile()
            logger.debug(f'{self.config_file=}')
        if not self.calib_file:
            self.calib_file = self.getCalibFile()
            if not self.calib_file:
                logger.warning('Note has no matching calib file, need calib first')

    
    def __repr__(self):
        return f'AniposeProcessor({self.note.date}, model_set={self.model_set_name})'
    
    @property
    def info(self) -> str:
        return self.information(concat=True) #type:ignore

    def information(self, concat=True) -> str | list[str]:
        info = []
        info.append('AniposeProcessor')
        info.append(f'{self.note.animal} @ {self.note.date}')
        info.append(f'Config: {str(self.config_file)}')
        info.append(f'Calib: {str(self.calib_file)}')
        info.append(f'Used env: {self.conda_env}')
        info.append('Included daets:')
        info.extend([f'\t{d}' for d in self.note.daets])
        if concat: 
            return '\n'.join(info)
        else:
            return info
    
    def getCalibLib(self, model_set_name:str) -> CalibLib:
        '''here maps model set to the calibration lib'''
        if 'Brkm' in model_set_name or 'BBT' or 'Hand' in model_set_name:
            return CalibLib(LIB_HAND)
        elif 'TS' in model_set_name or 'Pull' in model_set_name:
            return CalibLib(LIB_ARM)
        else:
            raise ValueError(f'Cannot get calib lib for unrecognized set: {model_set_name}')

    def getCfgFile(self) -> Path:
        '''get cfg based on model_set_name'''
        cfg_path = BASE_DIR / 'cfgs'
        cfg_matching = Config.anipose_cfgs
        for k, v in cfg_matching.items():
            if k in self.model_set_name:
                cfg_file = cfg_path / v
                if not cfg_file.exists():
                    raise FileNotFoundError(f'{self.model_set_name} should use {v}, but {cfg_file} doesnt exist')
                return cfg_path / v
        
        logger.warning(f'No match found for {self.model_set_name}, using default config!')
        return cfg_path / 'config.toml'
    
    def getCalibFile(self) -> Path | None:
        '''determine calib file from note, with calib library as fallback'''
        calib = self.calib_lib.lookUp(int(self.note.date))
        if calib is None: # check if this note carries calib itself
            if not self.note.has_calib:
                raise ValueError(f'AniposeProcessor: cannot find this date\'s calib file {self.note.date}')
            return None
        else:
            return calib
        
    def runPipeline(self) -> bool:
        try:
            self.setupRoot()
            self.setupCalibs()
            self.calibrate()
            self.batchSetup()
            self.triangulate()
        except Exception as e:
            logger.error(f'AP.runPipeline error: {e}')
            return False
        else:
            return True
        
    def setupSingleCalib(self, daet:DAET)->None:
        if not daet.isCalib:
            return
        daet_calib_root = self.ani_root_path / str(daet) / 'calibration'
        daet_sync_root = self.note.getDaetSyncRoot(daet)
            # eg. anipose/TS-LR-20250618 [1476-4237]/20250610-Pici-Calib-c
        daet_calib_root.mkdir(exist_ok=True, parents=True)
        for vid in daet_sync_root.glob('*.mp4'):
            logger.info(f'Copying {vid.name}')
            try:
                shutil.copy(vid, daet_calib_root)
            except OSError as e:
                logger.error(f'ssc copy failed {e}')
    
    def setupCalibs(self) -> None:
        if self.isCalibDone():
            logger.debug(f'skipped setup calib: {self.note.getCalibs()} already done')
            return
        for daet in self.note.getCalibs():
            self.setupSingleCalib(daet)
    
    def isCalibDone(self) -> bool:
        """check if **all** calibs are done"""
        calibs: list[DAET] = self.note.getCalibs()
        curr_lib = self.calib_lib.lib.get(int(self.note.date), None)
        if not curr_lib: 
            return False
        return all(
                any(
                    str(daet) in calib_file.stem
                    for calib_file in curr_lib
                )
                for daet in calibs
            )

    def calibrateCLI(self, override_existing:bool = False) -> None:
        '''CLI anipose'''
        if not (self.ani_root_path / 'config.toml').exists():
            self.setupRoot()

        if self.isCalibDone():
            logger.debug(f'skipped calib: {self.note.getCalibs()} already done')
            return

        cmd = [
            'conda', 'activate', self.conda_env, '&&',
            'P:', '&&',
            'cd', str(self.ani_root_path), '&&',
            'anipose', 'calibrate'
        ]
        result = subprocess.run(cmd, shell=True, check=True)
        if result.stderr:
            logger.error(result.stderr)

        self.collectCalibs()
    
    def calibrate(self) -> bool:
        '''directly calls anipose. will auto-collect'''
        if not (self.ani_root_path / 'config.toml').exists():
            self.setupRoot()

        try:
            from anipose import anipose, calibrate
        except ImportError as e:
            logger.error('Cannot find anipose installed, or dependency not intact')
            return False
        
        cfg = anipose.load_config(str(self.ani_root_path / 'config.toml'))
        logger.debug(cfg)
        try:
            calibrate.calibrate_all(config=cfg)
        except Exception as e:  # idk what can be wrong
            logger.error(f'Failed to calibrate: {e}')
            return False
        else:
            logger.info('Calibration successful')
            self.collectCalibs()
            return True

    def collectCalibs(self) -> None:
        """store anipose calculated calib files in calib lib"""
        for daet in self.note.getCalibs():
            daet_calib_toml = self.ani_root_path / str(daet) / 'calibration' / 'calibration.toml'
            if daet_calib_toml.exists():
                new_name = f'calibration-{str(daet)}.toml'
                try:
                    logger.debug(f'{daet_calib_toml} -> {self.calib_lib.lib_path}')
                    shutil.copy(daet_calib_toml, self.calib_lib.lib_path / new_name)
                except OSError as e:
                    logger.error(f'collectCalib copy failed {e}')
            else:
                logger.warning(f'collectCalib(): FNF {daet_calib_toml}')

        self.calib_lib.updateLibIndex()
        self.calib_file = self.getCalibFile()
        
    def setupRoot(self) -> None:
        '''setup only the root folder'''
        if not self.config_file.exists():
            raise ValueError(f'AniposeProcessor: assigned config file doesn\'t exist: {self.config_file}')
        if not self.calib_file:
            logger.warning('No calib file. you may NOT continue triangulation before calibrate.')
        elif not self.calib_file.exists():
            raise ValueError(f'AniposeProcessor: assigned calib file doesn\'t exist: {self.config_file}')
        
        self.ani_root_path.mkdir(exist_ok=True)
        logger.info(f'using {self.config_file=}')
        shutil.copy(self.config_file, self.ani_root_path / 'config.toml')

    def setupSingleDaet(self, daet:DAET, use_filtered:bool=True, copy_videos:bool=False) -> None:
        '''setup anipose folder for single daet: copy h5, calib, and videos if needed'''
        # prepare ingredients
        if not self.note.hasDaet(daet):
            raise ValueError(f'setupSingleDaet: trying to process non-existing daet {daet}')
        if daet.isCalib:
            return
        
        daet_dlc_root = self.note.getDaetDlcRoot(daet) / self.model_set_name
            # eg. SynchronizedVideos/20250610-Pici-BBT-1/DLC/TS-LR-20250618 [1476-4237]
        if not daet_dlc_root.exists():
            logger.warning(f'setupSingleDaet: skipped {daet} due to no DLC results')
            return
        
        daet_ani_root = self.ani_root_path / str(daet)
            # eg. anipose/TS-LR-20250618 [1476-4237]/20250610-Pici-BBT-1
        daet_pose_2d_filtered = daet_ani_root / 'pose-2d-filtered'
        subfolders = [
            'calibration',
            'videos-raw',
            'pose-2d-filtered',
        ]

        # start cooking
        daet_ani_root.mkdir(exist_ok=True)
        for sf in subfolders:
            (daet_ani_root / sf).mkdir(exist_ok=True)

        # copy h5
        for h5 in daet_dlc_root.glob('*.h5'):
            if 'filtered' in h5.name:
                if not use_filtered:
                    continue
            else:
                if use_filtered:
                    continue
            
            new_name = getH5Rename(h5.name, stem_only=False)
            dst = daet_pose_2d_filtered / new_name
            if not dst.exists():
                logger.info(f'Copying h5: {h5.name}')
                try:
                    shutil.copy(h5, dst)
                except OSError as e:
                    logger.error(f'setupSingleDaet: failed copying {h5} -> {daet_pose_2d_filtered}, err: {e}')
            else:
                logger.info(f'setupSingleDaet: skipped {h5.name} due to existance')
        
        # copy calibration.toml
        try:
            if self.calib_file:
                shutil.copy(self.calib_file, daet_ani_root / 'calibration' / 'calibration.toml')
        except OSError as e:
            logger.error(f'setupSingleDaet: failed copying {self.calib_file} -> {daet}, err: {e}')

        # copy json
        inherit = daet_dlc_root / 'inherit.json'
        if not inherit.exists():
            logger.warning(f'{inherit} FNF')
        else:
            shutil.copy(inherit, daet_ani_root)
            
    def batchSetup(self, use_filtered:bool=True, copy_videos:bool=False) -> None:
        self.setupRoot()
        for daet in self.note.daets:
            self.setupSingleDaet(daet, use_filtered, copy_videos)
    
    def triangulateCLI(self) -> None:
        '''CLI anipose'''
        cmd = [
            'conda', 'activate', self.conda_env, '&&',
            'P:', '&&',
            'cd', str(self.ani_root_path), '&&',
            'anipose', 'triangulate'
        ]
        result = subprocess.run(cmd, shell=True, check=True)
        if result.stderr:
            logger.error(result.stderr)
    
    def triangulate(self) -> bool:
        '''directly calls anipose'''
        try:
            from anipose import anipose, triangulate
        except ImportError as e:
            logger.error('Cannot find anipose installed, or dependency not intact')
            return False
        
        logger.info('Triangulating all tasks')
        try:
            cfg = anipose.load_config(str(self.ani_root_path / 'config.toml'))
            logger.debug(cfg)
            triangulate.triangulate_all(cfg)
        except Exception as e:
            logger.error(f'Failed triangulation: {e}')
            return False
        else:
            return True
        
    def makeVideos(self, start:float|None=None, end:float|None=None) -> None:
        '''label-3d + label-combined\n
        - raise: RuntimeError on subprocess failure
        ''' 

        #TODO make this work on non-Windows system

        drive = os.path.splitdrive(str(self.ani_root_path))[0]
        cmd_header = [
            'conda', 'activate', self.conda_env, '&&',
            drive, '&&',
            'cd', str(self.ani_root_path), '&&',
        ]

        cmd = cmd_header + [
            'anipose', 'label-3d',
        ]
        if start is not None and 0 < start < 1: # start == 0 case same as no start
            cmd.extend(['--start', str(start)])
        if end is not None and 0 < end < 1: 
            cmd.extend(['--end', str(end)])
        result = subprocess.run(cmd, shell=True, check=True)
        if result.stderr:
            logger.error(result.stderr)
            raise RuntimeError(f'label-3d failed: {result.stderr}')
        
        cmd = cmd_header + [
            'anipose', 'label-combined',
        ]
        if start is not None:
            cmd.extend(['--start', str(start)])
        if end is not None:
            cmd.extend(['--end', str(end)])
        result = subprocess.run(cmd, shell=True, check=True)
        if result.stderr:
            logger.error(result.stderr)
            raise RuntimeError(f'label-combined failed: {result.stderr}')

    def copy_vid_to_daet(self, daet:DAET) -> None:
        '''copy raw videos to anipose folder for this daet'''
        daet_sync_root = self.note.getDaetSyncRoot(daet)
        daet_ani_videos_raw = self.ani_root_path / str(daet) / 'videos-raw'
        daet_ani_videos_raw.mkdir(exist_ok=True, parents=True)
        for vid in daet_sync_root.rglob('*.mp4'):
            logger.info(f'Copying {vid.name}')
            if not (daet_ani_videos_raw / vid.name).exists():
                try:
                    shutil.copy(vid, daet_ani_videos_raw)
                except OSError as e:
                    logger.error(f'ssc copy failed {e}')
    
    def copy_videos_all_daets(self, skip_non_exist:bool=True) -> None:
        included_daet_dirs = list(self.ani_root_path.glob('*'))
        for daet in self.note.daets:
            if skip_non_exist:
                if str(daet).lower() not in [d.name.lower() for d in included_daet_dirs]:
                    logger.debug(f'skipped copy for non-existing ani daet {daet}')
                    continue
            self.copy_vid_to_daet(daet)

    def pee(self, daet_root: Path) -> None:
        # write this analysis' info
        info =  '=== Anipose triangulation record ===\n'   \
            f'Log created {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n' \
            f'Anipose root: {str(daet_root)}\n\n'\
            '-- Config info --\n' + \
            self.info
        with open(daet_root / 'scent.log', 'a') as f:
            f.writelines(info)
    
# util func
def runAnipose(note:ExpNote, model_set_name:str):
    logger.setLevel(logging.INFO)

    ap = AniposeProcessor(note, model_set_name)
    ap.setupRoot()
    ap.setupCalibs()

    # dont want to crash because of no anipose
    try:
        import anipose
        ani_flag = True
    except ImportError:
        ani_flag = False

    ani_flag = False # for now

    logger.info(f'Into switch: anipose {ani_flag}')
    if ani_flag:
        logger.info('calibrating')
        ap.calibrate()
        ap.setupRoot()

        logger.info('setting up data')
        ap.batchSetup()

        logger.info('trangulate')
        ap.triangulate()

    else:
        logger.info('calibrating')
        ap.calibrateCLI()
        ap.setupRoot()

        logger.info('setting up data')
        ap.batchSetup()

        logger.info('trangulate')
        ap.triangulateCLI()

    return ap