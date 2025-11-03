'''
refactored full pipeline logic from flet_main
'''

from typing import TYPE_CHECKING
import flet as ft
from .. import landfill as lf

if TYPE_CHECKING:
    from ..flet_main import AmmApp

def run_all_local(e: ft.ControlEvent, app: AmmApp) -> None:
    dlg_sync_set_roi = ft.AlertDialog(
        title=ft.Text('Set ROIs needed'),
        content=ft.Text('Plz set ROIs before running everything.'),
        alignment=ft.alignment.center,
    )

    dlg_set_dlc_model = ft.AlertDialog(
        title=ft.Text('DLC model not selected'),
        content=ft.Text('Plz select DLC models before running everything.'),
        alignment=ft.alignment.center,
    )

    if not lf.note:
        app.lg.error('No note is set')
        return

    if not hasattr(app.tab_sync, 'vs') or not app.tab_sync.vs:
        app.pg.open(dlg_sync_set_roi)
        app.tab_setup.on_setup_click(e)
        app.tab_sync.on_create_click(e)
        app.tab_sync.on_set_all(e)
        return
    
    model = app.tab_dlc.model_dropdown.value
    if model:
        app.lg.debug(f'on_run_all: {lf.note_filtered=}, {model=}')
    else:
        app.lg.error('on_run_all: dlc model not selected')
        app.tabs.selected_index = 2
        app.pg.open(dlg_set_dlc_model)
        return
    
    app.lg.info(f'Running through pipeline with {lf.note_filtered}')
    app.lg.info(f'Model used: {model}')

    app.tab_sync.on_sync_all(e)

    app.tab_dlc.on_run_dlc_click(e)

    app.tab_ani.on_model_refresh_click(e)
    app.tab_ani.on_run_anipose_click(e)

    app.tab_ani.on_vid_refresh_click(e)
    app.tab_ani.on_make_vid_click(e)

    app.tab_final.on_collect_click(e)

def run_all_dask(app: AmmApp) -> None:
    try:
        from ...dask.dask_factory import create_full_pipeline
    except ImportError as e:
        app.lg.error('Failed to import dask')
        return
    if not lf.note:
        app.lg.error('No note is set')
        return
    if not lf.scheduler:
        app.lg.error('Scheduler is not connected')
        return
    
    if not app.tab_sync.vs:
        app.lg.error('on_run_all: vid synchronizer instance not created')
        return
    model = app.tab_dlc.model_dropdown.value
    if model:
        app.lg.debug(f'on_run_all: {lf.note_filtered=}, {model=}')
    else:
        app.lg.error('on_run_all: dlc model not selected')
        return
    
    tasks = create_full_pipeline(
        note=lf.note_filtered,
        processor_type=model,
        rois=app.tab_sync.vs.cam_config.rois #type:ignore
    )

    futures = lf.scheduler.submit_tasks(tasks)
    app.lg.info('Submitted to dask.')

    if lf.AWAIT_DASK_RESULTS:
        results = lf.scheduler.monitor_progress(futures)
        app.lg.info("Dask returns:")
        for i, r in enumerate(results):
            app.lg.info(f"{i:>4}. [{r.get('status')}] {r.get('task_id')} ({r.get('type')}): {r.get('message')}")
