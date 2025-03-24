import os
from pathlib import Path

ANIMALS = ['Pici']  #TODO this should be configurable

class PathMngr:
    def __init__(self, raw=None):
        self._PPATH_RAW = None
        self._vid_path = []
        self._cfg_path = []
        self._ani_base = None
        self._calib_idx = []
        self._dlc_mdl_path = {'L': None, 'R': None}
        if raw:
            self.PPATH_RAW = raw

    @property
    def PPATH_RAW(self):
        return self._PPATH_RAW
    
    @PPATH_RAW.setter
    def PPATH_RAW(self, v):
        if not v:
            raise ValueError('None occurred in PPATH_RAW.setter')
        if not os.path.exists(v):
           #  print(f"ValueError(f'PPATH_RAW.setter Path not found: {v}')")
           raise ValueError(f'PPATH_RAW.setter Path not found: {v}')
        else:
            self._PPATH_RAW = v
        print(f"[LOG] Updated PPATH_RAW to {v}")
    
    @property
    def data_path(self):
        return self._PPATH_RAW.replace('DATA_RAW', 'DATA') if self._PPATH_RAW else None

    @property
    def animal(self):
        path = Path(self._PPATH_RAW)
        pt = path.parts
        animal = next((p for p in pt if p in ANIMALS), None)
        if animal is None:
            raise ValueError(f"Check animal name in raw path. Recognized names: {ANIMALS}")
        return animal
    
    @property
    def date(self):
        path = Path(self._PPATH_RAW)
        pt = path.parts
        return pt[-1]
    
    @property
    def vid_path(self):
        return self._vid_path
    
    @vid_path.setter
    def vid_path(self, v):
        if not isinstance(v, list):
            raise ValueError(f'(Internal) Passed invalid vid_path {v}')
        self._vid_path = v
    
    @property
    def cfg_path(self):
        return self._cfg_path
    
    @cfg_path.setter
    def cfg_path(self, v):
        if not isinstance(v, list):
            raise ValueError(f'(Internal) Passed invalid cfg_path {v}')
        self._cfg_path = v

    @property
    def ani_base_path(self):
        return os.path.join(self.data_path, 'anipose')
    
    @property
    def calib_idx(self):
        return self._calib_idx
    
    @calib_idx.setter
    def calib_idx(self, v):
        self._calib_idx = v

    @property
    def dlc_mdl_path(self):
        return self._dlc_mdl_path
    
    @dlc_mdl_path.setter
    def dlc_mdl_path(self, p:dict):
        for side, path in p.items():
            if side in ['L', 'R']:
                if os.path.exists(os.path.join(path, 'config.yaml')):
                    self._dlc_mdl_path[side] = path
                else:
                    raise FileNotFoundError(f'Unable to locate config.yaml in {path}')
                
    @property
    def dlc_cfg_path(self):
        haspath = all([p for _, p in self._dlc_mdl_path.items()])
        if haspath:
            return {s: os.path.join(p,'config.yaml') for s, p in self._dlc_mdl_path.items()}
    
    def show(self):
        return f"""
        --- Path Summary ---
        Raw Path: {self.PPATH_RAW}
        Data Path: {self.data_path}
        Animal: {self.animal}
        Date: {self.date}
        Video Paths: {self.vid_path}
        --------------------
        """