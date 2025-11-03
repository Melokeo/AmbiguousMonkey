'''
DLC module
'''

import logging
import re, json
from socket import gethostname
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from hashlib import md5
from collections.abc import Callable
from functools import partial

from .expNote import ExpNote, Task
from .camConfig import CamGroup
from .daet import DAET
from .dlcCollector import mergeDlcOutput, getDLCMergedFolderName
from ..utils.log import Wood
from .config import Config

logger = logging.getLogger(__name__)
ready: bool = False
deeplabcut = None

def initDlc() -> int:
    global ready, deeplabcut
    '''import dlc here. Returns 1 if imported successfully, else 0'''
    try:
        import deeplabcut as dlc
        deeplabcut = dlc
    except ImportError as e:
        logger.error(f'failed to import deeplabcut: {e}')
        return 0
    
    ready = True
    return 1

@dataclass(frozen=True, eq=True)  # will be used to hash, but doesn't count snapshot idx.
class DLCModel:
    '''name must be genuine model name'''
    name: str
    cfg_path: Path
    iteration: int = 0
    trainset: int = 95
    shuffle: int = 1
    short: str | None = None

    @property
    def md5(self) -> int:
        key = f"{self.name}_{self.cfg_path}_{self.trainset}_{self.shuffle}_{self.iteration}"
        return int(md5(key.encode()).hexdigest(), 16)
    @property
    def md5_short(self) -> str:
        return f'{self.md5 % 10_000:04d}'  # last 4-digit decimal
    
    @property
    def easy_name(self) -> str:
        return self.short if self.short else self.name
    @property
    def id_str(self) -> str:
        return f"{self.name}-trainset{self.trainset}shuffle{self.shuffle}"
    @property
    def id_output(self) -> str:
        '''how it appears in the output filenames of dlc'''
        return f"{self.name}shuffle{self.shuffle}"
    
    @property
    def start_date(self) -> str:
        m = re.search(r'(\d{8})', self.name)
        return m.group(1) if m else '00000000'
    
    #FIXME here date should be assigned/overridden beforehand to avoid cutting one set into two
    @property
    def final_folder_name(self) -> str:
        return f"{self.easy_name}-{datetime.now().strftime('%Y%m%d')} [{self.md5_short}]"
    
    @property
    def base_path(self) -> Path:
        return self.cfg_path.parent
    @property
    def iter_path(self) -> Path:
        return self.base_path / 'dlc-models' / f'iteration-{self.iteration}'
    @property
    def model_path(self) -> Path:
        return self.iter_path / self.id_str / "train"
    
    @property
    def is_available(self) -> bool:
        return self.cfg_path.exists() and self.iter_path.exists() and self.model_path.exists()

    def __repr__(self):
        return f"DLCModel pointer ({self.id_str})"
    
    @property
    def info(self) -> str:
        return '\n'.join(self.information())

    @classmethod
    def fromDict(cls, d: dict):
        return cls(
            name=d['name'],
            cfg_path=Path(d['cfg_path']),
            iteration=d.get('iteration', 0),
            trainset=d.get('trainset', 95),
            shuffle=d.get('shuffle', 1),
            short=d.get('short')
        )
    
    def toDict(self):
        return {
            'name': self.name,
            'cfg_path': str(self.cfg_path),
            'iteration': self.iteration,
            'trainset': self.trainset,
            'shuffle': self.shuffle,
            'short': self.short
        }
    
    def information(self) -> list[str]:
        '''model information'''
        info = []
        info.append(f"Model {self.easy_name}")
        info.append(self.__repr__())
        info.append(f"iteration folder: {str(self.iter_path)}\n\tExist {self.iter_path.exists()}")
        info.append(f"model folder: {str(self.model_path)}\n\tExist {self.model_path.exists()}")
        
        if self.model_path.exists():
            iters = [ # :)
                int(m.group(1)) 
                for f in self.model_path.glob('snapshot-*.index')
                if (m := re.search(r'snapshot-(\d+)\.index', f.name))
            ]       
            info.append(f'max training iteration: {max(iters)}')
        if self.iter_path.exists():
            sib = [sub.name.split('trainset')[-1] for sub in self.iter_path.glob(f'*trainset*')]
            info.append('Siblings: \n\t' + ', \n\t'.join(sib))

        return info

    def runOnce(self, vid_path: Path | str, override_exist:bool=True) -> bool:
        """run DLC analysis on single video directory"""
        if not ready or deeplabcut is None:
            logger.error('deeplabcut is called before successful import')
            return False
        if not self.is_available:
            logger.error('model not valid')
            return False

        vid_path = Path(vid_path)
        if not vid_path.exists():
            logger.error(f'DLCModel.runOnce: Folder not found {vid_path}')
            return False

        skip_file = vid_path / '.skipDLC'
        if skip_file.exists() and not override_exist:
            logger.info(f'Skipped processed folder as marked {vid_path.stem}')
            return True

        try:
            # analyze videos
            deeplabcut.analyze_videos(
                str(self.cfg_path),
                [str(vid_path)], 
                videotype='mp4',           
                trainingsetindex=0,
                shuffle=self.shuffle,
                cropping=None,
                auto_track=False,
                engine=deeplabcut.Engine.TF,
            )
            
            # filter predictions
            deeplabcut.filterpredictions(
                str(self.cfg_path), 
                str(vid_path), 
                shuffle=self.shuffle,
                save_as_csv=True,
                videotype='mp4',
                filtertype="median",
            )
            
            # mark as processed
            skip_file.touch()
            logger.info(f'DLC analysis completed for {vid_path.stem}')

            self.pee(vid_path)

            return True
            
        except Exception as e:
            logger.error(f'DLC analysis failed for {vid_path}: {e}')
            raise e
            return False
    
    def _getPeedTree(self, vid_path:Path) -> Path:
        vid_root = vid_path.parent if vid_path.is_file() else vid_path
        return vid_root.parent / "DLC" / "separate" / self.final_folder_name
    
    def pee(self, vid_path:Path) -> None:
        # collect files for isolation
        vid_root = vid_path.parent if vid_path.is_file() else vid_path
        tree = self._getPeedTree(vid_path)        #note where it peed, the .parent
        file_list = []

        tree.mkdir(parents=True, exist_ok=True)
        for sub in vid_root.glob(f'*{self.id_output}*'):
            if sub.is_file():
                sub.rename(tree / sub.name)
                file_list.append(sub.name+'\n')
        
        # write this analysis' info
        info =  '=== DLC analysis record ===\n'   \
                f'Log created {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n' \
                f'video root: {str(vid_root)}\n\n'\
                f'Processed on: {gethostname()}'\
                '-- Model info --\n'\
                + "\n".join(self.information()) + \
                '\n\n-- File list on creation --\n'
                
        with open(tree / 'scent.log', 'a') as f:
            f.writelines(info)
            if file_list:
                f.writelines(file_list)
            else:
                f.write('*blank*')

        # write json for further identification
        jfile = tree / 'inherit.json'
        j = {
            'finish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'terminal': gethostname(),
            'model': self.toDict(),
            'model_hash': self.md5,
        }
        with open(jfile, 'w') as f:
            json.dump(j, f, indent=4)

