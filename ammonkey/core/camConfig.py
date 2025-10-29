'''
Camera setup
'''

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

from ..utils import ROIConfig as ROI
from ..core.config import Config

logger = logging.getLogger(__name__)

class CamGroup(Enum):
    '''cam grouping. value will be used to index subfolders!'''
    LEFT = 'L'
    RIGHT = 'R'
    UNDEFINED = 'NA'

    @classmethod
    def from_char(cls, char: str) -> 'CamGroup':
        for group in cls:
            if group.value == char:
                return group
        raise ValueError(f"Invalid camera group character: {char}")

class LedColor(Enum):
    YELLOW = 'Y'
    GREEN  = 'G'
    # below are reserved, just
    RED    = 'R'
    BLUE   = 'B'
    WHITE  = 'W'
    NONE   = None

    @classmethod
    def from_char(cls, char: str) -> 'LedColor':
        if char is None or char == '':
            return cls.NONE
        for color in cls:   
            if color.value == char:
                return color
        raise ValueError(f"Invalid LED color character: {char}")

@dataclass
class Camera:
    '''(planned) object to describe and store cam-specific routing'''
    name: str
    index: int      # consider change this to int | str and allow letter indexing
    group: CamGroup
    roi: tuple[int,...] | None = None
    led_color: LedColor = LedColor.NONE
    enabled: bool = True

@dataclass
class CamConfig:
    """Flexible camera configuration for different setups"""
    #TODO move these values to amm-config.yaml
    # camera grouping, note this starts from 1 not 0
    groups: dict[int, CamGroup] = field(default_factory=lambda: {
        ind: CamGroup.from_char(cam.get('group', 'NA'))
        for ind, cam in Config.cam_settings.items()
    })

    # sync detection settings in X, Y, W, H
    rois: dict[int, tuple[int]] = field(default_factory=lambda: {
        ind: tuple(cam.get('roi', [0, 0, 1920, 1080]))
        for ind, cam in Config.cam_settings.items()
    })
    
    led_colors: dict[int, str] = field(default_factory=lambda: {
        ind: cam.get('led_color', '')
        for ind, cam in Config.cam_settings.items()
    })

    headers_in_note: dict[int, str] = field(default_factory=lambda: {
        ind: cam.get('header_in_note', '_N/A_')
        for ind, cam in Config.cam_settings.items()
    })

    # processing settings
    enabled_cameras: list[bool] = field(default_factory=lambda: [True] * 4)

    def __post_init__(self):
        # reject if dict keys doesn't match each other
        if not (self.groups.keys() == self.rois.keys() == self.led_colors.keys()):
            raise ValueError("CamConfig dict keys mismatch among groups, rois, led_colors")

        self.cams_dict: dict[int, Camera] = {
            ind: Camera(
                name=f'cam{ind}',
                index=ind,
                group=grp,
                roi=tuple(roi),
                led_color=LedColor.from_char(led),
            ) for ind, grp, roi, led in zip(
                self.groups.keys(), self.groups.values(),
                self.rois.values(), self.led_colors.values()
            )
        }
    
    @property
    def cams(self) -> list[Camera]:
        return list(self.cams_dict.values())
    
    @property
    def num_cams(self) -> int:
        return len(self.cams_dict.values())
    
    @property
    def evolved_groups(self) -> set[CamGroup]:
        """get set of camera groups used in config"""
        return set(self.groups.values())
    
    def getGroupCameras(self, group: CamGroup) -> list[int]:
        """get camera indices for given group"""
        return [cam for cam, grp in self.groups.items() if grp == group]
    
    def getEnabledCameras(self) -> list[int]:
        """get indices of enabled cameras"""
        return [i+1 for i, enabled in enumerate(self.enabled_cameras) if enabled]
    
    def isValidSetup(self, video_ids: list[int | None]) -> bool:
        """check if video configuration is valid for processing"""
        enabled = self.getEnabledCameras()
        available = [i+1 for i, vid in enumerate(video_ids) if vid is not None]
        
        # need at least 2 cameras per group for 3D
        groups_with_cams = {}
        for cam in available:
            if cam in enabled:
                group = self.groups.get(cam)
                if group:
                    groups_with_cams[group] = groups_with_cams.get(group, 0) + 1
        
        return len([g for g, count in groups_with_cams.items() if count >= 2]) >= 1

    def batchSelectROIs(self, vid_set:list[Path|None], frame_to_use:int=500) -> None:
        '''main function when setting ROI for sync'''
        
        for i, v in enumerate(vid_set):
            if v is None or not v.exists():
                logger.error(f'batchSelectROIs: invalid video - {v}')
                continue
            roi = ROI.draw_roi(str(v), frame_to_use)
            if roi is None:
                logger.warning('[warning] ROI not updated')
            else:
                #FIXME here should refer to [vid order - cam idx mapping] from config above
                # instead of directly i+1
                self.rois[i+1] = tuple(roi)

if __name__ == '__main__':
    cam_cfg = CamConfig()
    print(f'Number of cameras: {cam_cfg.num_cams}')
    for cam in cam_cfg.cams:
        print(cam)