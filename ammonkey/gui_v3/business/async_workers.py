import asyncio

from ammonkey import (
    VidSynchronizer, DLCModel, DLCProcessor, AniposeProcessor,
)
from ..landfill import JobStatus, TabJob, kennel
from ammonkey.utils.ol_logging import set_colored_logger
lg = set_colored_logger(__name__)

async def _run_anipose(job: TabJob):
    '''fake run for test'''
    job.ani_processing = True
    job.status = JobStatus.RUNNING
    await job.notify()
    try:
        if job.selected_model is None:
            raise ValueError('Selected model is None, which is impossible') # already set it in tab_ani
        job.ap = AniposeProcessor(job.note, model_set_name=job.selected_model)
        job.ani_info = 'Mocking anipose info for model ' + job.selected_model
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

async def _run_anipose_real(job: TabJob):
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