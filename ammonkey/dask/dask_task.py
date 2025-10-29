"""dask task definitions and serialization"""

import pickle
from enum import Enum
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

from ..core.daet import DAET
from ..core.expNote import ExpNote

class DaskType(Enum):
    # gpu-heavy tasks
    DLC_BATCH = "dlc_batch"
    DLC_SINGLE = "dlc_single"  
    SYNC_VIDEO = "sync_video"  # SyncLED.process_videos
    
    # cpu-heavy tasks
    SYNC_DETECT = "sync_detect"  # combined detection + cross-validation
    ANI_CALIBRATE = "ani_calibrate"
    ANI_TRIANGULATE = "ani_triangulate"
    ANI_FULL = "ani_full"  # calibrate + triangulate pipeline
    ANI_PENDING = 'ani_pending'

    THRU = 'full_run'

REQUIRES_GPU = [
            DaskType.DLC_BATCH, 
            DaskType.DLC_SINGLE,
            DaskType.SYNC_VIDEO
        ]

@dataclass
class DaskTask:
    """serializable task for dask execution"""
    id: str
    type: DaskType
    priority: int = 0
    params: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    
    # note and daet tracking
    note_cache_path: Path | None = None
    daet_dicts: list[dict] = field(default_factory=list)  # serialized daets
    
    @property
    def requires_gpu(self) -> bool:
        return self.type in REQUIRES_GPU
    
    def __repr__(self) -> str:
        return f"DaskTask(id={self.id}, type={self.type}, gpu={self.requires_gpu}, prio={self.priority})"

    def set_note(self, note: ExpNote, cache_path: Path) -> None:
        """attach note context via cache file"""
        self.note_cache_path = cache_path
        self.params['note_animal'] = note.animal
        self.params['note_date'] = note.date
        self.params['data_path'] = str(note.data_path)
    
    def add_daet(self, daet: DAET) -> None:
        """serialize and add single daet"""
        self.daet_dicts.append({
            'date': daet.date,
            'animal': daet.animal,
            'experiment': daet.experiment,
            'task': daet.task
        })
    
    def add_daets(self, daets: list[DAET]) -> None:
        """serialize and add multiple daets"""
        for daet in daets:
            self.add_daet(daet)
    
    def get_daets(self) -> list[DAET]:
        """reconstruct daets from serialized form"""
        return [DAET(**d) for d in self.daet_dicts]

class NoteCache:
    """handles note serialization for worker access"""
    
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / '.ammonkey' / 'dask_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def save_note(self, note: ExpNote) -> Path:
        """serialize note to cache file"""
        # use hash of daets to ensure uniqueness for filtered notes
        daet_hash = hash(tuple(str(d) for d in note.daets))
        cache_name = f"{note.animal}_{note.date}_{abs(daet_hash) % 100000:05d}.pkl"
        cache_path = self.cache_dir / cache_name
        
        with open(cache_path, 'wb') as f:
            pickle.dump(note, f)
        
        return cache_path
    
    def load_note(self, cache_path: Path) -> ExpNote:
        """load note from cache file"""
        with open(cache_path, 'rb') as f:
            return pickle.load(f)
    
    def cleanup(self, older_than_days: int = 7) -> None:
        """remove old cache files"""
        import time
        cutoff = time.time() - (older_than_days * 24 * 3600)
        
        for cache_file in self.cache_dir.glob('*.pkl'):
            if cache_file.stat().st_mtime < cutoff:
                cache_file.unlink()