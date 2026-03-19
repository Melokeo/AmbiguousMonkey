from ammonkey import (
    ExpNote, DAET, Path,
    iter_notes,
    getUnprocessedDlcData,
    AniposeProcessor,
    ColorLoggingFormatter,
    dataSetup,
)
from itertools import tee
from time import time, sleep as sleeep

import logging
lg = logging.getLogger(__name__)
lg.setLevel(logging.DEBUG)
lg.handlers.clear()
handler = logging.StreamHandler()
handler.setFormatter(ColorLoggingFormatter())
lg.addHandler(handler)
lg.info('test')

run: bool = True

futs = {}

#if run:
from ammonkey.dask.dask_factory import create_ani_pipeline
from ammonkey.dask.dask_scheduler import DaskScheduler
sched = DaskScheduler()

def main() -> None:
    global futs
    p = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025')
    ni1, ni2 = tee(iter_notes(p))

    need_anipose: dict[str, list[str]] = {}
    for n in ni1:
        date = n.date
        if not n.sync_path.exists():
            lg.warning(f'\033[33m{n} has no synced vid folder!\033[0m')
            continue
        udd = getUnprocessedDlcData(data_path=n.data_path)
        if udd:
            dataSetup(data_path=n.data_path)
            need_anipose[date] = udd
            if not run: continue
            try:
                for model_set in udd:
                    tasks = create_ani_pipeline(
                        note=n,
                        model_set=model_set,
                    )

                    futs |= sched.submit_tasks(tasks)

                    continue
                    ap = AniposeProcessor(n, model_set)
                    ap.setupRoot()
                    ap.setupCalibs()
                    ap.calibrateCLI()
                    ap.batchSetup()
                    ap.triangulateCLI()
            except Exception as e:
                lg.error(f'during {n.date}: {e}')

    lg.info('\033[7mdata needing anipose\033[0m')

    for date, list_model_sets in need_anipose.items():
        lg.info(f'{date}:')
        for ms in list_model_sets:
            lg.info(f'\t- {ms}')
    
    wait_for_futs()

def wait_for_futs():
    global futs
    results = sched.monitor_progress(futs)
    for i, r in enumerate(results):
        lg.info(f"{i:>4}. [{r.get('status')}] {r.get('task_id')} ({r.get('type')}): {r.get('message')}")

def looped_main() -> None:    

    def loop_blacklist_verbose(results: list[dict]) -> None:
        for i, r in enumerate(results):
            print(f"{i:>4}. [{r.get('status')}] {r.get('task_id')} ({r.get('type')}): {r.get('message')}")
            if r.get('status') == 'error':
                tid = r.get('task_id')
                if tid:
                    try:
                        stem_bad = get_task_stem(tid)
                    except Exception as e:
                        print(f'{e=}, {tid=}, bad task_id')
                    else:
                        blacklisted_model_sets.append(stem_bad)
        print_blacklist()
    
    def print_blacklist():
        print('Blacklisted entries:', end='\n\t')
        print(*blacklisted_model_sets, sep='\n\t')

    p = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025')
    notes_iterator = iter_notes(Path(p))
    blacklisted_model_sets: list[str] = []


    try:
        while True:
            start_time = time()

            ni1, notes_iterator = tee(notes_iterator, 2)
            need_anipose: dict[str, list[str]] = {}
            futs = {}
            for n in ni1:
                date = n.date
                if not n.sync_path.exists():
                    lg.warning(f'\033[33m{n} has no synced vid folder!\033[0m')
                    continue
                udd = getUnprocessedDlcData(data_path=n.data_path)

                if udd:
                    udd = [ms for ms in udd if not f'{date}_{ms}' in blacklisted_model_sets]
                    if not udd:
                        continue
                    dataSetup(data_path=n.data_path)
                    need_anipose[date] = udd
                    if not run: continue
                    try:
                        for model_set in udd:
                            tasks = create_ani_pipeline(
                                note=n,
                                model_set=model_set,
                                with_hash=True, # or same id won't be processed twice
                            )
                            print(*[t.id for t in tasks], sep='\n')
                            futs |= sched.submit_tasks(tasks)
                    except Exception as e:
                        lg.error(f'during {n.date}: {e}')

            lg.info('\033[7mdata needing anipose\033[0m')

            for date, list_model_sets in need_anipose.items():
                lg.info(f'{date}:')
                for ms in list_model_sets:
                    lg.info(f'\t- {ms}')
            
            results = sched.monitor_progress(futs)
            print('\033[7mDASK TASKS FINISHED\033[0m')

            loop_blacklist_verbose(results)
            
            sleep_time = max(0.5, 50*60 - (time() - start_time))
            print(f'waiting for next scan in {sleep_time/60:1f} mins')
            sleeep(sleep_time) # no more frequent than 30 mins/round

    except KeyboardInterrupt as e:
        print('interrupted.')
        print_blacklist()
        return
    
    
def get_task_stem(id: str) -> str:
    tail = id.split('_Pici_')[-1]
    if '@' in tail:
        tailhead = tail.split('@')[0]
    elif '#' in tail:
        tailhead = tail.split('#')[0]
    else:
        tailhead = tail
    return tailhead


if __name__ == '__main__':
    try:
        looped_main()
    except KeyboardInterrupt:
        sched.client.cancel(futs)