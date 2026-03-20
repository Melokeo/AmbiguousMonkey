import argparse
import sys

def main() -> None:
    '''main entry, also used in pyproject'''
    parser = argparse.ArgumentParser(prog="ammonkey")
    parser.add_argument("-u", "--util", type=str, help="Run a utility by name")
    args, remaining = parser.parse_known_args()

    if args.util:
        # route -u to utils
        sys.argv = ["ammonkey.utils", "-u", args.util] + remaining
        from ammonkey.utils.__main__ import main as utils_main
        utils_main()
        return

    import flet as ft
    from .gui_v3.flet_main import AmmApp
    ft.app(AmmApp())

if __name__ == "__main__":
    main()