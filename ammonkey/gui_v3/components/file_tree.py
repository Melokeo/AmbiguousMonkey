# file_tree_view.py
from __future__ import annotations
import os, sys, subprocess
from pathlib import Path
import flet as ft


class FileTreeView(ft.ListView):
    """
    Fully expanded file tree snapshot for viewing. Double-click files to open.
    """
    def __init__(
        self,
        root_dir: str | Path,
        show_hidden: bool = False,
        indent_px: int = 12,
        font_size: int = 11,
        icon_size: int = 14,
        max_items: int | None = None,  # soft cap for huge trees
        max_expand_level: int | None = None,
    ):
        super().__init__()
        self.expand = True
        self.spacing = 0
        self.auto_scroll = False

        self.root = Path(root_dir).expanduser().resolve()
        self.show_hidden = show_hidden
        self.indent = indent_px
        self.font = font_size
        self.icon = icon_size
        self.max_items = max_items
        self.max_expand_level = max_expand_level
        self.expanded_dirs: set[Path] = set()

    # render only after attachment to page
    def did_mount(self):
        self._render_snapshot()
        if self.page:
            self.page.update()

    def set_root(self, root_dir: str | Path):
        self.root = Path(root_dir).expanduser().resolve()
        self._render_snapshot()
        if self.page:
            self.page.update()

    # ---- internals ----
    def _render_snapshot(self):
        rows: list[ft.Control] = []
        count = 0
        for level, path, is_dir, expanded in self._walk(self.root):
            if self.max_items is not None and count >= self.max_items:
                break
            rows.append(self._row(path, level, is_dir, expanded))
            count += 1
        self.controls.clear()
        self.controls.extend(rows)

    def _walk(self, start: Path):
        stack: list[tuple[int, Path, bool]] = [(0, start, True)]  # level, path, expanded
        while stack:
            level, path, expanded = stack.pop()
            is_dir = path.is_dir()
            
            # auto-expand up to max level, check manual expansion beyond
            if self.max_expand_level is not None and level >= self.max_expand_level:
                expanded = path in self.expanded_dirs
            elif self.max_expand_level is not None:
                expanded = level < self.max_expand_level
            
            yield level, path, is_dir, expanded
            
            if not is_dir or not expanded:
                continue
                
            entries: list[Path] = []
            try:
                with os.scandir(path) as it:
                    for e in it:
                        name = e.name
                        if not self.show_hidden and name.startswith("."):
                            continue
                        entries.append(Path(e.path))
            except (PermissionError, FileNotFoundError):
                entries = []
            
            # dirs first, then files; case-insensitive, extension then name
            entries.sort(key=lambda p: (p.is_file(), p.suffix.lower(), p.name.lower()))
            # push in reverse so iteration is natural (top-to-bottom)
            for child in reversed(entries):
                stack.append((level + 1, child, expanded))

    def _get_icon(self, path: Path, is_dir: bool) -> str:
        if is_dir:
            return ft.Icons.FOLDER_OUTLINED
        ext = path.suffix.lower()
        if ext == '.mp4':
            return ft.Icons.PLAY_CIRCLE_OUTLINE
        elif ext == '.csv':
            return ft.Icons.TABLE_CHART_OUTLINED
        elif ext in ['.xlsx', '.xls']:
            return ft.Icons.GRID_ON_OUTLINED
        return ft.Icons.INSERT_DRIVE_FILE_OUTLINED

    def _row(self, path: Path, level: int, is_dir: bool, expanded: bool) -> ft.Control:
        icon = self._get_icon(path, is_dir)
        label = path.name if path != self.root else str(path)
        pad_l = self.indent * level + 4
        
        trailing = None
        # add expand/collapse for dirs beyond max level
        if is_dir and self.max_expand_level is not None and level >= self.max_expand_level:
            trailing = ft.IconButton(
                icon=ft.Icons.EXPAND_MORE if not expanded else ft.Icons.EXPAND_LESS,
                icon_size=12,
                on_click=lambda e, p=path: self._toggle_expand(p)
            )
        
        tile = ft.ListTile(
                leading=ft.Icon(icon, size=self.icon),
                trailing=trailing,
                min_leading_width=0,
                min_vertical_padding=0,
                min_height=0,
                title=ft.Text(label, no_wrap=True, size=self.font),
                content_padding=ft.padding.only(left=pad_l, right=4, top=0, bottom=0),
                visual_density=ft.VisualDensity.COMPACT,
                scale=0.92,
            )
        return ft.GestureDetector(content=tile, on_double_tap=lambda e, p=path: self._open_file(p))

    def _toggle_expand(self, path: Path):
        if path in self.expanded_dirs:
            self.expanded_dirs.remove(path)
        else:
            self.expanded_dirs.add(path)
        self._render_snapshot()
        if self.page:
            self.page.update()

    def _open_file(self, p: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as ex:
            print(f"OPEN FAILED: {p} ({ex})")


class MultiTreeView(ft.Tabs):
    """
    Tabbed file tree view with lazy loading for memory efficiency.
    """
    def __init__(
        self,
        roots: list[Path | str],
        show_hidden: bool = False,
        indent_px: int = 12,
        font_size: int = 11,
        icon_size: int = 14,
        max_items: int | None = None,
        max_expand_level: int | None = 2,
    ):
        super().__init__()
        self.expand = True
        self.scrollable = True
        self.tab_alignment = ft.TabAlignment.START
        
        self.roots = [Path(r).expanduser().resolve() for r in roots]
        self.tree_kwargs = {
            'show_hidden': show_hidden,
            'indent_px': indent_px, 
            'font_size': font_size,
            'icon_size': icon_size,
            'max_items': max_items,
            'max_expand_level': max_expand_level,
        }
        self.trees: dict[int, FileTreeView] = {}  # lazy cache
        
        # create tabs without content initially
        for i, root in enumerate(self.roots):
            tab = ft.Tab(
                text=root.name or str(root),
                content=ft.Container()  # placeholder
            )
            self.tabs.append(tab)
        
        self.on_change = self._on_tab_change
    
    def did_mount(self):
        # render initial tab
        if self.tabs:
            self._load_tree(0)
            if self.page:
                self.page.update()
    
    def _on_tab_change(self, e):
        """lazy load tree when tab becomes active"""
        if e.control.selected_index is not None:
            self._load_tree(e.control.selected_index)
    
    def _load_tree(self, index: int):
        """create tree view only when needed"""
        if index in self.trees:
            return  # already loaded
        
        root = self.roots[index]
        tree = FileTreeView(root, **self.tree_kwargs)
        self.trees[index] = tree
        self.tabs[index].content = tree
        
        if self.page:  # ensure it renders
            tree.did_mount()


# demo
def main(page: ft.Page):
    page.title = "Multi File Tree"
    page.window.min_width = 600
    page.window.min_height = 400

    r = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Fusillo\2025\09\20250902')
    d = Path(r'P:\projects\monkeys\Chronic_VLL\DATA\Fusillo\2025\09\20250902')
    
    page.add(MultiTreeView([r, d], show_hidden=False))

if __name__ == "__main__":
    ft.app(target=main)