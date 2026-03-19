from ammonkey.core.daet import DAET, Task
from ammonkey import ExpNote
from pathlib import Path

def print_all_tasks(dir_to_check: Path) -> None:
    out = []

    for date in dir_to_check.glob('*'):
        if not date.is_dir() or not date.name.isnumeric():
            continue
        print(date.name, end='\r')
        try:
            n = ExpNote(date)
        except FileNotFoundError as e:
            continue

        tasks = n.getAllTaskTypes()
        out.append(f'{n.animal}\t{n.date}\t{", ".join([t.name for t in sorted(tasks, key=lambda x: x.value) if t != Task.CALIB])}')

    out = sorted(out)
    print('')
    for line in out:
        print(line)

def main()->None:
    for mo in ['08', '09', '10']:
        dir_to_check = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Fusillo\2025') / mo
        print_all_tasks(dir_to_check)

if __name__=='__main__':
    main()