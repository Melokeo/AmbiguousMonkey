'''runs utils: python -m ammonkey.utils -u <util_name>'''

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run utility functions.')
    parser.add_argument('-u', '--util', type=str, required=True, help='Name of the utility to run')
    args = parser.parse_args()
    
    if not args.util:
        print('Please specify a utility to run using -u or --util')
        exit(1)
        
    if args.util == 'av':
        from ammonkey.utils.ani_video_uiget import main as ani_video_uiget_main
        ani_video_uiget_main()
    if args.util == 'animal-wizard':
        from ammonkey.utils.animal_wizard import main as animal_wizard_main
        animal_wizard_main()
    else:
        print(f'Unknown utility: {args.util}')