'''runs utils: python -m ammonkey.utils -u <util_name>'''

import argparse
from ammonkey.utils.ani_video_uiget import main as ani_video_uiget_main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run utility functions.')
    parser.add_argument('-u', '--util', type=str, required=True, help='Name of the utility to run')
    args = parser.parse_args()

    if args.util == 'av':
        ani_video_uiget_main()
    else:
        print(f'Unknown utility: {args.util}')