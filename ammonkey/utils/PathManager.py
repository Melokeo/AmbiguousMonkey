"""
store paths used in mky, but doesn't handle any logic
all paths are Path objects
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ANIMALS = ['Pici']  # TODO this should be configurable

@dataclass
class PathMngr:
   raw: Optional[Path] = None
   _vid_path: list[Path] = field(default_factory=list, init=False)
   _cfg_path: list[Path] = field(default_factory=list, init=False)
   _calib_idx: list = field(default_factory=list, init=False)
   _dlc_mdl_path: dict[str, Optional[Path]] = field(
       default_factory=lambda: {'L': None, 'R': None}, init=False
   )

   def __post_init__(self):
       if self.raw:
           self.PPATH_RAW = self.raw

   @property
   def PPATH_RAW(self) -> Optional[Path]:
       return getattr(self, '_PPATH_RAW', None)
   
   @PPATH_RAW.setter
   def PPATH_RAW(self, v: Path | str) -> None:
       if not v:
           raise ValueError('None occurred in PPATH_RAW.setter')
       
       path = Path(v)
       if not path.exists():
           raise FileNotFoundError(f'PPATH_RAW.setter Path not found: {v}')
       
       self._PPATH_RAW = path
       print(f"[LOG] Updated PPATH_RAW to {v}")
   
   @property
   def data_path(self) -> Optional[Path]:
       if not self._PPATH_RAW:
           return None
       return Path(str(self._PPATH_RAW).replace('DATA_RAW', 'DATA'))

   @property
   def animal(self) -> str:
       if not self._PPATH_RAW:
           raise ValueError("PPATH_RAW not set")
       
       animal = next((p for p in self._PPATH_RAW.parts if p in ANIMALS), None)
       if animal is None:
           raise ValueError(f"Check animal name in raw path. Recognized names: {ANIMALS}")
       return animal
   
   @property
   def date(self) -> str:
       if not self._PPATH_RAW:
           raise ValueError("PPATH_RAW not set")
       return self._PPATH_RAW.parts[-1]
   
   @property
   def vid_path(self) -> list[Path]:
       return self._vid_path
   
   @vid_path.setter
   def vid_path(self, v: list[Path]) -> None:
       if not isinstance(v, list):
           raise ValueError(f'(Internal) Passed invalid vid_path {v}')
       self._vid_path = v
   
   @property
   def cfg_path(self) -> list[Path]:
       return self._cfg_path
   
   @cfg_path.setter
   def cfg_path(self, v: list[Path]) -> None:
       if not isinstance(v, list):
           raise ValueError(f'(Internal) Passed invalid cfg_path {v}')
       self._cfg_path = v

   @property
   def ani_base_path(self) -> Optional[Path]:
       return self.data_path / 'anipose' if self.data_path else None
   
   @property
   def calib_idx(self) -> list:
       return self._calib_idx
   
   @calib_idx.setter
   def calib_idx(self, v: list) -> None:
       self._calib_idx = v

   @property
   def dlc_mdl_path(self) -> dict[str, Optional[Path]]:
       return self._dlc_mdl_path
   
   @dlc_mdl_path.setter
   def dlc_mdl_path(self, p: dict[str, Path | str]) -> None:
       for side, path in p.items():
           if side in ['L', 'R']:
               path_obj = Path(path)
               if (path_obj / 'config.yaml').exists():
                   self._dlc_mdl_path[side] = path_obj
               else:
                   raise FileNotFoundError(f'Unable to locate config.yaml in {path}')
               
   @property
   def dlc_cfg_path(self) -> Optional[dict[str, Path]]:
       haspath = all(p for p in self._dlc_mdl_path.values())
       if haspath:
           return {s: p / 'config.yaml' for s, p in self._dlc_mdl_path.items() if p}
   
   def show(self) -> str:
       return f"""
       --- Path Summary ---
       Raw Path: {self.PPATH_RAW}
       Data Path: {self.data_path}
       Animal: {self.animal}
       Date: {self.date}
       Video Paths: {self.vid_path}
       --------------------
       """