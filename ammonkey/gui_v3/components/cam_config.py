import logging
from pathlib import Path
import flet as ft

from ...core.camConfig import CamConfig, CamGroup, Camera
from ...core.camConfig import LedColor

class RowCamCfg(ft.Row):
    def __init__(self, camera: Camera, logger: logging.Logger):
        super().__init__()
        self.lg = logger
        self.cam = camera
        self.build()

    def build(self):
        self.chk = ft.Checkbox(
            label=str(self.cam.name),
            value=True,
        )
        self.color_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option('Y'),
                ft.dropdown.Option('G'),
            ],  # expand to match LedColor in the future
            value=self.cam.led_color.value if self.cam.led_color else '',
            on_change=self.on_led_change,
            width=80,
            padding=ft.padding.only(left=10, right=20),
            item_height=20,
        )
        self.roi_text = ft.Text(f'ROI {self.cam.roi}', size=10)

        self.btn_check = ft.ElevatedButton(
            text = 'Check ROI',
            icon=ft.Icons.REMOVE_RED_EYE,
            on_click=self.on_check_click,
        )
        self.btn_set_roi = ft.ElevatedButton(
            text = 'Set ROI',
            icon=ft.Icons.CROP,
            on_click=self.on_set_roi_click,
        )

        self.btn_check.disabled = True
        self.btn_set_roi.disabled = True

        self.controls = [
            self.chk, 
            # self.roi_text, 
            self.color_dropdown,
            ft.Row(
                controls=[self.btn_check, self.btn_set_roi],
                alignment=ft.MainAxisAlignment.END,
                expand=True,
            )
        ]
        # self.update()

    def on_check_click(self, e: ft.ControlEvent):
        self.lg.debug('on_check_click')

    def on_set_roi_click(self, e: ft.ControlEvent):
        self.lg.debug('on_set_roi_click')
    
    def on_led_change(self, e: ft.ControlEvent):
        self.lg.debug(f'on_led_change - {e.control.value}')
        self.cam.led_color = LedColor.from_char(e.control.value)

    def generate_container(self):
        return ft.Container(
            content=ft.Row(
                self.controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(vertical=2, horizontal=10),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=ft.border_radius.all(8),
            data=self.cam
        )
    

class ColCamCfgs(ft.Column):
    def __init__(self, cam_config: CamConfig, logger: logging.Logger|None=None):
        super().__init__()

        if not logger:
            self.lg = logging.getLogger(__name__)
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter('[GUI] %(name)s - %(levelname)s - %(message)s'))
            self.lg.addHandler(ch)
            self.lg.setLevel(logging.DEBUG)
        else:
            self.lg = logger
        
        if cam_config:
            self.cams = cam_config.cams
            self.cam_cfg = cam_config
        else:
            self.lg.error(cam_config)
            return

        self.rows: list[ft.Container] = []
        self.build()

    def build(self):
        self.rows.clear()
        '''elem_count = 0
        elem_per_row = 2
        ctrls = []
        row = []
        for cam in self.cams:
            if elem_count < elem_per_row:
                row.append(RowCamCfg(cam, self.lg).generate_container())
                elem_count += 1
            else:
                elem_count = 0
                ctrls.append(ft.Row(row))
                row.clear()
        if not row:
            ctrls.append(ft.Row(row))
                
        self.rows = ctrls'''
        self.rows = [RowCamCfg(cam, self.lg).generate_container() for cam in self.cams]
        self.controls = [ft.ListView(
            controls=self.rows,
            expand=True, 
            spacing=5,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            padding=ft.padding.only(right=10),
        )]

def main(pg: ft.Page):
    cam_cfg = CamConfig()
    pg.add(ColCamCfgs(cam_cfg))
    pg.update()

if __name__ == '__main__':
    ft.app(main)