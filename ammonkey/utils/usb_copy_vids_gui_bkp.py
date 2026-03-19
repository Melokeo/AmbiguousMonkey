import subprocess
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import flet as ft
from datetime import datetime
from pathlib import Path

import pythoncom
import wmi as _wmi

import usb_copy_vids as ucv
from ol_logging import set_colored_logger

lg = set_colored_logger(__name__)

DEFAULT_DEST = r"P:\projects\monkeys\Remyelination\DATA_RAW\Pepe\.temp"
MAGIC_FIXED = ['DATA_RAW']
MAGIC_ANY = ['Pepe', 'Riso', '_TESTER_']

DEST = {
    'Pp': r"P:\projects\monkeys\Remyelination\DATA_RAW\Pepe",
    'Rs': r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Riso",
}

_ROW_H = 28
_HEAD_H = 30
_MAX_TABLE_H = 280

_DISK_TIMEOUT = 10  # seconds for disk-I/O operations
_COPY_TMP_SUFFIX = ".ammtmp"     # temp suffix during copy
_SIZE_WARN_RATIO = 1.67           # warn if max/min file size ratio exceeds this
_SIZE_CHECK_LOWEST = 67 * 1024 * 1024  # smallest file to trigger check (67MB, no why)
_COPY_CHUNK = 4 * 1024 * 1024          # 4 MB per chunk for cancellable copy

# window auto-size constants
_CHROME_H = 150       
_CARD_BASE_H = 34   
_CARD_CONTENT_GAP = 2  
_GRID_ROW_GAP = 4  
_INFO_LINE_H = 16    
_WIN_MIN_H = 400     # never shrink below this
_WIN_MAX_H = 950     # never grow above this


