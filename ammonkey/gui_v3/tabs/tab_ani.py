import flet as ft
import logging

from .. import landfill as lf
from ...core.dlcCollector import getUnprocessedDlcData
from ...core.ani import AniposeProcessor, runAnipose 
from ...core.finalize import violentCollect

class TabAnipose:
    def __init__(self, logger: logging.Logger) -> None:
        self.lg = logger
        self.ap: AniposeProcessor | None = None

        udd = self._get_dropdown_options()

        self.model_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(d)
                for d in udd
            ],
            on_change=self.on_model_change,
            label='Model unprocessed',
            width=250,
        )

        self.btn_model_refresh = ft.IconButton(
            icon=ft.Icons.REFRESH,
            on_click=self.on_model_refresh_click
        )

        self.btn_run_ani = ft.ElevatedButton(
            text='Run anipose',
            icon=ft.Icons.PLAY_CIRCLE,
            on_click=self.on_run_anipose_click
        )

        self.btn_collect = ft.ElevatedButton(
            text='Collect',
            on_click=self.on_collect_click,
        )

        self.pr = ft.ProgressRing(width=16, height=16, stroke_width=2, value=None)
        self.running_row = ft.Row([
            self.pr,
            ft.Text(value='Running Anipose... takes a while'),
            ft.Icon(ft.Icons.DINNER_DINING),
        ], ft.MainAxisAlignment.CENTER)
        self.running_row.visible = False

        self.ani_info = ft.Text(value='<anipose processor info>')

        self.col = ft.Column(
            controls=[
                ft.Row([
                        self.model_dropdown,
                        self.btn_model_refresh,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        self.ani_info,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        self.btn_run_ani,
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
            text='Anipose',
            icon=ft.Icons.THREED_ROTATION,
            content=ft.Container(
                content=self.col,
                # alignment=ft.alignment.center,
                padding=ft.padding.only(top=16),
            ),
        )
        
        self.lg.debug('tab_anipose is up')

    def on_model_change(self, e: ft.ControlEvent):
        pass
    
    def on_run_anipose_click(self, e: ft.ControlEvent):
        msn = self.model_dropdown.value
        self.lg.debug(f'run ani w/ {msn}')
        if msn is None:
            self.lg.error('Model set to process is not selected')
            return
        
        self.lg.info('Starting anipose...')
        self.running_row.visible = True
        self.btn_run_ani.disabled = True
        self.tab.update()
        try:
            self.ap = AniposeProcessor(lf.note_filtered, model_set_name=msn)
            self._update_ani_info()
            self.ap.setupRoot()
            self.ap.setupCalibs()

            self.lg.debug('-calibrateCLI-')
            self.ap.calibrateCLI()
            self.lg.debug('-calibrateCLI: done-')
            self._update_ani_info()

            self.ap.batchSetup()
            self.lg.debug('-Trangulate CLI-')
            self.ap.triangulateCLI()
            self.lg.info('Anipose terminated. Let\'s pray it\'s done.')
        finally:
            self.running_row.visible = False
            self.btn_run_ani.disabled= False
            self.tab.update()

    def on_model_refresh_click(self, e: ft.ControlEvent):
        self.lg.debug(f'on_model_refresh_click')
        udd = self._get_dropdown_options()
        self.model_dropdown.options.clear() #type:ignore
        self.model_dropdown.options = [ft.dropdown.Option(d) for d in udd]
        if udd:
            self.model_dropdown.value = udd[0]
        self.lg.debug(f'{e=}, {e.control=}, {self.tab=} ,{self.tab.parent=}, {self.tab.page=}')
        self.tab.update()

        if not ('* Nothing *' in udd and len(udd)==1):
            self.lg.debug(f'Found {len(udd)} datasets for anipose')
        else:
            self.lg.debug(f'Found nothing for anipose')

    def on_collect_click(self, e: ft.ControlEvent):
        self.lg.debug(f'on_collect_click')
        if self.ap is None:
            self.lg.error('Anipose Processor is None!')
            return
        violentCollect(self.ap.ani_root_path, lf.note_filtered.data_path / 'clean')

    def on_msn_change(self, e: ft.ControlEvent):
        #if e.control.value != '* Nothing *' and e.control.value:
        #    self.ap = AniposeProcessor(lf.note_filtered, e.control.value)
        ...

    def _update_ani_info(self):
        self.lg.debug(self.ap)
        if self.ap is None:
            return
        self.ani_info.value = self.ap.info
        self.tab.update()

    def _get_dropdown_options(self) -> list[str]:
        if lf.note_filtered:
            udd: list[str] | None = getUnprocessedDlcData(lf.note_filtered.data_path) 
        else:
            udd = None 
        if udd is None:
            udd = ['* Nothing *']
        return udd
