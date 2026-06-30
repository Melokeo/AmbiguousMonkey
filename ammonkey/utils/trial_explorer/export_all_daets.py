'''
util for trial management:
pass animal dir, create a csv file with all valid daets
e.g. P:/projects/monkeys/Remyelination/DATA/Pepe
'''

import csv
from typing import Iterator
from rich import print
from pathlib import Path

from ammonkey import ExpNote, DAET

def iter_date_from_animal_dir(animal_dir: Path) -> Iterator[Path]:
    for year in animal_dir.iterdir():
        if not year.is_dir() or not year.name.isdigit():
            continue
        for mo in year.iterdir():
            if not mo.is_dir() or not mo.name.isdigit() or int(mo.name) > 12:
                continue
            for day in mo.iterdir():
                if not day.is_dir() or not day.name.isdigit() or len(day.name) != 8:
                    continue
                yield day

def main() -> None:
    path = Path(r'P:/projects/monkeys/Remyelination/DATA_RAW/Pepe')

    rows: list[dict] = []
    for day in iter_date_from_animal_dir(path):
        try:
            note = ExpNote(day)
            valid_daets = note.getValidDaets()
            note.dupWithWhiteList(valid_daets)
            print(f'{day} [dim]{note.getAllTaskTypes()}[/dim]')
            
            # make rows for this note
            for daet in valid_daets:
                rows.append({
                    'daet': str(daet),
                    'date': daet.date,
                    'animal': daet.animal,
                    'exp': daet.experiment,
                    'trial': daet.task,
                    'task-type': daet.task_type.name if daet.task_type else 'Unknown',
                })

        except FileNotFoundError as e:
            print(f'{day}  [dim red] Exists but failed to load[/dim red] ([dim]{e}[/dim])')

    # sort by daet before writing
    rows.sort(key=lambda r: r['daet'])
    
    # write to csv
    with open('pepe-daets.csv', 'w', newline='') as csvfile:
        fieldnames = ['daet', 'date', 'animal', 'exp', 'trial', 'task-type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print('[bold green]OK[/bold green]')

if __name__ == '__main__':
    main()