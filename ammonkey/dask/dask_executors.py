"""worker-side task executors"""

import logging
from pathlib import Path
from typing import Any

from dask.distributed import get_worker

from .dask_task import DaskTask, DaskType, NoteCache
from ..core.daet import DAET, Task
from ..core.expNote import ExpNote
from ..core.dlc import dp_factory, initDlc
from ..core.sync import VidSynchronizer, SyncConfig
from ..core.ani import AniposeProcessor
from ..core.dlcCollector import getUnprocessedDlcData
from ..utils import VidSyncLED as SyncLED

lg = logging.getLogger(__name__)
lg.debug('test')

# worker-level caching
_worker_cache: dict[str, Any] = {}

def execute_task(task: DaskTask) -> dict:
    """main task dispatcher on worker"""
    lg.info(f'exec_task: {task.id}')
    try:
        # dispatch to specific executor
        executors = {
            DaskType.DLC_BATCH: execute_dlc_batch,
            DaskType.DLC_SINGLE: execute_dlc_single,
            DaskType.SYNC_DETECT: execute_sync_detect,
            DaskType.SYNC_VIDEO: execute_sync_video,
            DaskType.ANI_CALIBRATE: execute_ani_calibrate,
            DaskType.ANI_TRIANGULATE: execute_ani_triangulate,
            DaskType.ANI_FULL: execute_ani_full,
            DaskType.ANI_PENDING: execute_ani_pending,
        }
        
        executor = executors.get(task.type)
        if not executor:
            return {
                'status': 'error',
                'task_id': task.id,
                'message': f'Unknown task type: {task.type}'
            }
        
        result = executor(task)
        result['task_id'] = task.id
        result['status'] = result.get('status', 'success')
        return result
        
    except Exception as e:
        lg.exception(f"Task {task.id} failed")
        return {
            'status': 'error',
            'task_id': task.id,
            'message': str(e),
            'type': type(e).__name__
        }

def _get_note(task: DaskTask) -> ExpNote:
    """load note from cache with worker-level caching"""
    cache_key = str(task.note_cache_path)
    
    if cache_key not in _worker_cache:
        cache = NoteCache()
        if task.note_cache_path is None:
            raise ValueError(f"Task {task.id} has no note_cache_path")
        _worker_cache[cache_key] = cache.load_note(task.note_cache_path)
    
    return _worker_cache[cache_key]

def _ensure_dlc_initialized():
    """ensure dlc is initialized on this worker"""
    if not _worker_cache.get('dlc_initialized'):
        if initDlc():
            _worker_cache['dlc_initialized'] = True
        else:
            raise RuntimeError("Failed to initialize DeepLabCut")

# === DLC Executors ===

def execute_dlc_batch(task: DaskTask) -> dict:
    """execute dlc batch processing"""
    lg.info(f'exec_dlc_batch: received task {task}')
    _ensure_dlc_initialized()
    
    note = _get_note(task)
    processor_type = task.params['processor_type']
    processor_func = dp_factory[processor_type]
    processor = processor_func(note)

    lg.info(f'{processor_func=}')
    
    # get daets to process
    if task.daet_dicts:
        daets = task.get_daets()
    else:
        daets = None  # process all valid

    lg.debug(f'{daets=}')
    
    results = processor.batchProcess(daets_to_process=daets)
    lg.debug(results)

    return {
        'daets_processed': len(results),
        'successful': sum(results.values()),
        'failed': [str(d) for d, success in results.items() if not success],
        'dlc_folder': processor.final_dlc_folder_name
    }

def execute_dlc_single(task: DaskTask) -> dict:
    """execute dlc for single daet"""
    _ensure_dlc_initialized()
    
    note = _get_note(task)
    processor_type = task.params['processor_type']
    processor_func = dp_factory[processor_type]
    processor = processor_func(note)
    
    daet = task.get_daets()[0]  # should have exactly one
    success = processor.analyzeSingleDaet(daet)
    
    return {
        'daet': str(daet),
        'success': success
    }

# === Sync Executors ===

