import logging
import flet as ft
import asyncio


from .. import landfill as lf
from ..landfill import TabJob, JobStatus
from ...core.dlc import available_dp, dp_factory, initDlc, dp_task
from ...core.expNote import Task
from ..business.async_workers import _run_dlc_local, _run_dlc_dask

class TabDlc:
    def __init__(self, logger: logging.Logger) -> None:
        self.lg = logger

        self.model_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(dp)
                for dp in available_dp
            ],
            on_change=self.on_model_change,
            label = 'Model',
        )

        self.btn_init = ft.ElevatedButton(
            text='Initialize DLC',
            icon=ft.Icons.ENGINEERING,
            on_click=self.on_init_click
        )

        self.btn_run_dlc = ft.ElevatedButton(
            text='!RUN DLC!',
            icon=ft.Icons.PLAY_CIRCLE,
            on_click=self.on_run_dlc_click_jobbed,
        )

        self.pr = ft.ProgressRing(width=16, height=16, stroke_width=2, value=None)
        self.running_row = ft.Row([
            self.pr,
            ft.Text(value='Running DeepLabCut... ETA one century'),
            ft.Icon(ft.Icons.HOT_TUB),
            ft.Icon(ft.Icons.NIGHTLIFE),
        ], ft.MainAxisAlignment.CENTER)
        self.running_row.visible = False

        self.col = ft.Column(
            controls=[
                self.model_dropdown,
                ft.Row(
                    [
                        # self.btn_init, 
                        self.btn_run_dlc
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                self.running_row,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        self.tab = ft.Tab(
            text='DeepLabCut',
            icon=ft.Icons.MEMORY,
            content=ft.Container(
                content=self.col,
                # alignment=ft.alignment.center,
                padding=ft.padding.only(top=16),
            ),
        )
        
        self.lg.debug('tab_dlc is up')
    
    def on_init_click(self, e: ft.ControlEvent):
        if self.dp_func is None:
            self.lg.error('No model selected!')
            return
        self.lg.info('Loading DLC...')
        if initDlc():
            self.lg.info('Loaded DLC')
        else:
            self.lg.error('DLC load failed!')

    def on_model_change(self, e: ft.ControlEvent):
        dp: str = e.control.value
        self.lg.debug(f'on_model_change {dp}')
        self.dp_func = dp_factory.get(dp, None)
        if self.dp_func is None:
            self.lg.error(f'on_model_change {e} get None dp')
            return
        
        if not self.check_model_compatibility(dp_name=dp):
            self.lg.warning(f'Model {dp} is not intended for this data, or multiple task types are included. plz confirm selection')

        self.lg.info(f'Updated dlc processor {dp}')

    def check_model_compatibility(self, dp_name) -> bool:
        note_tasks = set(lf.note_filtered.getAllTaskTypes())
        note_tasks.discard(Task.CALIB)
        target_task = dp_task.get(dp_name, None)
        
        self.lg.debug(f'{note_tasks=}, {target_task=}')
        if target_task is None:
            raise ValueError(f'check_model_compatibility: {dp_name} is not valid to check')
            
        if isinstance(target_task, list):
            target_task_set = set(target_task)
            return note_tasks.issubset(target_task_set)
        else:
            return note_tasks == {target_task}
        
    async def on_run_dlc_click_jobbed(self, e: ft.ControlEvent):
        job = lf.curr_job
        if job is None:
            return
        if job.is_running:
            self.lg.warning('task already running for this note')
            return

        model = self.model_dropdown.value
        if not model:
            self.lg.error('no model selected')
            return

        job.selected_set = model
        if lf.USE_DASK:
            job.task = asyncio.create_task(_run_dlc_dask(job))
        else:
            job.task = asyncio.create_task(_run_dlc_local(job))
        
    def on_run_dlc_click(self, e: ft.ControlEvent):
        self.lg.debug(f'on_run_dlc_click {e}')
        self._ui_processing_stat(True)

        try:
            if not hasattr(self, 'dp_func') or self.dp_func is None:    # valid model selected
                self.lg.error(f'on_run_dlc_click {e} get None dp')
                return

            if lf.USE_DASK:     # dask controlled dlc
                from ...dask.dask_factory import create_dlc_tasks
                if not lf.scheduler:
                    self.lg.error('dask unset')
                    return
                model = self.model_dropdown.value
                if model:
                    self.lg.debug(f'create_dlc_tasks (dask): {lf.note_filtered=}, {model=}')
                else:
                    return
                tasks = create_dlc_tasks(
                    note=lf.note_filtered,
                    processor_type=model,
                )
                futures = lf.scheduler.submit_tasks(tasks)
                self.lg.info('Submitted to dask.')

                if lf.AWAIT_DASK_RESULTS:
                    results = lf.scheduler.monitor_progress(futures)
                    self.lg.info("Dask finished:")
                    for i, r in enumerate(results):
                        self.lg.info(f"{i:>4}. [{r.get('status')}] {r.get('task_id')} ({r.get('type')}): {r.get('message')}")

            else:   # in-app dlc
                self.on_init_click(e)
                self.dp = self.dp_func(lf.note_filtered)
                self.dp.batchProcess()
                self.lg.info(f'Congrats! DLC finished (perhaps)')

        finally:
            self._ui_processing_stat(False)

    def _ui_processing_stat(self, processing: bool) -> None:
        self.lg.debug(f'switching dlc processing stat: {processing}')
        self.running_row.visible = processing
        self.btn_run_dlc.disabled = processing
        if processing:
            self.tab.icon = ft.Icons.FIRE_EXTINGUISHER
        else:
            self.tab.icon = ft.Icons.MEMORY
        self.tab.update()

    def update_state_to(self, job: TabJob) -> None:
        job.selected_set = self.model_dropdown.value

    def render_state_from(self, job: TabJob) -> None:
        self.model_dropdown.value = job.selected_set
        self.dp = job.dp
        self._ui_processing_stat(job.dlc_processing)