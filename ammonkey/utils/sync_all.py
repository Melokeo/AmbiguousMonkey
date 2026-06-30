'''sync all usable dates for given animal.
rewritten for Pepe <3
'''

from ammonkey import ExpNote, Path, Task, VidSynchronizer, dataSetup
from ol_logging import set_colored_logger
from iterate_days import iterate_days
import json

lg = set_colored_logger(__name__)

sync_dict = {}  # date: (note, vs)
roi_cache = Path(__file__).parent / Path("roi_cache.json")
if not roi_cache.exists():
    roi_cache.touch()
    # write {}
    with open(roi_cache, "w") as f:
        json.dump({}, f)

skipped = ['20260428']

def batch_select_roi(base: Path, start, end) -> dict[str, tuple[ExpNote, VidSynchronizer]]:
    for day in iterate_days(base, start, end):
        try:
            n = ExpNote(path = day)
        except (FileNotFoundError, ValueError) as e:
            continue
        except Exception as e:
            lg.error(f"Error loading {day}: {e}")
            continue
        print(f'\n======= {day} =======')
        if not any(n.daets):
            print(f'No daets found')
            continue
        if day.name in skipped:
            print(f'Skipping {day} due to known sync issues')
            continue

        dataSetup(raw_path=day)
        
        vs = VidSynchronizer(n)
        temp_rois = get_cached_rois(day.name)
        if temp_rois:
            print(f'Using cached ROIs for {day.name}')
            vs.cam_config.rois = temp_rois #type: ignore
        else:
            vs.setROI()
            cache_rois(day.name, vs.cam_config.rois) #type: ignore

        if input('LED2 clr Y/B').lower() == 'y':
            vs.cam_config.led_colors[2] = 'Y'

        sync_dict[day.name] = (n, vs)

    if not sync_dict:
        print("No valid notes found in the specified date range.")
    return sync_dict

def cache_rois(date: str, rois: dict[int, tuple[int, ...]]) -> None:
    with open(roi_cache, "r") as f:
        cache = json.load(f)
    cache[date] = rois
    with open(roi_cache, "w") as f:
        json.dump(cache, f)

def get_cached_rois(date: str) -> dict[int, tuple[int, ...]] | None:
    with open(roi_cache, "r") as f:
        cache = json.load(f)
    return cache.get(date, None)

def batch_run_sync(sync_dict: dict[str, tuple[ExpNote, VidSynchronizer]]):
    for day, (note, vs) in sync_dict.items():
        print(f'\n=======  {day} =======')
        print(f'Note has {len(note.daets)} daets')
        try:
            result = vs.syncAll()
            print(f'Sync result for {day}: {result}')
        except Exception as e:
            print(f'Error syncing {day}: {e}')

if __name__ == "__main__":
    base = Path(r'P:\projects\monkeys\Remyelination\DATA_RAW\Pepe')
    start = 2025
    end = 2027

    sync_dict = batch_select_roi(base, start, end)
    batch_run_sync(sync_dict)
        
        