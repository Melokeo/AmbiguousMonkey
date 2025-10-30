# GUI shared states

from ..core.expNote import ExpNote
from pathlib import Path

from ..utils.ol_logging import set_colored_logger
lg = set_colored_logger(__name__)

note: ExpNote = None   
note_filtered: ExpNote = None

try:
    from ..dask.dask_scheduler import DaskScheduler
    scheduler: DaskScheduler | None = None
    USE_DASK: bool = False
except (ImportError, ModuleNotFoundError) as e:
    USE_DASK = False

AWAIT_DASK_RESULTS: bool = True