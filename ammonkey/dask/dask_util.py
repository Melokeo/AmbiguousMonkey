from ammonkey.dask.dask_scheduler import DaskScheduler
from ammonkey.dask.dask_task import DaskTask
from ammonkey.dask.dask_factory import create_ani_pipeline
from ammonkey import ExpNote, Path, getUnprocessedDlcData, AniposeProcessor as AP

def main():
    scheduler = DaskScheduler('tcp://127.0.0.1:8786')
    note = ExpNote(Path(r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\03\20250331\PICI_20250331.xlsx"))
    
    upd = getUnprocessedDlcData(note.data_path)
    if not upd or len(upd) > 1:
        print(upd)
        return
    
    tasks = create_ani_pipeline(note, model_set=upd[0])
    futures = scheduler.submit_tasks(tasks)
    results = scheduler.monitor_progress(futures)

    for r in results:
        print(f"{r.get('task_id')}: {r.get('status')}")

def create_scheduler():
    from dask.distributed import LocalCluster, Worker
    c = LocalCluster(n_workers = 0)
    cpu_worker = Worker(c.scheduler_address, resources={'cpu': 1})
    gpu_worker = Worker(c.scheduler_address, resources={'gpu': 1})

    return c

if __name__ == '__main__':
    main()