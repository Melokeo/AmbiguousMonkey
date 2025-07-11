'''
setup anipose + run with CLI anipose
'''
import subprocess
import json
import shutil
import re
import logging
from datetime import datetime
import bisect   # to lookup calibs
from dataclasses import dataclass
from pathlib import Path

from .expNote import ExpNote
from .daet import DAET

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

dlc_postfix_pattern = re.compile(r'DLC_resnet\d+_[^_]+shuffle\d+_\d+(?:_filtered)?\.h5$')

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
    pass

@dataclass
class CalibLib:
    lib_path: Path
    
    def __post_init__(self):
        '''index available calibs'''
        self.lib: dict[int, list[Path]] = {}
        self.updateLibIndex()

    def updateLibIndex(self):
        date_pattern = re.compile(r'\d{8}')
        if not self.lib_path.exists():
            raise FileNotFoundError(f'CalibLib: passed non-existing lib path {self.lib_path}')
        for calib in self.lib_path.glob('*.toml'):
            if not 'calibration' in calib.name:
                continue
            date = int(re.search(date_pattern, calib.name).group())
            if date in self.lib.keys():
                self.lib[date].append(calib)
            else:
                self.lib[date] = [calib]

    def lookUp(self, date: int) -> Path | None:
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
    conda_env: str = 'anipose-3d'
    config_file: Path = None
    calib_file: Path = None
    calib_lib: CalibLib = None

    def __post_init__(self):
        self.ani_root_path = Path(self.note.data_path) / 'anipose' / self.model_set_name
        if not self.calib_lib:
            self.calib_lib = self.getCalibLib(self.model_set_name)
        if not self.config_file:
            self.config_file = self.getCfgFile()
        if not self.calib_file:
            self.calib_file = self.getCalibFile()
    
    def __repr__(self):
        return f'AniposeProcessor({self.note.date}, model_set={self.model_set_name})'
    
    @property
    def info(self) -> str:
        return self.information(concat=True)

    def information(self, concat=True):
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
        if 'TS' in model_set_name or 'Pull' in model_set_name:
            return CalibLib(Path(r'C:\Users\mkrig\Documents\Python Scripts\calib history\arm4'))
        elif 'Brkm' in model_set_name or 'BBT' in model_set_name:
            return CalibLib(Path(r'C:\Users\mkrig\Documents\Python Scripts\calib history\hand2'))
        else:
            raise ValueError(f'Cannot get calib lib for unrecognized set: {model_set_name}')

    def getCfgFile(self) -> Path:
        '''get cfg based on model_set_name'''
        cfg_path = BASE_DIR / 'cfgs'
        if 'TS' in self.model_set_name or 'Pull' in self.model_set_name:
            return cfg_path / 'config_arm.toml'
        elif 'Brkm' in self.model_set_name or 'BBT' in self.model_set_name:
            return cfg_path / 'config_hand.toml'
        else:
            return cfg_path / 'config.toml'
    
    def getCalibFile(self) -> Path:
        '''determine calib file from note, with calib library as fallback'''
        calib = self.calib_lib.lookUp(int(self.note.date))
        if calib is None:
            raise ValueError(f'AniposeProcessor: cannot find this date\'s calib file {self.note.date}')
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
        for daet in self.note.getCalibs():
            self.setupSingleCalib(daet)

    def calibrateCLI(self) -> None:
        '''CLI anipose'''
        if not (self.ani_root_path / 'config.toml').exists():
            self.setupRoot()
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
    
    def calibrate(self) -> None:
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
        else:
            logger.info('Calibration successful')
            self.collectCalibs()
            return True

    def collectCalibs(self) -> None:
        for daet in self.note.getCalibs():
            daet_calib_toml = self.ani_root_path / str(daet) / 'calibration' / 'calibration.toml'
            if daet_calib_toml.exists():
                new_name = f'calibration-{str(daet)}.toml'
                try:
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
        if not self.calib_file.exists():
            raise ValueError(f'AniposeProcessor: assigned calib file doesn\'t exist: {self.config_file}')
        
        self.ani_root_path.mkdir(exist_ok=True)
        shutil.copy(self.config_file, self.ani_root_path / 'config.toml')

    def setupSingleDaet(self, daet:DAET, use_filtered:bool=True, copy_videos:bool=False) -> None:
        '''setup'''
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
    
    def triangulate(self) -> None:
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

    logger.info(f'Into switch: anipose {ani_flag}')
    if ani_flag:
        logger.info('calibrating')
        ap.calibrate()

        logger.info('setting up data')
        ap.batchSetup()

        logger.info('trangulate')
        ap.triangulate()

    else:
        logger.info('calibrating')
        ap.calibrateCLI()

        logger.info('setting up data')
        ap.batchSetup()

        logger.info('trangulate')
        ap.triangulateCLI()

    return ap