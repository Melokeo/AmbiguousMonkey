# GUI shared states

from ..core.expNote import ExpNote
from pathlib import Path

from ..utils.ol_logging import set_colored_logger
lg = set_colored_logger(__name__)

note: ExpNote = None     #type: ignore
note_filtered: ExpNote = None #type: ignore

try:
    from ..dask.dask_scheduler import DaskScheduler
    scheduler: DaskScheduler | None = None
    USE_DASK: bool = False
except (ImportError, ModuleNotFoundError) as e:
    USE_DASK = False

AWAIT_DASK_RESULTS: bool = True

from .state import JobKennel, TabJob, JobStatus
kennel = JobKennel()

curr_job: TabJob | None = None