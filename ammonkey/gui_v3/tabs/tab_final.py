import logging
import flet as ft

from .. import landfill as lf
from ...core.finalize import violentCollect

class TabFinal:
    def __init__(self, logger: logging.Logger) -> None:
        self.lg = logger

        self.btn_collect = ft.ElevatedButton(
            text='Collect',
            on_click=self.on_collect_click,
        )

        self.col = ft.Column(
            controls=[
                self.btn_collect,
                
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        self.tab = ft.Tab(
            text='Finalize',
            icon=ft.Icons.CLEANING_SERVICES,
            content=ft.Container(
                content=self.col,
                # alignment=ft.alignment.center,
                padding=ft.padding.only(top=16),
            ),
        )
        
        self.lg.debug('tab_finalize is up')
    
    def on_collect_click(self, e: ft.ControlEvent):
        # violentCollect(lf.note_filtered, lf.note.data_path/'clean')        
        ...