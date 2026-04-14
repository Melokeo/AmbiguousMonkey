'''runs utils: python -m ammonkey.utils -u <util_name>'''
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run utility functions.')
    parser.add_argument('-u', '--util', type=str, required=True, help='Name of the utility to run')
    args = parser.parse_args()

    if args.util == 'av':
        from ammonkey.utils.ani_video_uiget import main as ani_video_uiget_main
        ani_video_uiget_main()
    elif args.util == 'animal-wizard':
        from ammonkey.utils.animal_wizard import main as animal_wizard_main
        animal_wizard_main()
    elif args.util == 'evtmkr' or args.util == 'event-marker':
        from ammonkey.utils.eventMarker import main as event_marker_main
        event_marker_main()
    elif args.util == 'ggl-sync':
        from ammonkey.utils.google_notes_wizard import main as google_notes_wizard_main
        google_notes_wizard_main()
    else:
        print(f'Unknown utility: {args.util}')

if __name__ == "__main__":
    main()