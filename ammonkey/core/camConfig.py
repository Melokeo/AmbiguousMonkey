'''
Camera setup
'''

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

from ..utils import ROIConfig as ROI

logger = logging.getLogger(__name__)

class CamGroup(Enum):
    '''cam grouping. value will be used to index subfolders!'''
    LEFT = 'L'
    RIGHT = 'R'

class LedColor(Enum):
    YELLOW = 'Y'
    GREEN  = 'G'
    # below are reserved, just
    RED    = 'R'
    WHITE  = 'W'
    NONE   = None

    @classmethod
    def from_char(cls, char: str) -> 'LedColor':
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
    # camera grouping
    groups: dict[int, CamGroup] = field(default_factory=lambda: {
        1: CamGroup.LEFT, 2: CamGroup.LEFT,
        3: CamGroup.RIGHT, 4: CamGroup.RIGHT
    })
    
    # sync detection settings
    rois: dict[int, list[int]] = field(default_factory=lambda: {
        1: [496, 55, 249, 223], 2: [211, 8, 149, 119],
        3: [864, 254, 131, 158], 4: [1007, 285, 171, 143],
    })
    
    led_colors: dict[int, str] = field(default_factory=lambda: {
        1: "Y", 2: "G", 3: "G", 4: "G"
    })

    # processing settings
    num_cameras: int = 4
    enabled_cameras: list[bool] = field(default_factory=lambda: [True] * 4)

    def __post_init__(self):
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

    def batchSelectROIs(self, vid_set:list[Path]):
        frame = 500
        if sum([1 for v in vid_set if v is not None and v.exists()]) != self.num_cameras:
            logger.error("Video set doesn't match cam num")
            return
        for i, v in enumerate(vid_set):
            if v is None or not v.exists():
                logger.error(f'batchSelectROIs: invalid video - {v}')
                continue
            roi = ROI.draw_roi(str(v), frame)
            if ROI is None:
                logger.warning('[warning] ROI not updated')
            self.rois[i+1] = roi
            
        