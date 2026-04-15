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

cfg_name_map = {
    'projects-path': 'projects_path',
    'animals': 'animal_paths',
    'cams': 'cam_settings',
    'ffmpeg': 'ffmpeg_path',
    'ffprobe': 'ffprobe_path',
    'sync-aud': 'sync_aud',
    'sync-led': 'sync_led',
    'vid-quality': 'vid_quality',
    # 'tasks': 'tasks',
    # 'task-keywords': 'task_kw',
    'dlc-models': 'dlc_models',
    'dlc-process-combos': 'dlc_combos',
    'anipose-conda-env': 'anipose_env',
    'anipose-cfgs': 'anipose_cfgs',
    'anipose-libs': 'anipose_libs',
}
cfg_name_map_rev = {v: k for k, v in cfg_name_map.items()}


@dataclass
class AniposeLibs:
    '''
    dict[str: dict]
    inner dict structure:
        {
            'path': Path,
            'models': list[str] (list of model keywords to wire to this lib)
        }
    '''
    libs: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_dicts(cls, dicts: dict[str, dict]) -> 'AniposeLibs':
        libs_dict = {}
        for name, d in dicts.items():
            # check for correct fields
            if name in libs_dict.keys():
                lg.warning(f'Duplicate anipose lib name in config: {name}, overwriting previous entry.')
            if not isinstance(d, dict):
                lg.error(f'Anipose lib config for {name} is not a dict: {type(d)}. skipping entry.')
                continue
            required_fields = ['path', 'models']
            if not all(k in d.keys() for k in required_fields):
                lg.error(f'Anipose lib config for {name} missing required fields, plz check config {required_fields}')
                continue

            path = str(d.get('path', ''))
            
            # fill allowed placeholders in path
            if '{home}' in path:
                path = path.format(home=str(Path.home()))

            path = Path(path)
            if not path.exists():
                lg.error(f'Anipose lib path for {name} does not exist: {path}. skipping entry.')
                continue
            
            libs_dict[name] = {
                'path': path,
                'models': d.get('models', [])
            }

        return cls(libs=libs_dict)

    def get_lib_path_for_key(self, key: str) -> Path | None:
        '''return matching lib that is contained as substr in given model key, first match'''
        for lib, info in self.libs.items():
            models = info.get('models', [])
            if not models or not isinstance(models, list):
                lg.error(f'Anipose lib {lib} has invalid models field (should be list): {models}. skipping.')
                continue
            for m in models:
                if m.lower() in key.lower():
                    return Path(info.get('path', ''))
        return None
    
    def get_lib_path_for_key_exact(self, key: str) -> Path | None:
        '''return matching lib for given model key, first match'''
        for lib, info in self.libs.items():
            if key in info.get('models', []):
                return Path(info.get('path', ''))
            elif key in [m.lower() for m in info.get('models', [])]:
                lg.warning(f'Key case mismatch for anipose lib model key: {key}')
                return Path(info.get('path', ''))
        return None

@dataclass
class _Config:
    projects_path: Path # actually never used cuz each animal has its own path configured
    animals: list[str]
    animal_paths: dict[str, str]
    cam_settings: dict[int, dict] 
    ffmpeg_path: str
    ffprobe_path: str
    sync_aud: dict
    sync_led: dict
    vid_quality: dict[str, list[str]]
    # tasks: dict[str, int]
    # task_kw: dict[str, list[str]]
    dlc_models: dict[str, dict]
    dlc_combos: dict[str, dict]
    anipose_env: str
    anipose_cfgs: dict[str, str]
    anipose_libs: AniposeLibs

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
        if not self.sync_aud:
            missing.append("sync_aud (default {})")
        if not self.sync_led:
            missing.append("sync_led (default {})")
        if not self.anipose_env:
            missing.append("anipose_env (empty)")
        if not self.anipose_cfgs:
            missing.append("anipose_cfgs (default {})")
        if not self.anipose_libs:
            missing.append("anipose_libs (default {})")

        # special checks
        for name, quality in self.vid_quality.items():
            if not name in self.animals:
                missing.append(f"vid_quality for {name} has no matching animal in animals list")
            elif not isinstance(quality, list) or len(quality) == 0:
                missing.append(f"vid_quality for {name} should be a non-empty list of ffmpeg parameters")
            elif not self._validate_ffmpeg_setting(quality):
                missing.append(f"Illegal vid_quality: {name} | {quality}")

        if missing:
            msg = "Missing or default fields:\n" + "\n".join(f" - {m}" for m in missing)
            return False, msg
        return True, "All config fields validated successfully."
    
    def save(self) -> None:
        '''save config back to file. comments will be lost.
        can use ruamel.yaml if needed in the future'''
        def flow_list_representer(dumper, data):
            return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
        yaml.add_representer(list, flow_list_representer)

        try:
            with open(cfg_path, 'w') as f:
                d = self.__dict__.copy()
                d['projects_path'] = str(self.projects_path)
                d['anipose_libs'] = {
                    k: {'path': str(v['path']), 'models': v['models']} 
                    for k, v in self.anipose_libs.libs.items()
                }
                # apply name mapping
                d = {cfg_name_map_rev.get(k, k): v for k, v in d.items()}

                yaml.dump(
                    d, f, 
                    default_flow_style=False, 
                    sort_keys=False)

            lg.info(f'Config saved to {cfg_path}')
        except Exception as e:
            lg.error(f'Failed to save config: {e}')

    # util methods
    def has_animal(self, animal: str) -> bool:
        return animal.lower() in [a.lower() for a in self.animals]
    
    def get_cam_groups(self) -> set[str]:
        '''return all cam group names'''
        groups = set()
        for cam_info in self.cam_settings.values():
            group = cam_info.get('group', None)
            if group:
                groups.add(group)
        return groups
    
    @staticmethod
    def _validate_ffmpeg_setting(setting: list[str]) -> bool:
        '''basic validation for ffmpeg setting list'''
        if not isinstance(setting, list) or len(setting) % 2 != 0:
            return False
        # further validation can be added here (check for known flags, ranges, etc)
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
                sync_aud=cfg_data.get('sync-aud', {}),
                sync_led=cfg_data.get('sync-led', {}),
                vid_quality=cfg_data.get('vid-quality', {}),
                # tasks=tasks,
                # task_kw=task_kw,
                dlc_models=cfg_data.get('dlc-models', {}),
                dlc_combos= cfg_data.get('dlc-process-combos', {}),
                anipose_env=cfg_data.get('anipose-conda-env', ''),
                anipose_cfgs=cfg_data.get('anipose-cfgs', {}),
                anipose_libs=AniposeLibs.from_dicts(cfg_data.get('anipose-libs', {}))
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

    from pprint import pp
    pp(Config.__dict__) 

    if input('run save: ') == 'y':
        Config.save()
        lg.info('saved')