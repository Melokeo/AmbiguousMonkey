import flet as ft
import logging

from .. import landfill as lf
from ...core.dlcCollector import getUnprocessedDlcData
from ...core.ani import AniposeProcessor, runAnipose 
from ...core.finalize import violentCollect
from ...core.statusChecker import StatusChecker

NOTHING = '* Nothing *'

class TabAnipose:
    def __init__(self, logger: logging.Logger) -> None:
        self.lg = logger
        self.ap: AniposeProcessor | None = None

        udd = self._get_dropdown_options()
        vid_udd = self._get_vid_dropdown_options()

        self.model_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(d)
                for d in udd
            ],
            on_change=self.on_model_change,
            label='Model unprocessed',
            width=280,
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

        self.vid_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(d)
                for d in vid_udd
            ],
            on_change=self.on_vid_msn_change,
            label='Model set w/o vids',
            width=280,
        )

        self.btn_vid_refresh = ft.IconButton(
            icon=ft.Icons.REFRESH,
            on_click=self.on_vid_refresh_click
        )

        self.rng_video = ft.RangeSlider(
            min=0,
            max=100,
            start_value=30,
            divisions=20,
            end_value=60,
            label='{value}',
            width=660,
        )

        self.btn_make_vid = ft.ElevatedButton(
            text='Make videos',
            icon=ft.Icons.VIDEOCAM,
            on_click=self.on_make_vid_click,
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

                ft.Divider(),
                ft.Row(
                    [
                        self.vid_dropdown,
                        self.btn_vid_refresh,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        self.rng_video,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        self.btn_make_vid,
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
        if msn is None or msn == NOTHING:
            self.lg.error('Model set to process is not selected')
            return
        
        self.lg.info('Starting anipose...')
        self._ui_processing_stat(True)

        #TODO this logic could be refactored
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

            # self.ap.makeVideos()
        finally:
            self._ui_processing_stat(False)

    def on_model_refresh_click(self, e: ft.ControlEvent):
        self.lg.debug(f'on_model_refresh_click')
        udd = self._get_dropdown_options()
        self.model_dropdown.options.clear() #type:ignore
        self.model_dropdown.options = [ft.dropdown.Option(d) for d in udd]
        if udd:
            self.model_dropdown.value = udd[0]
        # self.lg.debug(f'{e=}, {e.control=}, {self.tab=} ,{self.tab.parent=}, {self.tab.page=}')
        self.tab.update()

        if not (NOTHING in udd and len(udd)==1):
            self.lg.debug(f'Found {len(udd)} datasets for anipose')
        else:
            self.lg.debug(f'Found nothing for anipose')

    def on_vid_refresh_click(self, e: ft.ControlEvent):
        self.lg.debug(f'on_vid_refresh_click')
        vid_udd = self._get_vid_dropdown_options()
        self.vid_dropdown.options.clear() #type:ignore
        self.vid_dropdown.options = [ft.dropdown.Option(d) for d in vid_udd]
        if vid_udd:
            self.vid_dropdown.value = vid_udd[0]
        self.tab.update()

        if not (NOTHING in vid_udd and len(vid_udd)==1):
            self.lg.debug(f'Found {len(vid_udd)} datasets for anipose video')
        else:
            self.lg.debug(f'Found nothing for anipose video')

    def on_collect_click(self, e: ft.ControlEvent):
        self.lg.debug(f'on_collect_click')
        if self.ap is None:
            self.lg.error('Anipose Processor is None!')
            return
        violentCollect(self.ap.ani_root_path, lf.note_filtered.data_path / 'clean')

    def on_make_vid_click(self, e: ft.ControlEvent):
        self.lg.debug(f'on_make_vid_click')
        msn = self.vid_dropdown.value
        if msn is None or msn == NOTHING:
            self.lg.error('Model set to make videos is not selected')
            return

        self._ui_processing_stat(True)

        if self.ap is None:
            self.ap = AniposeProcessor(lf.note_filtered, model_set_name=msn)
            self._update_ani_info()

        start = int(self.rng_video.start_value) / 100
        end = int(self.rng_video.end_value) / 100
        self.lg.debug(f'Start making videos for {msn} with range {start:.2f} - {end:.2f}')

        try:
            self.lg.info('Copying videos to anipose dir')
            self.ap.copy_videos_all_daets()
            
            self.lg.info('Making videos with Anipose...')
            self.ap.makeVideos(start=start, end=end)
        except OSError as oe:
            self.lg.error(f'Perhaps copy videos failed: {oe}')
        except RuntimeError as re:
            self.lg.error(f'Anipose make videos failed: {re}')
        except Exception as ee:
            self.lg.error(f'Unexpected error during make videos: {ee}')
        else:
            self.lg.info('Make videos done')

        self._ui_processing_stat(False)

    def on_msn_change(self, e: ft.ControlEvent):
        #if e.control.value != '* Nothing *' and e.control.value:
        #    self.ap = AniposeProcessor(lf.note_filtered, e.control.value)
        ...
    def on_vid_msn_change(self, e: ft.ControlEvent):
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
            udd = [NOTHING]
        return udd
    
    def _ui_processing_stat(self, processing:bool) -> None:
        self.running_row.visible = processing
        self.btn_run_ani.disabled = processing
        self.btn_make_vid.disabled = processing
        self.tab.update()


#TODO: if a model set is triangulated but videos not made, it won't appear in the dropdown.
# should be fixed.

    def _get_vid_dropdown_options(self) -> list[str]:
        if lf.note_filtered:
            sc = StatusChecker(lf.note_filtered)
            process_stats = sc.check_ani_vid_combined_simple_all_ms()
            self.lg.debug(f'{process_stats=}')

            #TODO include label-3d in the future
            udd = [ms for ms, stat in process_stats.items() if not stat]
        else:
            udd = None 
        if udd is None:
            udd = [NOTHING]
        return udd