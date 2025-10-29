import flet as ft
import logging

from .. import landfill as lf
from ...core.statusChecker import full_check

class TabSetting:
    def __init__(self, logger: logging.Logger) -> None:
        self.lg = logger

        levels = ['debug', 'info', 'warning', 'error']
        self.level_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(l) for l in levels],
            on_change=self.on_level_change,
            label='Logging level',
            width=250,
        ) 

        self.switch_dask = ft.Switch(
            label='Use dask-centered flow',
            value=lf.USE_DASK,
            on_change=self.on_dask_change,
        )

        self.edt_dask_addr = ft.TextField(
            label="Server address <IP:port>",
            value='127.0.0.1:8786',
            hint_text="127.0.0.1:8786",
            width=300,
            input_filter=ft.InputFilter(
                regex_string=r"^[0-9.:]*$",
                allow=True,
                replacement_string=""
            )
        )

        self.btn_connect = ft.ElevatedButton(
            text='Connect dask',
            icon=ft.Icons.CONNECTED_TV,
            on_click=self.on_btn_connect,
        )

        self.lbl_connect_stat = ft.Text('Just initialized')

        self.dask_svr_row = ft.Row(
            controls=[
                self.btn_connect,
                self.lbl_connect_stat,
            ]
        )

        self.btn_full_check = ft.ElevatedButton(
            text='Full check proc stat',
            icon=ft.Icons.EXPAND_MORE,
            on_click=self.on_full_chk_click,
        )

        self.col = ft.Column(
            controls=[
                self.level_dropdown,
                self.switch_dask,
                self.edt_dask_addr,
                self.dask_svr_row,
                self.btn_full_check,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        self.tab = ft.Tab(
            text='Settings',
            icon=ft.Icons.SETTINGS,
            content=ft.Container(
                content=self.col,
                # alignment=ft.alignment.center
                padding=ft.padding.only(top=16),
            ),
        )
        
        self.lg.debug('tab_setup is up')
    
    def on_level_change(self, e: ft.ControlEvent):
        '''changes log level'''
        lvl = self.level_dropdown.value
        if lvl == 'debug':
            self.lg.setLevel(logging.DEBUG)
        elif lvl == 'info':
            self.lg.setLevel(logging.INFO)
        elif lvl == 'warning':
            self.lg.setLevel(logging.WARNING)
        elif lvl == 'error':
            self.lg.setLevel(logging.ERROR)
        self.lg.info(f'Set logging level {lvl}')
    
    def on_dask_change(self, e):
        if self.switch_dask.value:
            try:
                import dask
            except ModuleNotFoundError as e:
                self.lg.error('Dask is not available')
                self.switch_dask.value = False
        
        lf.USE_DASK = self.switch_dask.value

    def on_btn_connect(self, e):
        if not self.switch_dask.value:
            self.lg.info('You didn\'t enable dask above')
            return
        
        self.lg.debug('on_btn_connect')
        
        try:
            from ...dask.dask_scheduler import DaskScheduler
            svr_addr = self.edt_dask_addr.value
            if lf.scheduler:
                self.lg.debug('Closing prev client')
                lf.scheduler.client.close()
            self.lg.debug('Trying connection...')  
            lf.scheduler = DaskScheduler(scheduler_address=f'tcp://{svr_addr}')
            self.lg.info(f'Successfully connected to dask server {svr_addr}')
            self.lbl_connect_stat.value=f'Connected({svr_addr})'
        except (ImportError, ModuleNotFoundError) as e:
            self.lg.error(f'failed to load dask module: {e}')
        except TimeoutError as e:
            self.lg.error(f'Timeout reached while trying to connect server: {e}')
    
    def on_full_chk_click(self, e):
        if not lf.note_filtered:
            return
        self.lg.debug('on_btn_full_check')
        results = full_check(lf.note_filtered)
        for r in results:
            print(r)
        self.lg.info('stat check finished. plz check command line for details')