import flet as ft
from pathlib import Path
from file_tree import FileTreeView

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
            self.update()
    
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
            self.page.update()

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