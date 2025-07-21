'''
usage: in main(), change tasks_to_check list to tasks you want to check.
and also change output path.
'''

import logging
from tqdm import tqdm
import csv

from ammonkey import (
    ExpNote, DAET, Path,
    Task, iter_notes, 
    initDlc, createProcessor_Pull,
)
from ammonkey.utils.silence import silence

lg = logging.getLogger(__name__)
lg.setLevel(logging.DEBUG)

def export_daet_csv(daet_list: list[DAET], out_path: str|Path):
    out_path = Path(out_path)
    if out_path.is_dir():
        out_path = out_path / 'all_tasks.csv'
    daet_list = sorted(daet_list, key=lambda x: x.date)

    with out_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Experiment-Task'])
        prev_date = None
        for d in daet_list:
            date_str = d.date if d.date != prev_date else ''
            writer.writerow([date_str, f"{d.experiment}-{d.task}"])
            prev_date = d.date

def get_year_tasks(year_path:Path, tasks_to_check:list[Task]) -> dict[Task, list[DAET]]:
    tasks: dict[Task, list[DAET]] = {}
    for task in tasks_to_check:
        tasks[task] = []
        
    for note in iter_notes(year_path):
        task_types = note.getAllTaskTypes()
        if not note.checkSanity():
            lg.warning(f'{note=}, San={note.checkSanity()}, Tasks={task_types}')

        for task in tasks_to_check:
            note_filtered = note.applyTaskFilter([task])
            daets_str = [str(d) for d in note_filtered.daets]
            tasks[task].extend([DAET.fromString(d) for d in sorted(daets_str)])
        
        continue

    return tasks

def main()->None:
    p = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
    p = Path(p)

    '''for t in tasks:
        print(t)'''

    tasks = get_year_tasks(p, tasks_to_check=[
        Task.BRKM, Task.TS, Task.PULL, Task.BBT
    ])

    for task in tasks.keys():
        export_daet_csv(tasks[task], out_path=rf'C:\Users\mkrig\Downloads\all_{task.name}.csv')

if __name__=='__main__':
    main()