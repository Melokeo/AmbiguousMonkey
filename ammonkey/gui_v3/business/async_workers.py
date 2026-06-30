import asyncio

from ammonkey import (
    VidSynchronizer, DLCModel, DLCProcessor, AniposeProcessor,
)
from ..landfill import JobStatus, TabJob, kennel
from ammonkey.utils.ol_logging import set_colored_logger
lg = set_colored_logger(__name__)


async def _run_sync_local(job: TabJob):
    job.sync_processing = True
    job.status = JobStatus.RUNNING
    await job.notify()
    try:
        if job.vs is None:
            raise ValueError('VidSynchronizer not created')

        result = await asyncio.to_thread(job.vs.syncAll)
        lg.info(f'Sync result: {result}')
        job.status = JobStatus.DONE
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED; raise
    except Exception as ex:
        job.status = JobStatus.ERROR
        job.last_error = str(ex)
        lg.exception('sync failed')
    finally:
        job.sync_processing = False
        await job.notify()


async def _run_sync_dask(job: TabJob):
    job.sync_processing = True
    job.status = JobStatus.RUNNING
    await job.notify()
    try:
        if job.vs is None:
            raise ValueError('VidSynchronizer not created')

        from ..landfill import scheduler, AWAIT_DASK_RESULTS
        from ...dask.dask_factory import create_sync_pipeline

        if scheduler is None:
            raise RuntimeError('Dask scheduler is not set')

        tasks = create_sync_pipeline(
            note=job.vs.notes,
            rois=job.vs.cam_config.rois,  # type: ignore
        )
        futures = scheduler.submit_tasks(tasks)
        lg.info('Submitted sync tasks to dask')
        await job.notify()

        if AWAIT_DASK_RESULTS:
            results = await asyncio.to_thread(scheduler.monitor_progress, futures)
            lg.info(f'Dask sync finished: {results}')

        job.status = JobStatus.DONE
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED; raise
    except Exception as ex:
        job.status = JobStatus.ERROR
        job.last_error = str(ex)
        lg.exception('sync (dask) failed')
    finally:
        job.sync_processing = False
        await job.notify()


async def _run_dlc_local(job: TabJob):
    job.dlc_processing = True
    job.status = JobStatus.RUNNING
    await job.notify()
    try:
        if job.selected_set is None:
            raise ValueError('Selected DLC model is None, which is impossible') 

        from ammonkey.core.dlc import dp_factory, initDlc
        dp_func = dp_factory.get(job.selected_set)
        if dp_func is None:
            raise ValueError(f'Unknown DLC model: {job.selected_set}')

        await asyncio.to_thread(initDlc)
        job.dp = dp_func(job.note)
        await job.notify()

        await asyncio.to_thread(job.dp.batchProcess)
        job.status = JobStatus.DONE
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED; raise
    except Exception as ex:
        job.status = JobStatus.ERROR
        job.last_error = str(ex)
        lg.exception('dlc failed')
    finally:
        job.dlc_processing = False
        await job.notify()

async def _run_dlc_dask(job: TabJob):
    job.dlc_processing = True
    job.status = JobStatus.RUNNING
    await job.notify()
    try:
        if job.selected_set is None:
            raise ValueError('Selected DLC model is None, which is impossible')

        from ..landfill import scheduler, AWAIT_DASK_RESULTS
        from ...dask.dask_factory import create_dlc_tasks

        if scheduler is None:
            raise RuntimeError('Dask scheduler is not set')

        tasks = create_dlc_tasks(
            note=job.note,
            processor_type=job.selected_set,
        )
        futures = scheduler.submit_tasks(tasks)
        lg.info('Submitted DLC tasks to dask')
        await job.notify()

        if AWAIT_DASK_RESULTS:
            results = await asyncio.to_thread(scheduler.monitor_progress, futures)
            lg.info('Dask DLC finished:')
            for i, r in enumerate(results):
                lg.info(f"{i:>4}. [{r.get('status')}] {r.get('task_id')} "
                        f"({r.get('type')}): {r.get('message')}")

        job.status = JobStatus.DONE
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED; raise
    except Exception as ex:
        job.status = JobStatus.ERROR
        job.last_error = str(ex)
        lg.exception('dlc (dask) failed')
    finally:
        job.dlc_processing = False
        await job.notify()


async def _run_anipose(job: TabJob):
    job.ani_processing = True
    job.status = JobStatus.RUNNING
    await job.notify()
    try:
        if job.selected_model is None:
            raise ValueError('Selected model is None, which is impossible') # already set it in tab_ani
        job.ap = AniposeProcessor(job.note, model_set_name=job.selected_model)
        job.ani_info = job.ap.info
        await job.notify()
        # anipose cli calls, to_thread now, rewrite as create_subprocess_exec later
        await asyncio.to_thread(job.ap.setupRoot)
        await asyncio.to_thread(job.ap.setupCalibs)
        await asyncio.to_thread(job.ap.calibrateCLI)
        await asyncio.to_thread(job.ap.batchSetup)
        await asyncio.to_thread(job.ap.triangulateCLI)
        job.status = JobStatus.DONE
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED; raise
    except Exception as ex:
        job.status = JobStatus.ERROR; 
        job.last_error = str(ex)
        lg.exception('anipose failed')
    finally:
        job.ani_processing = False
        await job.notify()


async def _run_anipose_mock(job: TabJob):
    '''fake run for test'''
    job.ani_processing = True
    job.status = JobStatus.RUNNING
    await job.notify()
    try:
        if job.selected_model is None:
            raise ValueError('Selected model is None, which is impossible') # already set it in tab_ani
        job.ani_info = f'Mocking anipose info for model {job.selected_model}'
        await job.notify()
        await asyncio.sleep(30) 
        job.status = JobStatus.DONE
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED; raise
    except Exception as ex:
        job.status = JobStatus.ERROR; 
        job.last_error = str(ex)
        lg.exception('anipose failed')
    finally:
        job.ani_processing = False
        await job.notify()