class DLCProcessor:
    def __init__(self, note: ExpNote, model_dict: dict[CamGroup, DLCModel]):
        self.note = note
        self.model_dict = model_dict
        self.data_path = note.data_path
        self.video_extension = note.video_extension
        self.wood = Wood(self.data_path / 'SynchronizedVideos')

    @property
    def final_dlc_folder_name(self) -> str:
        model_finals = [Path(m.final_folder_name) for m in self.model_dict.values()]
        return getDLCMergedFolderName(*model_finals[0:2])

    def _getSyncRoot(self, daet: DAET) -> Path | None:
        """get synchronized video path for DAET"""
        sync_path = self.note.getDaetSyncRoot(daet)
        return sync_path if sync_path.exists() else None

    def analyzeSingleDaet(self, daet: DAET) -> bool:
        """process single DAET with DLC analysis"""
        if not all(m.is_available for m in self.model_dict.values()) and not ready:
            logger.error(f'DLC processor: models not ready')
            return False
        
        if not self.note.hasDaet(daet):
            logger.error(f'DLC processor: Passed unknown daet item {daet}')
            return False
        
        # skip calibration videos
        if daet.isCalib:
            logger.info(f'Skipping calibration DAET: {daet}')
            return True
        
        sync_root_path = self._getSyncRoot(daet)
        if not sync_root_path:
            logger.error(f'Video path not found for {daet}')
            return False
        
        logger.info(f'DLC analyzing {daet}...')
        success = True
 
        # process each camera group       
        trees: list[Path] = []
        for group, model in self.model_dict.items():
            group_path = sync_root_path / group.value  # e.g. L or R
            if group_path.exists():
                if not model.runOnce(group_path):
                    success = False
            else:
                logger.warning(f'Group path not found: {group_path}')
            
            trees.append(model._getPeedTree(group_path))

        # merge outputs
        if success:
            mergeDlcOutput(*trees)
        
        return success

    def batchProcess(self, daets_to_process: list[DAET] | None = None, min_videos: int = 2) -> dict[DAET, bool]:
        """process multiple DAETs with DLC analysis"""
        if not ready:
            logger.error('DLC not properly initialized')
            return {}
        if daets_to_process is None:
            daets = self.note.getValidDaets(min_videos=min_videos, skip_void=True)
        else:
            daets = daets_to_process
        
        # write the history (yeah)
        self.wood.logger.info('Starting DLC with models:')
        for cg, m in self.model_dict.items():
            self.wood.logger.info(f'CamGroup: {cg} | Model: {m.easy_name}')
            self.wood.logger.info('\n'.join(m.information()))

        results = {}
        for daet in daets:
            try:
                with self.wood.log(f'DLC running {daet}'):
                    results[daet] = self.analyzeSingleDaet(daet)
            except OSError as e:
                logger.error(f'DLC batch processing failed: {daet} | {e}')
                self.wood.logger.error(f'DLC batch processing failed: {daet} | {e}')
        
        successful = sum(results.values())
        total = len(results)
        logger.info(f'DLC batch processing complete: {successful}/{total} successful')

        return results
    
    def collectResults(self, daet:DAET) -> None:
        '''so that multiple models can live together'''
        pass # implemented in DLCModel.pee()
    
