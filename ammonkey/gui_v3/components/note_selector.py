
from typing import Callable
import logging
import flet as ft

from .. import landfill as lf
from ...core.expNote import ExpNote, DAET, Task
from ...core.statusChecker import StatusChecker

class ColNoteSelector(ft.Column):
    '''
    The panel that displays entries from ExpNote, with file status indicators
    '''
    def __init__(self, 
                 logger: logging.Logger|None = None, 
                 unlocker_func: Callable|None = None):
        super().__init__()

        if not logger:
            self.lg = logging.getLogger(__name__)
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter('[GUI] %(name)s - %(levelname)s - %(message)s'))
            self.lg.addHandler(ch)
            self.lg.setLevel(logging.DEBUG)
        else:
            self.lg = logger

        self.expand = True
        # self.scroll = ft.ScrollMode.AUTO
        self.task_chips_map: dict[Task, ft.Chip] = {}
        self.daet_checkboxes: dict[DAET, ft.Checkbox] = {}
        self.daet_entries_map: dict[DAET, ft.Container] = {}
        self.unlock = unlocker_func
        
        if lf.note is not None:
            self.assemble()
        else:
            self.controls = [ft.Text('Note is None.')]

    def assemble(self) -> None:
        self.selected_daets: set[DAET] = set(lf.note.daets)
        self.stat_checker = StatusChecker(lf.note)

        # self.task_chips_map
        self._init_task_chips()
        # self.daet_checkboxes, self.daet_entries_map
        self._init_daet_list()

        self.lock_switch = ft.Switch(label="Lock Selections", on_change=self.on_lock_change)

        self.confirm_button = ft.ElevatedButton(
            text="Confirm Selection",
            icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
            on_click=self.on_confirm_sel,
            expand=True
        )

        # --- assemble ---
        self.controls = [
            ft.Row(
                [
                    ft.Text("Filter by Task:", weight=ft.FontWeight.BOLD),
                    *self.task_chips_map.values()
                ],
                wrap=True, spacing=10, run_spacing=5
            ),
            ft.Divider(),
            ft.Text("Select DAETs for Processing:", weight=ft.FontWeight.BOLD),
            ft.ListView(
                controls=list(self.daet_entries_map.values()), 
                expand=True, 
                spacing=5,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                padding=ft.padding.only(right=10),
            ),
            ft.Divider(),
            ft.Row([self.confirm_button, self.lock_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ]

    def clear_daets(self) -> None:
        self.controls.clear()
        self.task_chips_map.clear()
        self.daet_checkboxes.clear()
        self.daet_entries_map.clear()
    
    def refresh_note(self) -> None:
        if lf.note is None:
            raise ValueError('selector refresh_note: ExpNote is None.')
            return
        self.clear_daets()
        # show a spinner for waiting
        self.controls = [ft.ProgressRing()]
        self.update()
        self.assemble()
        self.lg.info(f'Refreshed {lf.note}')
        self.update()

    def _init_task_chips(self) -> None:
        self.task_chips_map: dict[Task, ft.Chip] = {
            task_chip: ft.Chip(
                label=ft.Text(task_chip.name),
                selected=True,
                on_select=self.on_task_chip_select,
                data=task_chip,
            ) for task_chip in lf.note.getAllTaskTypes()
        }
    
    def _init_daet_list(self) -> None:
        self.daet_checkboxes = {
            daet: ft.Checkbox(
                value=True,
                on_change=self.on_daet_chk_change,
                data=daet,
            ) for daet in lf.note.daets
        }

        self.daet_entries_map = {
            daet: self._create_daet_entry(daet) for daet in lf.note.daets
        }

    def _create_daet_entry(self, daet) -> ft.Container:
        '''create single daet's Container(Row(chk, ...))'''
        video_paths = lf.note.getVidSetPaths(daet)
        checkbox = self.daet_checkboxes[daet]

        # video file physical stat indicators
        video_indicators = []
        for i, path in enumerate(video_paths):
            has_path = path is not None
            if has_path:
                if path.exists():
                    tooltip_message = f"Cam {i+1}: {path.name}"
                    name = ft.Icons.CHECK_CIRCLE
                    color = ft.Colors.GREEN_400
                else:
                    tooltip_message = f"Cam {i+1}: {path.name} file not found"
                    name = ft.Icons.WARNING
                    color = ft.Colors.YELLOW_400
            else:
                tooltip_message = f"Cam {i+1}: Has no/invalid file name"
                name = ft.Icons.CANCEL_OUTLINED
                color = ft.Colors.RED_400

            video_indicators.append(
                ft.Icon(
                    name=name,
                    color=color,
                    size=18,
                    tooltip=tooltip_message
                )
            )
        
        # daet processing stat indicators
        stat_indicators = []
        # sync stat
        sync_stat, sync_text = self.stat_checker.check_sync_single_daet(daet)
        if sync_stat:
            sync_icon = ft.Icon(
                name=ft.Icons.ALIGN_HORIZONTAL_RIGHT, 
                size=18,
                tooltip="Synced",
            )
            stat_indicators.append(sync_icon)
        # DLC stat
        dlc_stat, dlc_text = self.stat_checker.check_dlc_single_daet(daet)
        if dlc_stat:
            dlc_icon = ft.Icon(
                name=ft.Icons.MEMORY, 
                size=18,
                tooltip=dlc_text,
            )
            stat_indicators.append(dlc_icon)
        # Anipose stat
        ani_stat, ani_text = self.stat_checker.check_ani_single_daet(daet)
        if ani_stat:
            ani_icon = ft.Icon(
                name=ft.Icons.THREED_ROTATION, 
                size=18,
                tooltip=ani_text,
            )
            stat_indicators.append(ani_icon)

        indicators = ft.Row(
            spacing=5, alignment=ft.MainAxisAlignment.END,
            controls=stat_indicators + video_indicators
        )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Row([checkbox, ft.Text(str(daet))]),
                    indicators,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(vertical=2, horizontal=10),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=ft.border_radius.all(8),
            data=daet
        )
    
    def on_task_chip_select(self, e: ft.ControlEvent) -> None:
        '''sel/deselect daets according to task'''
        task_chip: ft.Chip = e.control
        task: Task = task_chip.data #type:ignore
        daets_for_task = lf.note.daets_by_task.get(task, [])

        for daet in daets_for_task:
            checkbox = self.daet_checkboxes[daet]
            container = self.daet_entries_map[daet]
            
            if task_chip.selected:
                checkbox.value = True
                self.selected_daets.add(daet)
                container.opacity = 1.0 
            else:
                checkbox.value = False
                self.selected_daets.discard(daet)
                container.opacity = 0.5 # grey out by opacity

        self._update_task_chip_visuals()
        self.update()

    def _update_task_chip_visuals(self):
        """Set the visual state of task chips (off, on, half)"""
        for task, chip in self.task_chips_map.items():
            daets_for_task = lf.note.daets_by_task.get(task, [])
            if not daets_for_task:
                continue

            selected_count = sum(1 for d in daets_for_task if d in self.selected_daets)

            if selected_count == 0: # Unselected
                chip.selected = False
                chip.opacity = 0.3
            elif selected_count < len(daets_for_task): # Half-selected
                chip.selected = True
                chip.opacity = 0.5
            else: # Fully selected
                chip.selected = True
                chip.opacity = 1.0
    
    def on_lock_change(self, e: ft.ControlEvent):
        is_locked: bool = e.control.value
        self._toggle_lock(is_locked)

    def _toggle_lock(self, is_locked: bool) -> None:
        for chip in self.task_chips_map.values():
            chip.disabled = is_locked
        for checkbox in self.daet_checkboxes.values():
            checkbox.disabled = is_locked
        self.update()
    
    def on_confirm_sel(self, e: ft.ControlEvent):
        selection = sorted(list(self.selected_daets), key=lambda d: str(d))
        self.lg.debug(selection)

        lf.note_filtered = lf.note.dupWithWhiteList(selection)
        self.lg.info(f'Filtered -> {lf.note_filtered}')
        self.lg.debug(f'{lf.note_filtered.daets=}')

        self.lock_switch.value = True
        self._toggle_lock(True)

        # unlock other tabs
        if not self.unlock is None:
            self.lg.debug('calling unlock()')
            self.unlock()

        self.update()

    def on_daet_chk_change(self, e: ft.ControlEvent):
        """When a DAET is checked/unchecked, update its state and the parent task chip."""
        checkbox: ft.Checkbox = e.control
        daet = checkbox.data
        if not isinstance(daet, DAET):
            self.lg.error(f'on_daet_chk_change: passed wrong daet internally, {type(daet)=}')
            return

        container = self.daet_entries_map.get(daet, None)
        if container is None:
            self.lg.error(f'on_daet_chk_change: map mismatch internally, {daet=}')
            return
        
        if checkbox.value:
            self.selected_daets.add(daet)
            container.opacity = 1.0
        else:
            self.selected_daets.discard(daet)
            container.opacity = 0.5

        self._update_task_chip_visuals()
        self.update()

def main(pg:ft.Page):
    pg.add(ColNoteSelector())
    pg.update()

if __name__ == '__main__':
    lf.note = ExpNote(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\09\20250902') #type:ignore
    ft.app(main)