def execute_sync_detect(task: DaskTask) -> dict:
    """execute combined sync detection (LED + audio + cross-validation)"""
    note = _get_note(task)
    daets = task.get_daets() if task.daet_dicts else note.getValidDaets(min_videos=2)
    
    from ..core.sync import VidSynchronizer, SyncConfig
    
    sync_cfg = SyncConfig()
    synchronizer = VidSynchronizer(note, sync_cfg=sync_cfg)

    rois = task.params.get('rois')
    if rois:
        synchronizer.cam_config.rois = rois
    
    detected_daets = synchronizer._getAllDetectedDaets(Task.ALL)
    daets_to_detect = [d for d in daets if not d in detected_daets]

    # run audio sync for all daets
    audio_results = synchronizer._runAudioSync(daets)
    
    # run LED detection and cross-validation for each
    detection_results = []
    for daet in daets_to_detect:
        try:
            audio_starts = audio_results.get(daet, [])
            sync_result = synchronizer._runLEDSync(daet, audio_starts)
            
            detection_results.append({
                'daet': str(daet),
                'status': sync_result.status,
                'message': sync_result.message,
                'led_starts': sync_result.led_starts,
                'audio_starts': sync_result.audio_starts,
                'corrected_starts': sync_result.corrected_starts,
                'config_created': sync_result.config_path is not None
            })
        except Exception as e:
            detection_results.append({
                'daet': str(daet),
                'status': 'error',
                'message': str(e)
            })
    
    successful = sum(1 for r in detection_results if r['status'] == 'success')
    warnings = sum(1 for r in detection_results if r['status'] == 'warning')
    
    return {
        'daets_processed': len(daets),
        'successful': successful,
        'warnings': warnings,
        'detection_results': detection_results,
        'skipped_existing': detected_daets
    }

def execute_sync_video(task: DaskTask) -> dict:
    """execute video synchronization (gpu-heavy)"""
    note = _get_note(task)
    daet = task.get_daets()[0]  # should have exactly one
    
    sync_folder = note.getDaetSyncRoot(daet)
    
    # find config file
    config_files = list(sync_folder.glob('sync_config_*.json'))
    if not config_files:
        return {
            'daet': str(daet),
            'success': False,
            'message': 'No sync config found'
        }
    
    import json
    with open(config_files[0]) as f:
        config = json.load(f)
    
    try:
        SyncLED.process_videos(config)
        (sync_folder / '.skipSync').touch()
        
        return {
            'daet': str(daet),
            'success': True
        }
    except Exception as e:
        return {
            'daet': str(daet),
            'success': False,
            'message': str(e)
        }

# === Anipose Executors ===

def execute_ani_calibrate(task: DaskTask) -> dict:
    """execute anipose calibration"""
    note = _get_note(task)
    model_set = task.params['model_set']
    
    ap = AniposeProcessor(note, model_set)
    ap.setupRoot()

    ap.setupCalibs()
    success = ap.calibrateCLI()
    
    if success:
        ap.collectCalibs()
    
    return {
        'model_set': model_set,
        'success': success,
        'calib_file': str(ap.calib_file) if ap.calib_file else None
    }

def execute_ani_triangulate(task: DaskTask) -> dict:
    """execute anipose triangulation"""
    note = _get_note(task)
    model_set = task.params['model_set']
    
    ap = AniposeProcessor(note, model_set)
    ap.batchSetup()
    
    success = ap.triangulateCLI()
    
    return {
        'model_set': model_set,
        'success': success,
        'ani_root': str(ap.ani_root_path)
    }

def execute_ani_full(task: DaskTask) -> dict:
    """execute full anipose pipeline"""
    note = _get_note(task)
    model_set = task.params['model_set']
    
    ap = AniposeProcessor(note, model_set)
    
    try:
        success = ap.runPipeline()
        
        return {
            'model_set': model_set,
            'success': success,
            'ani_root': str(ap.ani_root_path),
            'calib_file': str(ap.calib_file) if ap.calib_file else None
        }
    except Exception as e:
        return {
            'model_set': model_set,
            'success': False,
            'message': str(e)
        }

def execute_ani_pending(task: DaskTask) -> dict:
    def implode(l):
        return ', '.join(l)
        
    note = _get_note(task)
    msns = getUnprocessedDlcData(data_path=note.data_path, note=note)
    if not msns:
        lg.info('execute_ani_pending: found nothing for anipose.')
        return {
            'success': False,
            'message': 'Found zero model set for anipose.'
        }
    
    results: list[dict] = []

    for msn in msns:
        lg.info(f'AP processing {msn}')
        ap = AniposeProcessor(note, msn)
        try:
            success = ap.runPipeline()
            results.append( {
                'model_set': msn,
                'success': success,
                'ani_root': str(ap.ani_root_path),
                'calib_file': str(ap.calib_file) if ap.calib_file else None,
            } )
        except Exception as e:
            lg.error(f'execute_ani_pending ({msn}): {e}')
            results.append( {
                'model_set': msn,
                'success': False,
                'message': str(e)
            } )

    return {
        'model_sets': implode(d['model_set'] for d in results),
        'success': implode(str(d['success']) for d in results),
        'message': implode(d.get('message', '-') for d in results),
    }
    