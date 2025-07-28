import flet as ft
import logging

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

        self.btn_setup = ft.ElevatedButton(
            text='Setup DATA folders',
         
            # on_click=self.on_setup_click,
        )

        self.col = ft.Column(
            controls=[
                self.level_dropdown,
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