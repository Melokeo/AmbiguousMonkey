import logging
from pathlib import Path
import flet as ft

from .. import landfill as lf
from ...core.camConfig import CamConfig, CamGroup
from ...core.sync import VidSynchronizer
from ..components.cam_config import ColCamCfgs

class TabSync:
    def __init__(self, logger: logging.Logger) -> None:
        self.lg = logger

        self.col_cams = ColCamCfgs(CamConfig())

        self.btn_check_all = ft.ElevatedButton(
            text='Check all ROIs',
            icon=ft.Icons.REMOVE_RED_EYE,
            on_click=self.on_check_all
        )

        self.btn_set_all = ft.ElevatedButton(
            text='Set all ROIs',
            icon=ft.Icons.CROP,
            on_click=self.on_set_all
        )

        self.btn_create_vs = ft.ElevatedButton(
            text='Create sync',
            icon=ft.Icons.UPCOMING,
            on_click=self.on_create_click
        )

        self.btn_sync_all = ft.ElevatedButton(
            text='Synchronize',
            icon=ft.Icons.SYNC,
            on_click=self.on_sync_all
        )

        self.pr = ft.ProgressRing(width=16, height=16, stroke_width=2, value=None)
        self.syncing_row = ft.Row([
            self.pr,
            ft.Text(value='Running synchronization'),
            ft.Icon(ft.Icons.COFFEE),
        ], ft.MainAxisAlignment.CENTER)
        self.syncing_row.visible = False

        self.col = ft.Column(
            controls=[
                self.col_cams,
                ft.Row([self.btn_create_vs], ft.MainAxisAlignment.CENTER),
                ft.Row([self.btn_check_all, self.btn_set_all], ft.MainAxisAlignment.CENTER),
                ft.Row([self.btn_sync_all], ft.MainAxisAlignment.CENTER),
                self.syncing_row,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        self.tab = ft.Tab(
            text='Vid sync',
            icon=ft.Icons.ALIGN_HORIZONTAL_RIGHT,
            content=ft.Container(content=self.col, 
                padding=ft.padding.only(top=16),),
        )
        
        self.lg.debug('tab_sync is up')
    
    def on_setup_click(self, e: ft.ControlEvent):
        self.lg.debug('on_setup_click')

    def on_check_all(self, e: ft.ControlEvent):
        self.lg.debug('on_check_all')

    def on_create_click(self, e: ft.ControlEvent):
        self.vs = VidSynchronizer(notes=lf.note_filtered)
        self.lg.debug(self.vs)

    def on_set_all(self, e: ft.ControlEvent):
        if not hasattr(self, 'vs'):
            self.lg.error('on_set_all: synchronizer not created')
            return
        self.vs.setROI()
        self.lg.debug(self.vs.cam_config.cams)
        self.lg.info('Updated ROIs')

    def on_sync_all(self, e: ft.ControlEvent):

        self.lg.debug('on_sync_all')
        self.lg.info('Starting sync all...')
        self.syncing_row.visible = True
        # self.tab.badge = ft.Badge(small_size=10),
        self.tab.icon = ft.Icons.FIRE_EXTINGUISHER
        self.btn_sync_all.disabled = True
        self.tab.update()

        if lf.USE_DASK:
            from ...dask.dask_scheduler import DaskScheduler
            from ammonkey.dask.dask_factory import create_sync_pipeline
            sched = lf.scheduler
            if not sched:
                self.lg.error('dask not connected')
                return
            tasks = create_sync_pipeline(
                note=self.vs.notes,
                rois=self.vs.cam_config.rois,
            )
            futs = sched.submit_tasks(tasks)
            result = sched.monitor_progress(futs)
        else:
            result = self.vs.syncAll()

        self.lg.debug(result)
        self.lg.info('Received sync result.')
        self.syncing_row.visible = False
        self.tab.icon = ft.Icons.ALIGN_HORIZONTAL_RIGHT
        self.btn_sync_all.disabled = False
        self.tab.update()

    def reset(self):
        pass

