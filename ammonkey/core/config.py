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
    # tasks: dict[str, int]
    # task_kw: dict[str, list[str]]
    dlc_models: dict[str, dict]
    dlc_combos: dict[str, dict]
    anipose_cfgs: dict[str, str]

    def validate(self) -> bool:
        return True

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
        
        # tasks = cfg_data.get('tasks', None)
        # if not tasks:
        #     raise ValueError('No task is defined in config. plz check amm-config.yaml file.')
        # 
        # task_kw = cfg_data.get('task-keywords', {})
        # if not validate_task_match(tasks, task_kw):
        #     raise ValueError('Task matching criteria doesn\'t match task items in config. plz check amm-config.yaml file.')
        
        Config = _Config(
            projects_path=Path(cfg_data.get('projects-path', '')),
            animals=[k for k in animals.keys()],
            animal_paths=animals,
            cam_settings=cfg_data.get('cams', {}),
            # tasks=tasks,
            # task_kw=task_kw,
            dlc_models=cfg_data.get('dlc-models', {}),
            dlc_combos= cfg_data.get('dlc-process-combos', {}),
            anipose_cfgs=cfg_data.get('anipose-cfgs', {}),
        )
    except (ValueError, KeyError, TypeError) as e:
        lg.error(f'Failed parsing config: {e}')
        lg.debug(cfg_data)

if not Config:
    raise RuntimeError(f'Package cannot work without a global Config obj.')

if __name__ == '__main__':
    print(Config)  