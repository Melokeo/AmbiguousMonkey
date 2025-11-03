import logging
import platform
import subprocess
from pathlib import Path
import flet as ft

from ...core.daet import DAET

from .. import landfill as lf
from ...core.finalize import one_stop_collect

DRPDN_BASE = 'Base'

class TabFinal:
    def __init__(self, logger: logging.Logger) -> None:
        self.lg = logger

        self.btn_collect = ft.ElevatedButton(
            text='Collect',
            on_click=self.on_collect_click,
        )

        daet_opts = self._get_daet_dropdown_items()
        self.dropdown_daets = ft.Dropdown(
            options=daet_opts,
        )
        self.dropdown_daets.value = DRPDN_BASE
        
        self.btn_refresh_daets = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip='Refresh DAETs',
            on_click=self.on_refresh_daets,
        )

        self.btn_open_sync_dir = ft.ElevatedButton(
            text='Sync',
            on_click=self.on_open_dir,
        )

        self.btn_open_dlc_dir = ft.ElevatedButton(
            text='DLC',
            on_click=self.on_open_dir,
        )

        self.btn_open_ani_dir = ft.ElevatedButton(
            text='Anipose',
            on_click=self.on_open_dir,
        )

        self.btn_open_clean_dir = ft.ElevatedButton(
            text='Clean',
            on_click=self.on_open_dir,
        )

        self.row_spirit_well = ft.Row(
            controls=[
                ft.Text('Spirit well'),
                self.dropdown_daets,
                self.btn_refresh_daets,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.row_btns = ft.Row(
            controls=[
                self.btn_open_sync_dir,
                self.btn_open_dlc_dir,
                self.btn_open_ani_dir,
                self.btn_open_clean_dir,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.col = ft.Column(
            controls=[
                self.btn_collect,
                ft.Divider(),
                self.row_spirit_well,
                self.row_btns,
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
        self.lg.debug('on_collect_click')
        collected = one_stop_collect(lf.note_filtered)
        if collected:
            self.lg.info(f'Collected from {", ".join(collected)}')
        else:
            self.lg.info('Nothing was collected.')
    
    def open_dir(self, path: str|Path) -> None:
        p = Path(path)
        if p.exists():
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{p}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", p])
            else:
                subprocess.Popen(["xdg-open", p])
        else:
            self.lg.error(f'Path does not exist: {p}')

    def _get_daet_dropdown_items(self) -> list[ft.dropdown.Option]:
        daets = [str(daet) for daet in lf.note_filtered.daets] if lf.note_filtered else []
        daets = [DRPDN_BASE] + daets
        return [ft.dropdown.Option(daet) for daet in daets]
    
    def on_open_dir(self, e: ft.ControlEvent):
        if lf.note_filtered is None:
            self.lg.error('No note is set')
            return
        
        dir_map = {
            'Sync': lf.note_filtered.sync_path,
            'Anipose': lf.note_filtered.getAniRoot(),
            'Clean': lf.note_filtered.getCleanDir(),
        }

        dir_name = e.control.text
        daet = self.dropdown_daets.value
        if not daet:
            raise ValueError('weird case, None from dropdown')
        if daet != DRPDN_BASE:
            daet = DAET.fromString(daet)
            if dir_name == 'Sync':
                dir_name = lf.note_filtered.getDaetSyncRoot(daet)
            elif dir_name == 'DLC':
                dir_name = lf.note_filtered.getDaetDlcRoot(daet)
            else:
                dir_name = dir_map.get(dir_name, None)
                if dir_name is None:
                    self.lg.error(f'Unknown dir name: {dir_name}')
                    return
        else:
            dir_name = dir_map.get(dir_name, None)
            if dir_name is None:
                self.lg.error(f'Unknown dir name: {dir_name}')
                return

        self.lg.debug(f'on_open_dir {dir_name}, {daet}')
        self.open_dir(dir_name)
    
    def on_refresh_daets(self, e: ft.ControlEvent):
        self.lg.debug('on_refresh_daets')
        self.dropdown_daets.options = self._get_daet_dropdown_items()
        self.dropdown_daets.value = DRPDN_BASE
        self.dropdown_daets.update()