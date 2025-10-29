"""task factory functions for creating dask tasks"""

from pathlib import Path
import logging
from datetime import datetime
import hashlib
import os

from .dask_task import DaskTask, DaskType, NoteCache
from ..core.expNote import ExpNote
from ..core.daet import DAET
from ..core.dlcCollector import getUnprocessedDlcData

lg = logging.getLogger(__name__)

def create_dlc_tasks(note: ExpNote, processor_type: str, 
                     daets: list[DAET] | None = None,
                     batch_mode: bool = True) -> list[DaskTask]:
    """create dlc processing tasks"""
    cache = init_note_cache_dir(note)
    cache_path = cache.save_note(note)
    
    tasks = []
    
    if batch_mode:
        # single batch task for all daets
        task = DaskTask(
            id=f"dlc_batch_{note.animal}_{note.date}_{processor_type}",
            type=DaskType.DLC_BATCH,
            params={'processor_type': processor_type},
            priority=2
        )
        task.set_note(note, cache_path)
        
        if daets:
            task.add_daets(daets)
        
        tasks.append(task)
    else:
        # individual tasks per daet
        daets = daets or note.daets
        for daet in daets:
            task = DaskTask(
                id=f"dlc_{str(daet)}_{processor_type}",
                type=DaskType.DLC_SINGLE,
                params={'processor_type': processor_type},
                priority=3
            )
            task.set_note(note, cache_path)
            task.add_daet(daet)
            tasks.append(task)
    
    return tasks

def create_sync_pipeline(note: ExpNote, daets: list[DAET] | None = None, rois: dict[int, list[int]]|None = None) -> list[DaskTask]:
    """create full sync pipeline (detection + video processing)"""
    cache = init_note_cache_dir(note)
    cache_path = cache.save_note(note)
    
    if daets is None:
        daets = note.getValidDaets(min_videos=2)
    
    tasks = []
    
    # phase 1: combined detection task (audio + LED + cross-validation)
    detect_task = DaskTask(
        id=f"sync_detect_{note.animal}_{note.date}",
        type=DaskType.SYNC_DETECT,
        priority=1
    )
    detect_task.set_note(note, cache_path)
    detect_task.add_daets(daets)
    if rois:
        detect_task.params["rois"] = rois
    tasks.append(detect_task)
    
    # phase 2: video sync per daet (gpu-heavy)
    for daet in daets:
        video_task = DaskTask(
            id=f"sync_video_{str(daet)}",
            type=DaskType.SYNC_VIDEO,
            dependencies=[detect_task.id],
            priority=4
        )
        video_task.set_note(note, cache_path)
        video_task.add_daet(daet)
        tasks.append(video_task)
    
    return tasks

def create_ani_pipeline(note: ExpNote, model_set: str,
                       calibrate_only: bool = False,
                       triangulate_only: bool = False,
                       with_hash: bool = False) -> list[DaskTask]:
    """create anipose pipeline tasks"""
    cache = init_note_cache_dir(note)
    cache_path = cache.save_note(note)
    
    tasks = []
    
    if not triangulate_only:
        # calibration task
        calib_task = DaskTask(
            id=f"ani_calib_{note.animal}_{note.date}_{model_set}",
            type=DaskType.ANI_CALIBRATE,
            params={'model_set': model_set},
            priority=5
        )
        calib_task.set_note(note, cache_path)
        tasks.append(calib_task)
        
        if calibrate_only:
            return tasks
    
    if not calibrate_only:
        # triangulation task
        tri_task = DaskTask(
            id=f"ani_tri_{note.animal}_{note.date}_{model_set}",
            type=DaskType.ANI_TRIANGULATE,
            params={'model_set': model_set},
            priority=5
        )
        tri_task.set_note(note, cache_path)
        
        # add dependency if calibration is included
        if not triangulate_only and tasks:
            tri_task.dependencies.append(tasks[0].id)

        # add hash id if needed
        if with_hash:
            tri_task = hashed_task(tri_task, note.daets)
            print(tri_task.id)
        
        tasks.append(tri_task)
    
    return tasks

def create_ani_pending(note: ExpNote) -> list[DaskTask]:
    cache = init_note_cache_dir(note)
    cache_path = cache.save_note(note)

    ani_pending_task = DaskTask(
        id=f"ani_pending_{note.animal}_{note.date}",
        type=DaskType.ANI_PENDING,
        params={},
        priority=5
    )
    ani_pending_task.set_note(note, cache_path)
    
    return [ani_pending_task]
    

def create_full_pipeline(
        note: ExpNote,
        processor_type: str,
        daets: list[DAET] | None = None,
        rois: dict[int, list[int]]|None = None,
) -> list[DaskTask]:
    """create complete processing pipeline: sync -> dlc -> anipose"""
    all_tasks = []
    
    # 1. sync pipeline
    sync_tasks = create_sync_pipeline(note, daets, rois)
    all_tasks.extend(sync_tasks)
    
    # get last sync task id for dependency
    if sync_tasks:
        last_sync_id = sync_tasks[-1].id
    else:
        lg.error('dask_factory: Sync task is empty')
        return []
    
    # 2. dlc tasks (depend on sync)
    dlc_tasks = create_dlc_tasks(note, processor_type, daets, batch_mode=False)
    if sync_tasks:
        for task in dlc_tasks:
            task.dependencies.extend([t.id for t in sync_tasks])
    all_tasks.extend(dlc_tasks)
    
    # 3. anipose tasks (depend on dlc)
    ani_tasks = create_ani_pending(note)
    if dlc_tasks:
        for task in ani_tasks:
            task.dependencies.extend([t.id for t in dlc_tasks])
    all_tasks.extend(ani_tasks)
    
    return all_tasks

# collision avoider, optional
def timestamped_tasks(tasks: list[DaskTask]) -> list[DaskTask]:
    """Add timestamp to task IDs to prevent duplicate task collisions"""
    timestamp = datetime.now().strftime("%H%M%S")
    for task in tasks:
        task.id = f"{task.id}@{timestamp}"
    
    return tasks

def make_hashable(obj):
    """Convert object to hashable equivalent"""
    if isinstance(obj, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return tuple(make_hashable(item) for item in obj)
    elif isinstance(obj, set):
        return tuple(sorted(make_hashable(item) for item in obj))
    else:
        return obj

def hashed_task(task: DaskTask, hash_in) -> DaskTask:
    hashable = make_hashable(hash_in)
    task_hash = hashlib.md5(str(hashable).encode()).hexdigest()[:8]
    task.id = f"{task.id}#{task_hash}"
    return task

def init_note_cache_dir(note: ExpNote) -> NoteCache:
    cache_dir = note.data_path / '.ammonkey'
    if not cache_dir.exists():
        cache_dir.mkdir()
        lg.debug(f'New note cache dir: {cache_dir}')
    if os.name == 'nt':
        os.system(f'attrib +H "{cache_dir}"')
    return NoteCache(cache_dir)