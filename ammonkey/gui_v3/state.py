'''
objects here preserves state independent of ui rendering
'''

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
import asyncio
from enum import Enum

from ammonkey.core.expNote import ExpNote, DAET
from ammonkey import VidSynchronizer, DLCModel, DLCProcessor, AniposeProcessor

class JobStatus(Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    DONE = 'done'
    ERROR = 'error'
    CANCELLED = 'cancelled'

@dataclass
class TabJob:
    '''represents a long-running job started from gui, to preserve state across tab switches'''
    key: tuple[str, str]        # (animal, date)
    note: ExpNote
    task: asyncio.Task | None = field(init=False, default=None, repr=False)
    status: JobStatus = field(init=False, default=JobStatus.IDLE)
    # async callback, will be tab renderer method
    _subscriber: Callable[['TabJob'], Awaitable[None]] | None = field(
        init=False, default=None, repr=False
    )

    # sync
    vs: VidSynchronizer | None = field(init=False, default=None)
    sync_processing: bool = field(init=False, default=False)
    # dlc
    dp: DLCProcessor | None = field(init=False, default=None)
    selected_set: str | None = field(init=False, default=None)
    dlc_processing: bool = field(init=False, default=False)
    # anipose
    ap: AniposeProcessor | None = field(init=False, default=None)
    ani_processing: bool = field(init=False, default=False)
    selected_model: str | None = field(init=False, default=None)
    selected_vid: str | None = field(init=False, default=None)
    rng_video: tuple[float, float] = field(init=False, default=(30.0, 60.0))
    ani_info: str = field(init=False, default='')
    last_error: str | None = field(init=False, default=None)

    def __repr__(self) -> str:
        current_running = []
        if self.sync_processing:
            current_running.append('sync')
        if self.dlc_processing:
            current_running.append('dlc')
        if self.ani_processing:
            current_running.append('ani')
        return f'TabJob(key={self.key}, running={current_running})'

            
    @property
    def is_running(self) -> bool:
        return self.task is not None and not self.task.done()

    def subscribe(self, cb) -> None:
        self._subscriber = cb

    def unsubscribe(self) -> None:
        self._subscriber = None

    async def notify(self) -> None:
        cb = self._subscriber   # idk, direct call might cause subscriber to be None b/w check and call
        if cb is not None:
            await cb(self)

    def cancel(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()


class JobKennel:
    '''Store multiple TabJob here'''
    def __init__(self) -> None:
        self.jobs: dict[tuple[str, str], TabJob] = {}

    def get(self, animal, date) -> TabJob | None:
        return self.jobs.get((animal, date), None)

    # i dont think it really needs to new a job in any case
    def get_or_new(self, animal:str, date:str, note: ExpNote,) -> TabJob:
        key = (animal, date)
        if key not in self.jobs:
            self.jobs[key] = TabJob(key=key, note=note)
        return self.jobs[key]
    
    def update_job(self, job: TabJob) -> None:
        if not isinstance(job, TabJob):
            raise ValueError(f'update_job: expected TabJob, got {type(job)}')
        if not job.key in self.jobs:
            raise KeyError(f'update_job: job with key {job.key} not found in kennel')
        self.jobs[job.key] = job