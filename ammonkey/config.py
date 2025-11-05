'''
Setup specific configurations
cfg by default is in ammonkey/cfgs/amm-config.yaml
'''

import yaml
from dataclasses import dataclass, field
from pathlib import Path

import logging
lg = logging.getLogger(__name__)

cfg_path = Path(__file__).parent.parent / 'cfgs/amm-config.yaml'

if not cfg_path.exists():
    raise FileNotFoundError(f'Basic config not found: {cfg_path}')

Config = None

@dataclass
class _Config:
    projects_path: Path
    animals: list[str]
    animal_paths: dict[str, str]
    cam_settings: dict[int, dict] 
    ffmpeg_path: str
    ffprobe_path: str
    # tasks: dict[str, int]
    # task_kw: dict[str, list[str]]
    dlc_models: dict[str, dict]
    dlc_combos: dict[str, dict]
    anipose_env: str
    anipose_cfgs: dict[str, str]

    def validate(self) -> tuple[bool, str]:
        missing = []
        if not self.projects_path or not self.projects_path.exists():
            missing.append("projects_path (missing or invalid path)")
        if not self.animals:
            missing.append("animals (empty)")
        if not self.animal_paths:
            missing.append("animal_paths (empty)")
        if not self.cam_settings:
            missing.append("cam_settings (default {})")
        if not self.ffmpeg_path:
            missing.append("ffmpeg_path (empty)")
        if not self.ffprobe_path:
            missing.append("ffmpeg_path (empty)")
        if not self.dlc_models:
            missing.append("dlc_models (default {})")
        if not self.dlc_combos:
            missing.append("dlc_combos (default {})")
        if not self.anipose_env:
            missing.append("anipose_env (empty)")
        if not self.anipose_cfgs:
            missing.append("anipose_cfgs (default {})")

        if missing:
            msg = "Missing or default fields:\n" + "\n".join(f" - {m}" for m in missing)
            return False, msg
        return True, "All config fields validated successfully."

def validate_task_match(tasks: list, task_kw: dict[str, list[str]]) -> bool:
    keys = list(task_kw.keys())
    return all(t in keys for t in tasks)

with open(cfg_path, 'r') as cfg:
    cfg_data = yaml.safe_load(cfg)
    if not isinstance(cfg_data, dict):
        raise ValueError(f'Incorrect cfg type: {type(cfg_data)}')
    try:
        animals = cfg_data.get('animals', None)
        if not animals:
            raise ValueError('No animal is defined in config. plz check amm-config.yaml file.')
        elif not isinstance(animals, dict):
            raise ValueError('Config animal field incorrect: should be dict. plz check amm-config.yaml file.')
        
        # tasks = cfg_data.get('tasks', None)
        # if not tasks:
        #     raise ValueError('No task is defined in config. plz check amm-config.yaml file.')
        # 
        # task_kw = cfg_data.get('task-keywords', {})
        # if not validate_task_match(tasks, task_kw):
        #     raise ValueError('Task matching criteria doesn\'t match task items in config. plz check amm-config.yaml file.')
        
        try:
            Config = _Config(
                projects_path=Path(cfg_data.get('projects-path', '')),
                animals=[k.lower() for k in animals.keys()],
                animal_paths=animals,
                cam_settings=cfg_data.get('cams', {}),
                ffmpeg_path=cfg_data.get('ffmpeg', ''),
                ffprobe_path=cfg_data.get('ffprobe', ''),
                # tasks=tasks,
                # task_kw=task_kw,
                dlc_models=cfg_data.get('dlc-models', {}),
                dlc_combos= cfg_data.get('dlc-process-combos', {}),
                anipose_env=cfg_data.get('anipose-conda-env', ''),
                anipose_cfgs=cfg_data.get('anipose-cfgs', {}),
            )
        except Exception as e:
            lg.error(f'Unexpected error occurred when creating Config obj: {e}')
            exit(1)

        valid, msg = Config.validate()
        if not valid:
            lg.warning((f'Config reading failed: \n{msg}'))
    except (ValueError, KeyError, TypeError) as e:
        lg.error(f'Failed parsing config: {e}')
        lg.debug(cfg_data)

if not Config:
    raise RuntimeError(f'Package cannot work without a global Config obj.')

if __name__ == '__main__':
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    lg.addHandler(handler)
    lg.setLevel(logging.DEBUG)
    print(Config)  