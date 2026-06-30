import logging
from typing import Callable
import flet as ft

from .. import landfill as lf
from ..landfill import TabJob
from ..components.note_selector import ColNoteSelector
from ...core.fileOp import dataSetup

class TabSetup:
    def __init__(self, logger: logging.Logger, unlocker_func: Callable) -> None:
        self.lg = logger

        self.btn_setup = ft.ElevatedButton(
            text='Setup DATA folders',
            on_click=self.on_setup_click,
        )

        self.note_selector = ColNoteSelector(logger=logger, unlocker_func=unlocker_func)

        self.col = ft.Column(
            controls=[
                self.btn_setup,
                self.note_selector,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        self.tab = ft.Tab(
            text='Folder setup',
            icon=ft.Icons.FOLDER_COPY,
            content=ft.Container(
                content=self.col,
                # alignment=ft.alignment.center
                padding=ft.padding.only(top=16),
            ),
        )
        
        self.lg.debug('tab_setup is up')
    
    def on_setup_click(self, e: ft.ControlEvent):
        if lf.note is not None:
            dataSetup(raw_path=lf.note.path)
            self.lg.info(f'Setup ok {lf.note}')
        else:
            self.lg.error('ExpNote is not loaded!')

    def update_state_to(self, job: TabJob) -> None:
        job.selected_daets = set(self.note_selector.selected_daets)

    def render_state_from(self, job: TabJob) -> None:
        if not job.selected_daets:
            return
        self.lg.debug(f're-select: {job.selected_daets}')
        sel = self.note_selector
        sel.selected_daets = set(job.selected_daets) & set(sel.daet_checkboxes.keys())
        for daet, cb in sel.daet_checkboxes.items():
            is_sel = daet in sel.selected_daets
            cb.value = is_sel
            sel.daet_entries_map[daet].opacity = 1.0 if is_sel else 0.5
        sel._update_task_chip_visuals()
        sel.update()