# util funcs
def create_processor(wiring: dict[CamGroup, DLCModel]) -> Callable[[ExpNote], DLCProcessor]:
    return partial(DLCProcessor, model_dict=wiring)

def deserialize_wiring(wiring: dict[str,str]) -> dict[CamGroup, DLCModel]:
    return {CamGroup(k): modelPreset(v) 
            for k, v in wiring.items()}

def modelPreset(preset_name:str) -> DLCModel:
    mdl_param = Config.dlc_models.get(preset_name, None)
    if mdl_param:
        return DLCModel(
            name=mdl_param.get('dir-name', ''),
            cfg_path=Path(mdl_param.get('cfg-path', '')),
            iteration=mdl_param.get('iteration', 0),
            shuffle=mdl_param.get('shuffle', 1),
        )
    raise ValueError(f'Unknown preset {preset_name}')

#TODO below should be wrapped in another dataclass.

available_models = [k for k in Config.dlc_models.keys()]
available_dp = [k for k in Config.dlc_combos.keys()]

dp_task = {
    'TS-LR':     Task.TS,
    'Pull-LR':   Task.PULL,
    'Brkm':      Task.BRKM,
    'BBT':       Task.BBT,
    'Pull-Hand': Task.PULL,
    'fus-arm':   Task.PULL,
    'fus-arm-it3':   Task.PULL,
    'fus-arm-it7':   Task.PULL,
}

dp_factory = {
    k: create_processor(deserialize_wiring(w))
    for k, w in Config.dlc_combos.items()
}

@dataclass
class ModelFactory:
    models: list[DLCModel]
    factory: list[Callable]

    def __post_init__(self):
        self._avail_models: list[str] = [
            m.name for m in self.models
        ]

model_factory = ModelFactory(
    models=[modelPreset(am) for am in available_models],
    factory=[v for v in dp_factory.values()]
)