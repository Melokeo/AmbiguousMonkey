from pathlib import Path
from typing import Iterator, Union
from loguru import logger as lg

# define type alias for date inputs
DateLimit = Union[str, int, None]

def _normalize_limit(val: str | int, is_upper: bool) -> int:
    # convert input to string to determine precision
    s = str(val).strip()
    
    # helper to pad based on bounds
    # if upper bound, pad with 9s to include the full period
    # if lower bound, pad with 0s to include the start
    pad_char = '9' if is_upper else '0'
    
    if len(s) == 4: # year only, e.g. 2025
        return int(s + (pad_char * 4))
    elif len(s) == 6: # year and month, e.g. 202501
        return int(s + (pad_char * 2))
    elif len(s) >= 8: # full date or more, e.g. 20250101
        return int(s[:8])
    
    # fallback for unexpected formats, try to return as int
    try:
        return int(s)
    except ValueError:
        lg.error(f"norm limit: failed to convert {s} to integer")
        return 0 if not is_upper else 99999999

def is_day_in_range(day_val: int, start: int | None, end: int | None) -> bool:
    # check lower bound
    if start is not None and day_val < start:
        return False
    # check upper bound
    if end is not None and day_val > end:
        return False
    return True

def iterate_days(base_dir: Path, 
                 start: DateLimit = None, 
                 end: DateLimit = None) -> Iterator[Path]:
    
    # normalize range constraints once before looping
    start_norm = _normalize_limit(start, False) if start is not None else None
    end_norm = _normalize_limit(end, True) if end is not None else None
    
    # log the configuration for debugging
    lg.debug(f"scanning {base_dir} with range: {start_norm} to {end_norm}")

    if not base_dir.exists():
        lg.error(f"base directory does not exist: {base_dir}")
        return

    if not base_dir.is_dir():
        lg.error(f"path is not a directory: {base_dir}")
        return

    # iterate years
    # sort to ensure chronological order
    try:
        years = sorted([p for p in base_dir.iterdir() if p.is_dir()])
    except OSError as e:
        lg.error(f"failed to access base directory: {e}")
        return

    for year_path in years:
        # basic validation: year folder should be 4 digits
        if not year_path.name.isdigit() or len(year_path.name) != 4:
            continue

        try:
            months = sorted([p for p in year_path.iterdir() if p.is_dir()])
        except OSError as e:
            lg.warning(f"could not access year {year_path}: {e}")
            continue

        for month_path in months:
            # basic validation: month folder usually 2 digits
            if not month_path.name.isdigit():
                continue

            try:
                days = sorted([p for p in month_path.iterdir() if p.is_dir()])
            except OSError as e:
                lg.warning(f"could not access month {month_path}: {e}")
                continue

            for day_path in days:
                day_name = day_path.name
                
                # robust check: verify folder name represents a date
                if not day_name.isdigit():
                    continue
                
                # extract date integer. assuming format yyyymmdd based on example
                # if folder is just 'dd', we construct the full date from parents
                try:
                    if len(day_name) == 8:
                        day_int = int(day_name)
                    elif len(day_name) == 2:
                        # reconstruct yyyymmdd from parts
                        day_int = int(f"{year_path.name}{month_path.name}{day_name}")
                    else:
                        # skip unknown formats
                        lg.debug(f"skip folder with unexpected name: {day_path.name}")
                        continue
                except ValueError:
                    continue

                if is_day_in_range(day_int, start_norm, end_norm):
                    lg.trace(f"yielding day: {day_path}")
                    yield day_path

if __name__ == "__main__":
    # try to print some dates
    base = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici')
    for day in iterate_days(base, start='2025', end='20250331'):
        print(day.name)