def _with_timeout(fn, timeout=_DISK_TIMEOUT, default=None):
    """Run *fn()* in a worker thread; return *default* on timeout/error."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except Exception as exc:
            lg.warning(f"Timeout/error ({timeout}s): {exc}")
            return default


def _card_vid_dir(drive_letter: str) -> Path:
    """Return absolute cam video directory for a drive like 'E:' or 'E:\\'."""
    dl = (drive_letter or "").strip()
    if len(dl) == 2 and dl[1] == ":":
        dl = f"{dl}\\"
    return Path(dl) / "PRIVATE" / "M4ROOT" / "CLIP"


def _fmt_size(n: float) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"

def _magical_target_dir(dest: Path, date: str) -> Path:
    '''auto route to date dir for known DATA_RAW/animal'''
    def _date_str_to_dir(date_str: str) -> str:
        return f"{date_str[:4]}/{date_str[4:6]}/{date_str}"
    # check valid date
    if len(date) != 8 or not date.isdigit():
        raise ValueError(f'Invalid date format: {date}')
    
    pending_any = False
    paths_to_check = [dest] + [p for p in dest.parents]
    paths_to_check.reverse()
    for p in paths_to_check:
        if pending_any:
            if p.name in MAGIC_ANY:
                new_dest = p / _date_str_to_dir(date)
                lg.info(f'Routed dest to {new_dest}')
                return new_dest
            elif p.name in MAGIC_FIXED:
                continue
            else:
                pending_any = False
        if p.name in MAGIC_FIXED:
            pending_any = True
    
    return dest


def _scan_card_files(source_dir: Path, date_str: str) -> list[tuple[str, str, str, int]] | None:
    """Disk I/O: check dir exists, list files, stat each.

    Returns *None* if the directory does not exist, or a list of
    ``(filename, mtime_str, size_str, raw_bytes)`` tuples.
    """
    if not source_dir.exists():
        return None
    files = sorted(
        ucv.files_from_date(source_dir, date_str, suffix=ucv.FILE_SUFFIXES),
        key=lambda f: f.name,
    )
    result: list[tuple[str, str, str, int]] = []
    for f in files:
        try:
            st = f.stat()
            mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            raw_bytes = st.st_size
            size = _fmt_size(raw_bytes)
        except OSError:
            mtime = "??"
            size = "??"
            raw_bytes = -1
        result.append((f.name, mtime, size, raw_bytes))
    return result


def _cancellable_copy2(src: Path, dst: Path, cancel: threading.Event,
                       chunk: int = _COPY_CHUNK):
    """``shutil.copy2`` replacement that checks *cancel* between chunks."""
    with open(src, 'rb') as fin, open(dst, 'wb') as fout:
        while True:
            if cancel.is_set():
                raise InterruptedError("copy cancelled")
            buf = fin.read(chunk)
            if not buf:
                break
            fout.write(buf)
    shutil.copystat(src, dst)


class CardPanel(ft.Container):
    """Camera card: header + full-width scrollable file detail table."""

    def __init__(self, vol_name: str, target_dir: str, chain_cb=None):
        super().__init__()
        self.vol_name = vol_name
        self.target_dir = target_dir
        self.drive_letter = ""
        self._chain_cb = chain_cb  # chain_cb(source_card, row_idx, selected)
        self._raw_sizes: list[int] = []

        self.expand = True
        self.padding = ft.padding.all(4)
        self.border_radius = 6
        self.border = ft.border.all(1, ft.Colors.OUTLINE_VARIANT)
        self.clip_behavior = ft.ClipBehavior.HARD_EDGE
        self.animate_opacity = 150

        self._last_click_idx: int | None = None  # for shift-click range select
        self._source_dir: Path | None = None      # resolved source dir for explorer

        # header
        self.dot = ft.Container(
            width=8, height=8, border_radius=4, bgcolor=ft.Colors.GREY_400,
        )
        self.title_text = ft.Text(
            vol_name, weight=ft.FontWeight.W_600, size=12, no_wrap=True,
        )
        self.count_text = ft.Text(
            "", size=10, italic=True, color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.open_folder_btn = ft.IconButton(
            icon=ft.Icons.OPEN_IN_NEW,
            icon_size=14,
            tooltip="Open folder in Explorer",
            on_click=lambda _: self._open_in_explorer(),
            style=ft.ButtonStyle(padding=0),
            width=24, height=24,
            visible=False,
        )

        header = ft.Row(
            [self.dot, self.title_text, ft.Container(expand=True),
             self.open_folder_btn, self.count_text],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # file table
        self.file_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("File", size=12, weight=ft.FontWeight.W_600)),
                ft.DataColumn(ft.Text("Modified", size=12, weight=ft.FontWeight.W_600)),
                ft.DataColumn(
                    ft.Text("Size", size=12, weight=ft.FontWeight.W_600),
                    numeric=True,
                ),
            ],
            show_checkbox_column=True,
            checkbox_horizontal_margin=0,
            horizontal_margin=4,
            column_spacing=10,
            data_row_min_height=_ROW_H,
            data_row_max_height=_ROW_H,
            heading_row_height=_HEAD_H,
            on_select_all=self._on_select_all,
        )

        self.table_wrap = ft.Container(
            content=ft.Column(
                [self.file_table], scroll=ft.ScrollMode.AUTO, spacing=0,
            ),
            visible=False,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        self.info_text = ft.Text(
            "", size=10, italic=True, color=ft.Colors.AMBER_700, visible=False,
        )

        self.content = ft.Column([header, self.info_text, self.table_wrap], spacing=2)

    # -- explorer --
    def _open_in_explorer(self):
        if self._source_dir and self._source_dir.exists():
            subprocess.Popen(["explorer.exe", str(self._source_dir)])

    # -- selection --
    def _on_select_all(self, e):
        val = e.data == "true"
        for row in self.file_table.rows:
            row.selected = val
        self._update_count()
        if self._chain_cb:
            for i in range(len(self.file_table.rows)):
                self._chain_cb(self, i, val)
        self.page.update()

    def _on_row_toggle(self, e, row, idx):
        new_val = e.data == "true"
        row.selected = new_val

        # shift-click: fill range between last click and this one
        shift_on = (
            self.page is not None
            and hasattr(self.page, "_kb")
            and bool(self.page._kb.get("shift"))
        )
        applied_range = False
        if shift_on and self._last_click_idx is not None:
            lo = min(self._last_click_idx, idx)
            hi = max(self._last_click_idx, idx)
            for ri in range(lo, hi + 1):
                self.file_table.rows[ri].selected = new_val
                if self._chain_cb:
                    self._chain_cb(self, ri, new_val)
            applied_range = True

        self._last_click_idx = idx
        self._update_count()
        if self._chain_cb and not applied_range:
            self._chain_cb(self, idx, new_val)
        self.page.update()

    def _update_count(self):
        total = len(self.file_table.rows)
        sel = sum(1 for r in self.file_table.rows if r.selected)
        self.count_text.value = f"{sel}/{total}" if total else ""

    def set_row_selected(self, idx: int, selected: bool):
        """Set selection at idx (called by chain, no chain re-fire)."""
        if 0 <= idx < len(self.file_table.rows):
            self.file_table.rows[idx].selected = selected
            self._update_count()

    def file_count(self) -> int:
        return len(self.file_table.rows)

    # -- refresh / query --
    def refresh(self, date_str: str, drive_map: dict[str, str]):
        self.drive_letter = drive_map.get(self.vol_name, "")
        self.file_table.rows.clear()
        self._raw_sizes.clear()
        self._last_click_idx = None
        self.info_text.value = ""
        self.info_text.visible = False

        if not self.drive_letter:
            self.dot.bgcolor = ft.Colors.GREY_400
            self.title_text.value = self.vol_name
            self.opacity = 0.45
            self.table_wrap.visible = False
            self.count_text.value = ""
            self._source_dir = None
            self.open_folder_btn.visible = False
            return

        self.dot.bgcolor = ft.Colors.GREEN_600
        self.title_text.value = f"{self.vol_name} ({self.drive_letter})"
        self.opacity = 1.0

        source_dir = _card_vid_dir(self.drive_letter)
        self._source_dir = source_dir

        # -- disk I/O with timeout --
        file_infos = _with_timeout(
            lambda: _scan_card_files(source_dir, date_str),
            timeout=_DISK_TIMEOUT,
            default="timeout",
        )

        if file_infos == "timeout":
            self.dot.bgcolor = ft.Colors.AMBER_600
            self.open_folder_btn.visible = False
            self.table_wrap.visible = False
            self.count_text.value = ""
            self.info_text.value = f"Timed out reading {self.drive_letter}"
            self.info_text.visible = True
            lg.warning(f"Timed out reading {self.drive_letter} ({self.vol_name})")
            return

        if file_infos is None:
            self.open_folder_btn.visible = False
            self.table_wrap.visible = False
            self.count_text.value = ""
            return

        self.open_folder_btn.visible = True
        lg.debug(f"Refreshed {self.drive_letter}({self.vol_name}): {len(file_infos)} files")

        for i, (fname, mtime, size, raw_bytes) in enumerate(file_infos):
            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(fname, size=11, no_wrap=True)),
                    ft.DataCell(
                        ft.Text(mtime, size=10, color=ft.Colors.ON_SURFACE_VARIANT)
                    ),
                    ft.DataCell(ft.Text(size, size=10)),
                ],
                selected=True,
            )
            row.on_select_changed = (
                lambda e, r=row, ii=i: self._on_row_toggle(e, r, ii)
            )
            self.file_table.rows.append(row)
            self._raw_sizes.append(raw_bytes)

        n = len(file_infos)
        self.table_wrap.visible = n > 0
        self.table_wrap.height = (
            min(_HEAD_H + n * _ROW_H, _MAX_TABLE_H) if n else None
        )
        self._update_count()

    def get_selected(self) -> list[str]:
        return [
            row.cells[0].content.value
            for row in self.file_table.rows
            if row.selected
        ]

    def get_raw_sizes(self) -> list[int]:
        """Return raw byte sizes parallel to table rows."""
        return list(self._raw_sizes)


class _UsbWatcher:
    """Background thread that listens for Windows USB volume events.

    Uses WMI ``Win32_VolumeChangeEvent``.  Two modes of operation:

    * **wait_for_replug=False** (default) – fires the callback as soon
      as all expected volumes are connected.
    * **wait_for_replug=True** – if all volumes are *already* present
      when the watcher starts, it first waits for at least one to be
      *removed*, then waits for all to come back.  This prevents the
      "hide → immediate pop-back" problem.
    """

    def __init__(self, expected_vols: set[str], on_all_connected,
                 wait_for_replug: bool = False):
        self._expected = expected_vols
        self._on_all = on_all_connected
        self._wait_for_replug = wait_for_replug
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _all_present(self) -> bool:
        drives = ucv.scan_drives()
        return self._expected.issubset(set(drives.keys()))

    def _run(self):
        pythoncom.CoInitialize()
        try:
            already_all = self._all_present()

            if already_all and not self._wait_for_replug:
                # All here and we don't need a replug – fire immediately.
                self._on_all()
                return

            c = _wmi.WMI()
            watcher = c.Win32_VolumeChangeEvent.watch_for()

            # Phase 1 (only when wait_for_replug and all already present):
            # wait until at least one expected drive disappears.
            if already_all and self._wait_for_replug:
                lg.debug("USB watcher: all present, waiting for a removal")
                while not self._stop.is_set():
                    try:
                        watcher(timeout_ms=2000)
                        time.sleep(0.5)
                    except _wmi.x_wmi_timed_out:
                        pass
                    if self._stop.is_set():
                        return
                    if not self._all_present():
                        lg.debug("USB watcher: removal detected, now waiting for reconnect")
                        break

            # Phase 2: wait until all expected drives are connected.
            while not self._stop.is_set():
                try:
                    watcher(timeout_ms=2000)
                    # Real event – brief pause so the OS finishes mounting.
                    time.sleep(1)
                except _wmi.x_wmi_timed_out:
                    pass  # fall through to the check below
                if self._stop.is_set():
                    break
                if self._all_present():
                    self._on_all()
                    break
        except Exception as exc:
            lg.error(f"USB watcher error: {exc}")
        finally:
            pythoncom.CoUninitialize()


# ── Main application ─────────────────────────────────────────────────

class VideoIngestApp:
    """Flet-based GUI for copying camera-card videos."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.selected_date: datetime = datetime.today()
        self._chain_enabled = False
        self._usb_watcher: _UsbWatcher | None = None
        self._cancel_copy = threading.Event()
        self._copy_thread: threading.Thread | None = None
        self._closing = False

        self._configure_page()
        self._build_widgets()
        self._layout()
        self.trigger_refresh()

    # ── page setup ──

    def _configure_page(self):
        p = self.page
        p.title = "video ingest"
        p.theme = ft.Theme(color_scheme_seed=ft.Colors.ORANGE)
        p.padding = 8
        p.spacing = 0
        p.window.width = 608
        p.window.height = 715
        p.window.prevent_close = True

        p._kb = {"shift": False}
        p.on_keyboard_event = self._on_kb
        p.window.on_event = self._on_window_event

    # ── widget construction ──

    def _build_widgets(self):
        # date picker
        self.date_label = ft.Text(
            self.selected_date.strftime("%Y-%m-%d"),
            size=12, weight=ft.FontWeight.W_600,
        )
        self.date_picker = ft.DatePicker(
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
            value=self.selected_date,
            on_change=self._on_date_picked,
        )
        self.page.overlay.append(self.date_picker)

        # card panels
        self.card_widgets: list[CardPanel] = [
            CardPanel(vol, target, chain_cb=self._on_chain_row)
            for vol, target in ucv.TARGET_VID_DIRS.items()
        ]

        # chain button
        self.chain_btn = ft.IconButton(
            icon=ft.Icons.LINK,
            icon_size=18,
            tooltip="Chain OFF",
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            on_click=self._toggle_chain,
            style=ft.ButtonStyle(padding=0),
            width=32, height=30,
        )

        # minimize / usb-watch button
        self.minimize_btn = ft.IconButton(
            icon=ft.Icons.VISIBILITY_OFF,
            icon_size=18,
            tooltip="Hide | reappears when all cards connected",
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            on_click=self._minimize_to_watch,
            style=ft.ButtonStyle(padding=0),
            width=32, height=30,
        )

        # action buttons
        self.date_btn = ft.OutlinedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.CALENDAR_MONTH, size=14), self.date_label],
                spacing=4, tight=True,
            ),
            on_click=lambda _: self.page.open(self.date_picker),
            height=30,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=10, vertical=0),
            ),
        )
        self.btn_refresh = ft.ElevatedButton(
            "Refresh", icon=ft.Icons.REFRESH,
            on_click=lambda _: self.trigger_refresh(),
            height=30,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=10, vertical=0),
            ),
        )
        self.btn_copy = ft.FilledButton(
            "Copy", icon=ft.Icons.CONTENT_COPY,
            on_click=lambda _: self.trigger_copy(),
            height=30,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=14, vertical=0),
            ),
        )

        # destination row
        self.dest_input = ft.TextField(
            value=DEFAULT_DEST, expand=True, dense=True, text_size=12,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=6,
            on_change=self._on_dest_typed,
        )
        self.folder_picker = ft.FilePicker(on_result=self._on_folder_picked)
        self.page.overlay.append(self.folder_picker)

        self.btn_browse = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN, icon_size=18, tooltip="Browse",
            on_click=lambda _: self.folder_picker.get_directory_path(
                dialog_title="Select destination",
                initial_directory=self.dest_input.value or str(DEFAULT_DEST),
            ),
            style=ft.ButtonStyle(padding=0),
            width=32, height=32,
        )

        # ── dest animal preset chips (first two DEST entries) ──
        dest_items = list(DEST.items())[:2]
        self._dest_chip_keys = [k for k, _ in dest_items]
        self._dest_chips: list[ft.Chip] = [
            ft.Chip(
                label=ft.Text(key, size=10),
                selected=False,
                on_select=lambda e, k=key: self._on_dest_chip(k, e.data == "true"),
                padding=ft.padding.symmetric(horizontal=0, vertical=0),
                show_checkmark=False,
                height=20,
            )
            for key, _ in dest_items
        ]
        self._sync_dest_chips()

        # ── dest path right-click context menu ──
        self._ctx_menu = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [ft.Icon(ft.Icons.OPEN_IN_NEW, size=13),
                             ft.Text("Reveal in Explorer", size=12)],
                            spacing=8, tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        on_click=self._reveal_dest_in_explorer,
                        ink=True,
                        border_radius=2,
                    )
                ],
                spacing=0, tight=True,
            ),
            # bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=4,
            padding=ft.padding.symmetric(vertical=4),
            shadow=ft.BoxShadow(
                blur_radius=8, spread_radius=0,
                color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            width=180,
            visible=False,
        )
        self._ctx_backdrop = ft.Container(
            expand=True,
            bgcolor=ft.Colors.TRANSPARENT,
            on_click=self._dismiss_ctx_menu,
            visible=False,
        )
        self.page.overlay.extend([self._ctx_backdrop, self._ctx_menu])

        # wrap TextField so right-click is intercepted without breaking normal input
        self.dest_gesture = ft.GestureDetector(
            content=self.dest_input,
            on_secondary_tap_down=self._on_dest_right_click,
            expand=True,
        )

        # status bar
        self._status_ring = ft.ProgressRing(width=14, height=14, stroke_width=2)
        self._status_text = ft.Text("", size=11, italic=True)
        self.status_row = ft.Row(
            [self._status_ring, self._status_text],
            spacing=6, visible=False,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # size-mismatch warnings (shown when chain is on)
        self._size_warn_col = ft.Column([], spacing=2, visible=False)

    # ── layout ──

    def _layout(self):
        row1 = ft.Row(
            [self.date_btn, self.btn_refresh, ft.Container(expand=True),
             self.minimize_btn, self.chain_btn, self.btn_copy],
            spacing=6,
        )
        row2 = ft.Row(
            [ft.Text("Dest", size=11, weight=ft.FontWeight.W_600),
             self.dest_gesture, *self._dest_chips, self.btn_browse],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        grid_rows: list[ft.Row] = []
        for i in range(0, len(self.card_widgets), 2):
            pair = self.card_widgets[i : i + 2]
            grid_rows.append(ft.Row(pair, spacing=4))

        cards_grid = ft.Column(
            grid_rows, spacing=4, expand=True, scroll=ft.ScrollMode.AUTO,
        )

        self.page.add(
            ft.Column(
                [row1, row2, ft.Divider(height=1, thickness=0.5),
                 cards_grid, self._size_warn_col, self.status_row],
                spacing=4,
                expand=True,
            )
        )

    # ── event handlers ──

    @staticmethod
    def _on_kb(e: ft.KeyboardEvent):
        e.page._kb["shift"] = bool(e.shift)

    def _on_window_event(self, e):
        if e.data == "close":
            self._closing = True
            self._cancel_copy.set()
            self._stop_usb_watcher()
            if self._copy_thread and self._copy_thread.is_alive():
                self._copy_thread.join(timeout=5)
            self.page.window.destroy()

    def _on_date_picked(self, e):
        if self.date_picker.value:
            self.selected_date = self.date_picker.value
            self.date_label.value = self.selected_date.strftime("%Y-%m-%d")
            self.trigger_refresh()

    def _on_folder_picked(self, e):
        if e.path:
            self.dest_input.value = e.path
            self._sync_dest_chips()
            self.page.update()

    # ── dest chips ──

    def _on_dest_chip(self, key: str, is_selected: bool):
        if is_selected:
            self.dest_input.value = DEST[key]
        self._sync_dest_chips()
        self.page.update()

    def _on_dest_typed(self, _e):
        self._sync_dest_chips()
        self.page.update()

    def _sync_dest_chips(self):
        """Highlight the chip whose base path contains the current dest value."""
        val = self.dest_input.value or ""
        try:
            current = Path(val)
        except Exception:
            current = None
        for i, key in enumerate(self._dest_chip_keys):
            try:
                base = Path(DEST[key])
                selected = current is not None and (
                    current == base or current.is_relative_to(base)
                )
            except Exception:
                selected = False
            self._dest_chips[i].selected = selected

    # ── dest context menu ──

    def _on_dest_right_click(self, e):
        x = min(e.global_x, (self.page.window.width or 608) - 185)
        y = e.global_y + 4
        self._ctx_menu.left = x
        self._ctx_menu.top = y
        self._ctx_menu.visible = True
        self._ctx_backdrop.visible = True
        self.page.update()

    def _dismiss_ctx_menu(self, _e=None):
        self._ctx_menu.visible = False
        self._ctx_backdrop.visible = False
        self.page.update()

    def _reveal_dest_in_explorer(self, _e=None):
        self._dismiss_ctx_menu()
        path = Path(self.dest_input.value or DEFAULT_DEST)
        # Walk up to the nearest existing ancestor so Explorer always opens
        while not path.exists() and path != path.parent:
            path = path.parent
        subprocess.Popen(["explorer.exe", str(path)])

    # ── chain logic ──

    def _can_chain(self) -> bool:
        counts = [cw.file_count() for cw in self.card_widgets if cw.drive_letter]
        return len(counts) >= 2 and len(set(counts)) == 1 and counts[0] > 0

    def _on_chain_row(self, source_card, row_idx, selected):
        if not self._chain_enabled or not self._can_chain():
            return
        for cw in self.card_widgets:
            if cw is not source_card and cw.drive_letter:
                cw.set_row_selected(row_idx, selected)

    def _toggle_chain(self, _e):
        self._chain_enabled = not self._chain_enabled
        on = self._chain_enabled
        self.chain_btn.icon_color = (
            ft.Colors.ORANGE if on else ft.Colors.ON_SURFACE_VARIANT
        )
        self.chain_btn.tooltip = (
            "Chain ON | syncs row selection across cards" if on else "Chain OFF"
        )
        self._check_size_mismatches()
        self.page.update()

    def _sync_chain_btn(self):
        """Update chain button state after a refresh."""
        can = self._can_chain()
        self.chain_btn.disabled = not can
        self.chain_btn.selected = can
        if can:
            self._chain_enabled = True
            self.chain_btn.icon_color = ft.Colors.ORANGE
            self.chain_btn.tooltip = "Chain ON | syncs row selection across cards"
        else:
            self._chain_enabled = False
            self.chain_btn.icon_color = ft.Colors.ON_SURFACE_VARIANT
            self.chain_btn.tooltip = "Chain OFF"

    # ── size-mismatch checker ──

    def _check_size_mismatches(self):
        """Compare file sizes across connected cards; warn on large deviations."""
        self._size_warn_col.controls.clear()
        self._size_warn_col.visible = False

        if not self._chain_enabled:
            return

        connected = [cw for cw in self.card_widgets if cw.drive_letter]
        if len(connected) < 2:
            return

        counts = [cw.file_count() for cw in connected]
        if len(set(counts)) != 1 or counts[0] == 0:
            return

        n_files = counts[0]
        warnings: list[str] = []

        for idx in range(n_files):
            sizes: dict[str, int] = {}
            for cw in connected:
                raw = cw.get_raw_sizes()
                if idx < len(raw) and raw[idx] >= 0:
                    sizes[cw.vol_name] = raw[idx]

            if len(sizes) < 2:
                continue

            if all(s <= _SIZE_CHECK_LOWEST for s in sizes.values()):
                continue

            vals = list(sizes.values())
            min_s, max_s = min(vals), max(vals)
            if min_s <= 0:
                continue

            ratio = max_s / min_s
            if ratio > _SIZE_WARN_RATIO:
                fname = connected[0].file_table.rows[idx].cells[0].content.value
                parts = ", ".join(f"{k}: {_fmt_size(v)}" for k, v in sizes.items())
                warnings.append(f"\u26a0 {fname} - {parts}  ({ratio:.1f}x)")

        if warnings:
            for w in warnings:
                self._size_warn_col.controls.append(
                    ft.Text(w, size=11, color=ft.Colors.AMBER_700)
                )
            self._size_warn_col.visible = True

    # ── USB-watch / minimize ──

    def _minimize_to_watch(self, _e=None):
        """Hide window and start listening for USB events.

        If all drives are already connected we use ``wait_for_replug=True``
        so the watcher requires at least one removal before triggering,
        preventing the immediate-pop-back problem.
        """
        expected = set(ucv.TARGET_VID_DIRS.keys())
        currently_all = expected.issubset(set(ucv.scan_drives().keys()))

        w = _UsbWatcher(
            expected,
            self._on_all_drives_connected,
            wait_for_replug=currently_all,
        )
        self._usb_watcher = w
        self.page.window.visible = False
        self.page.update()
        w.start()

    def _on_all_drives_connected(self):
        self._usb_watcher = None
        self.page.window.visible = True
        self.page.window.focused = True

        # set to today
        self.date_picker.value = datetime.today()
        self.date_picker.on_change(self.date_picker)
        self._safe_update()

    def _stop_usb_watcher(self):
        if self._usb_watcher:
            self._usb_watcher.stop()
            self._usb_watcher = None

    # ── status helpers ──

    def _safe_update(self):
        """page.update() that silently no-ops after window close."""
        if self._closing:
            return
        try:
            self.page.update()
        except Exception:
            pass

    def _safe_open(self, control):
        """page.open() that silently no-ops after window close."""
        if self._closing:
            return
        try:
            self.page.open(control)
        except Exception:
            pass

    def _show_status(self, msg: str):
        self._status_text.value = msg
        self.status_row.visible = True
        self._safe_update()

    def _hide_status(self):
        self.status_row.visible = False
        self._status_ring.value = None  # back to indeterminate spin
        self._safe_update()

    def _show_copy_progress(self, done: int, total: int):
        """Update status text and drive the ring deterministically."""
        self._status_text.value = f"Copying... {done}/{total} files"
        self._status_ring.value = done / total if total else 0
        self.status_row.visible = True
        self._safe_update()

    # ── window sizing ──

    def _compute_window_height(self) -> int:
        """Return the window height needed to exactly fit current card states."""
        n_pairs = (len(self.card_widgets) + 1) // 2
        grid_h = max(0, n_pairs - 1) * _GRID_ROW_GAP
        for i in range(0, len(self.card_widgets), 2):
            pair = self.card_widgets[i : i + 2]
            row_h = 0
            for cw in pair:
                h = _CARD_BASE_H
                if cw.info_text.visible:
                    h += _CARD_CONTENT_GAP + _INFO_LINE_H
                if cw.table_wrap.visible and cw.table_wrap.height:
                    h += _CARD_CONTENT_GAP + cw.table_wrap.height
                row_h = max(row_h, h)
            grid_h += row_h
        total = _CHROME_H + grid_h
        return max(_WIN_MIN_H, min(total, _WIN_MAX_H))

    # ── actions ──

    def trigger_refresh(self):
        self.btn_refresh.disabled = True
        self.btn_copy.disabled = True
        self.page.update()

        def _do():
            self._show_status("Scanning drives...")
            drives = _with_timeout(ucv.scan_drives, timeout=_DISK_TIMEOUT, default={})
            if drives is None:
                drives = {}

            ds = self.selected_date.strftime("%Y%m%d")
            for cw in self.card_widgets:
                self._show_status(f"Reading {cw.vol_name}...")
                cw.refresh(ds, drives)
                self._safe_update()

            self._sync_chain_btn()
            self._check_size_mismatches()
            self.btn_refresh.disabled = False
            self.btn_copy.disabled = False
            self.status_row.visible = False
            self.page.window.height = self._compute_window_height()
            self._safe_update()

        threading.Thread(target=_do, daemon=True).start()

    def trigger_copy(self):
        self.btn_copy.disabled = True
        self.btn_refresh.disabled = True
        self._show_status("Preparing copy...")

        def _do():
            self._cancel_copy.clear()
            base = Path(self.dest_input.value or DEFAULT_DEST)
            base = _magical_target_dir(base, self.selected_date.strftime("%Y%m%d"))

            if not base.exists():
                try:
                    base.mkdir(parents=True, exist_ok=True)
                    lg.info(f'Created destination dir: {base}')
                except OSError as e:
                    lg.error(f'Failed to create destination dir {base}: {e}')
                    self._safe_open(
                        ft.SnackBar(ft.Text("Invalid destination path"), duration=2000)
                    )
                    self.btn_copy.disabled = False
                    self.btn_refresh.disabled = False
                    self._hide_status()
                    return

            card_jobs: list[tuple[CardPanel, list[str], Path]] = []
            for cw in self.card_widgets:
                if not cw.drive_letter:
                    continue
                sel = cw.get_selected()
                if not sel:
                    continue
                dst_dir = base / cw.target_dir
                dst_dir.mkdir(parents=True, exist_ok=True)
                card_jobs.append((cw, sel, dst_dir))

            if not card_jobs:
                self._safe_open(
                    ft.SnackBar(ft.Text("Nothing to copy"), duration=2000)
                )
                self.btn_copy.disabled = False
                self.btn_refresh.disabled = False
                self._hide_status()
                return

            total_files = sum(len(sel) for _, sel, _ in card_jobs)
            done_files = [0]
            _progress_lock = threading.Lock()
            self._show_copy_progress(0, total_files)

            def _copy_card(cw: CardPanel, files: list[str], dst_dir: Path) -> list[Path]:
                src_dir = _card_vid_dir(cw.drive_letter)
                copied: list[Path] = []
                for fname in files:
                    if self._cancel_copy.is_set():
                        lg.info(f"[{cw.vol_name}] Copy cancelled")
                        break
                    src = src_dir / fname
                    dst = dst_dir / fname
                    if dst.exists():
                        lg.info(f"[{cw.vol_name}] Skipped {fname} (exists)")
                        with _progress_lock:
                            done_files[0] += 1
                            self._show_copy_progress(done_files[0], total_files)
                        continue
                    # Write to a temp file first, then atomically rename so
                    # an interrupted copy never leaves a half-written final file.
                    tmp = dst.with_name(dst.name + _COPY_TMP_SUFFIX)
                    try:
                        _cancellable_copy2(src, tmp, self._cancel_copy)
                        tmp.replace(dst)
                    except BaseException:
                        try:
                            if tmp.exists():
                                tmp.unlink()
                        except OSError:
                            lg.warning(f"Could not remove partial temp file {tmp}")
                        raise
                    lg.info(f"[{cw.vol_name}] Copied {fname}")
                    copied.append(dst)
                    with _progress_lock:
                        done_files[0] += 1
                        self._show_copy_progress(done_files[0], total_files)
                return copied

            # Clean up leftover temp files from any prior interrupted copy
            for _, _, d in card_jobs:
                for stale in d.glob(f"*{_COPY_TMP_SUFFIX}"):
                    try:
                        stale.unlink()
                        lg.info(f"Removed stale temp file: {stale.name}")
                    except OSError:
                        pass

            all_copied: list[Path] = []
            errors: list[str] = []
            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = {
                    pool.submit(_copy_card, cw, sel, dst): cw
                    for cw, sel, dst in card_jobs
                }
                for fut in as_completed(futs):
                    card = futs[fut]
                    try:
                        all_copied.extend(fut.result())
                    except Exception as exc:
                        if not self._cancel_copy.is_set():
                            lg.error(f"Copy failed for card {card.vol_name}: {exc}")
                            errors.append(f"{card.vol_name}: {exc}")

            if self._cancel_copy.is_set():
                msg = f"Copy cancelled; {len(all_copied)} file(s) completed"
            elif errors:
                msg = f"Copied {len(all_copied)} file(s) with {len(errors)} error(s)"
            else:
                n = len(all_copied)
                msg = f"Copied {n} file(s)" if n else "Nothing new to copy"
            self._safe_open(ft.SnackBar(ft.Text(msg), duration=3000))
            self.btn_copy.disabled = False
            self.btn_refresh.disabled = False
            self._hide_status()

        t = threading.Thread(target=_do, daemon=True)
        self._copy_thread = t
        t.start()


# ── entry point ──────────────────────────────────────────────────────

def main(page: ft.Page):
    VideoIngestApp(page)


if __name__ == "__main__":
    ft.app(target=main)