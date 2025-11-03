import flet as ft
import logging
from pathlib import Path

from ..core.expNote import get_xlsx_dates, iter_xlsx, ExpNote, DAET
from ..core.config import Config

from . import landfill as lf
from .components.flet_logging import FletLogHandler, ColorLoggingFormatter
from .tabs.tab_setup import TabSetup
from .tabs.tab_sync import TabSync
from .tabs.tab_dlc import TabDlc
from .tabs.tab_ani import TabAnipose
from .tabs.tab_final import TabFinal
from .tabs.tab_setting import TabSetting

class AmmApp:
    def __init__(self) -> None:
        self.base_raw_root = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025' 
        self.mono_font = 'Consolas'

    def __call__(self, pg: ft.Page) -> None:
        self.pg = pg
        pg.theme = ft.Theme(
            color_scheme_seed=ft.Colors.ORANGE,
            font_family=self.mono_font
        )
        pg.window.height = 820
        pg.window.width = 720
        pg.window.icon = str(Path(__file__).parent / 'ambmky.ico')
        pg.title = 'Ambiguous Monkey V3.3.0'
        # pg.scroll = ft.ScrollMode.ADAPTIVE

        # logging area
        self.log_area = ft.Text(
            spans=[],
            font_family=self.mono_font,
            size=12,
            overflow=ft.TextOverflow.FADE,
            expand=True,
            selectable=True,
        )

        self.create_logger()
        self.setup_layout()
        self.connect_loggers()
        self.update_notes_dropdown()

    def create_logger(self) -> None:
        self.lg = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('[GUI] %(name)s - %(levelname)s - %(message)s'))
        self.lg.addHandler(ch)
        self.lg.setLevel(logging.DEBUG)

    def setup_layout(self) -> None:
        self.dropdown_animal = ft.Dropdown(
            options=[ft.dropdown.Option(a) for a in Config.animals],
            on_change=self.on_animal_dropdown_change,
            dense=True,
            enable_search=True,
            label='Animal',
            padding=ft.padding.only(left=10, right=20),
        )
        self.dropdown_notes = ft.Dropdown(
            options=[ft.dropdown.Option('* not initialized *')],
            on_change=self.on_dropdown_change,
            dense=True,
            enable_search=True,
            label='ExpNote',
            padding=ft.padding.only(left=10, right=20),
            width=180,
        )

        self.btn_scan = ft.IconButton(
            # text='Scan',
            icon=ft.Icons.SEARCH
        )

        self.btn_run_all = ft.IconButton(
            # text='Scan',
            icon=ft.Icons.PLAY_ARROW,
            on_click=self.on_run_all,
        )

        self.curr_note = ft.Text(
            'No note loaded',
            
        )

        self.curr_note_container = ft.Row(
            [ft.Container(
                self.curr_note, 
                border=ft.border.all(1, ft.Colors.ORANGE_200), 
                border_radius=5, 
                padding=ft.padding.only(left=10,right=10))
            ], 
            alignment=ft.MainAxisAlignment.END,
            expand=True,
        )

        self.tabs_list: list[ft.Tab] = []

        self.tab_setup   = TabSetup(logger=self.lg, unlocker_func=self.unlock_tabs)
        self.tab_sync    = TabSync(logger=self.lg)
        self.tab_dlc     = TabDlc(logger=self.lg)
        self.tab_ani     = TabAnipose(logger=self.lg)
        self.tab_final   = TabFinal(logger=self.lg)
        self.tab_setting = TabSetting(logger=self.lg)

        self.tabs_list.extend([self.tab_setup.tab, self.tab_sync.tab, self.tab_dlc.tab, 
                              self.tab_ani.tab, self.tab_final.tab, self.tab_setting.tab])

        self.tabs = ft.Tabs(
            tabs=self.tabs_list,
            selected_index=0,
            scrollable=True,
            on_change=self.on_tab_change,
        )

        self.log_wrapper = ft.Column(
            controls=[self.log_area],
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            expand=1,
            spacing=10,
        )

        main_content = ft.Column(
            controls=[
                ft.Row([self.dropdown_animal, self.dropdown_notes, self.btn_scan, self.btn_run_all, self.curr_note_container]),
                ft.Container(
                    content=self.tabs,
                    expand=False,
                    height=480,
                ),
                ft.Container(
                    content=self.log_wrapper,
                    # height=200,  
                    # border=ft.border.all(1, ft.Colors.OUTLINE),
                    expand=True,
                )
            ],
            expand=True,
            spacing=10,
        )

        self.pg.add(main_content)

        self.lg.info('Finished UI init')

    def connect_loggers(self) -> None:
        flet_handler = FletLogHandler(self.log_area)
        flet_handler.setFormatter(ColorLoggingFormatter(width=100))

        if __name__.startswith('ammonkey'):
            self.lg.handlers.clear()
        else:
            amm_logger = logging.getLogger('ammonkey')
            amm_logger.addHandler(flet_handler)
            amm_logger.setLevel(logging.DEBUG)

        self.lg.addHandler(flet_handler)
        self.lg.setLevel(logging.DEBUG) 

        self.lg.info('Finished UI init')

    def update_notes_dropdown(self) -> None:
        notes_paths = list(iter_xlsx(str(self.base_raw_root)))
        notes_dates = get_xlsx_dates(str(self.base_raw_root))        # redundant!!!
        self.lg.debug(f'Acquired {len(notes_paths)=}, {len(notes_dates)=}')

        self.dropdown_notes.options = [
            ft.dropdown.Option(text=d, key=p)
            for d, p in zip(notes_dates, notes_paths)
        ]
        self.pg.update()

    def on_animal_dropdown_change(self, e:ft.ControlEvent) -> None:
        new_animal = self.dropdown_animal.value
        if not new_animal:
            self.lg.debug('dropdown animal None.')
            return
        new_path = Config.animal_paths.get(new_animal, None)
        if not new_path:
            raise ValueError(f'{new_animal} isn\'t registered with a path in amm-config')
        
        self.base_raw_root = new_path
        self.dropdown_notes.value = None
        self.update_notes_dropdown()

        self.lg.info(f'Changed animal to {new_animal}')
    
    def on_dropdown_change(self, e:ft.ControlEvent) -> None:
        dropdown: ft.dropdown.Dropdown = e.control
        sel_path: str = dropdown.value #type:ignore
        self.lg.debug(sel_path)
        sel_text = next(
            (o.text for o in dropdown.options if o.key == sel_path), #type:ignore
            sel_path  # fallback to key if not found
        )

        self.lg.info(f'Reading ExpNote from {sel_text}')
        try:
            n = ExpNote(Path(sel_path))
            lf.note = n
            lf.note_filtered = ExpNote(Path(sel_path))  # careful about pointer
        except FileNotFoundError as fnf:
            self.lg.error(f'Failed to load {sel_path}. This is rare. {fnf}')
            return
        except Exception as ex:
            self.lg.error(f'Unknown exception when loading {sel_text}: {ex}')
            return
        else:
            self.lg.info(f"Selected {n}")

        # update ui
        try:
            self.tab_setup.note_selector.refresh_note()
            self.update_current_note_display()
        except ValueError as ve:
            self.lg.error(f'Updating DAET UI failed: {ve}')
            return
        except Exception as ex:
            self.lg.error(f'Updating DAET UI failed: {ex}')
            return
        
        if self.tabs.selected_index == 0: # opened folder setup tab
            for tab in self.tabs_list[1:]:
                tab.disabled = True
                # self.lg.debug(f'{tab.icon}, {tab.disabled=}')
            self.pg.update()

        return
    
    def unlock_tabs(self):
        '''
        unlock other tabs and go to sync, after confirming daet entries.
        Called when 'confirm selection' is clicked
        '''
        for tab in self.tabs_list:
            tab.disabled = False
        self.tabs.selected_index = 1
        self.update_current_note_display()
        self.pg.update()
    
    def update_current_note_display(self):
        filtered = not (len(lf.note.daets) == len(lf.note_filtered.daets))
        if lf.note_filtered:
            self.curr_note.value = f'Current: {str(lf.note_filtered)[16:].split(" with")[0]} {"F" if filtered else ""}' 
        else:
            self.curr_note.value = ('No note loaded')
        self.pg.update()

    def on_tab_change(self, e:ft.ControlEvent):
        if self.tabs.selected_index != 0:
            if not lf.note and self.tabs.selected_index != 5:
                self.lg.warning(f'Note is not set')
                self.tabs.selected_index = 0
                self.pg.update()
            if self.dropdown_notes.value and not lf.note_filtered.date in self.dropdown_notes.value:
                self.lg.warning(f'Displayed note doesnt match processing data {lf.note_filtered.date} != {self.dropdown_notes.value}')
        if self.tabs.selected_index == 3:    # anipose
            self.tab_ani.on_model_refresh_click(e)
            self.tab_ani.on_vid_refresh_click(e)
    
    def on_run_all(self, e):
        if lf.USE_DASK:
            self.lg.debug('dask full ppl')
            try:
                from ..dask.dask_factory import create_full_pipeline
            except ImportError as e:
                self.lg.error('Failed to import dask')
                return
            if not lf.note:
                self.lg.error('No note is set')
                return
            if not lf.scheduler:
                self.lg.error('Scheduler is not connected')
                return
            
            if not self.tab_sync.vs:
                self.lg.error('on_run_all: vid synchronizer instance not created')
                return
            model = self.tab_dlc.model_dropdown.value
            if model:
                self.lg.debug(f'on_run_all: {lf.note_filtered=}, {model=}')
            else:
                self.lg.error('on_run_all: dlc model not selected')
                return
            
            tasks = create_full_pipeline(
                note=lf.note_filtered,
                processor_type=model,
                rois=self.tab_sync.vs.cam_config.rois
            )

            futures = lf.scheduler.submit_tasks(tasks)
            self.lg.info('Submitted to dask.')

            if lf.AWAIT_DASK_RESULTS:
                results = lf.scheduler.monitor_progress(futures)
                self.lg.info("Dask returns:")
                for i, r in enumerate(results):
                    self.lg.info(f"{i:>4}. [{r.get('status')}] {r.get('task_id')} ({r.get('type')}): {r.get('message')}")
        
        else:
            self.lg.debug('local full ppl (not implemented)')

if __name__ == '__main__':
   ft.app(AmmApp())