#from .utils.VidSyncLEDv2_3 import *
#from .utils.VidSyncAudV2 import *
#from .h5rewrite1 import *
# from .gui.ambiguousGUI import PipelineGUI

#print('MonkeyUnity Imported')

from pathlib import Path

from .core.daet import DAET
from .core.expNote import ExpNote, Task, iter_notes, iter_xlsx, get_xlsx_dates
from .core.camConfig import CamGroup, CamConfig, Camera

from .core.sync import syncVideos, VidSynchronizer, SyncConfig, SyncResult

from .core.dlc import DLCProcessor, DLCModel
from .core.dlc import (
    modelPreset, initDlc, model_factory, available_models, available_dp,
)
from .core.dlcCollector import mergeDlcOutput, getUnprocessedDlcData
from .core.ani import AniposeProcessor, runAnipose
from .core.finalize import violentCollect
from .core.fileOp import dataSetup

from .utils.ol_logging import ColorLoggingFormatter, set_colored_logger

import logging

lg = set_colored_logger(__name__)
lg.info('test')