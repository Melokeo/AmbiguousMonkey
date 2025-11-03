import flet as ft
from .gui_v3.flet_main import AmmApp

def main() -> None:
    '''main gui entry, also used in pyproject'''
    ft.app(AmmApp())

if __name__ == '__main__':
    main()