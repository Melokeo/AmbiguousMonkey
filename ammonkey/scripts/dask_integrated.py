"""
Dask-based pipeline driver for the AmbiguousMonkey workflow.

This script submits the main processing steps (sync, dlc, anipose)
as a dependency-chained pipeline to a Dask scheduler.

Usage:
1. Start Dask scheduler and workers in separate terminals.
   - dask scheduler
   - dask worker tcp://127.0.0.1:8786 --resources "GPU=1" --nprocs 1
   - dask worker tcp://127.0.0.1:8786 --nprocs 1
2. Run this script.
"""
from typing import Any
from pathlib import Path
from dask.distributed import Client

# Import necessary objects and functions from your project
from ammonkey import (
    dataSetup, ExpNote, VidSynchronizer, SyncResult,
    initDlc, DLCProcessor, AniposeProcessor, runAnipose,
    violentCollect, createProcessor_Pull
)

# --- Wrapper Functions to Define Task Dependencies ---

def run_sync_task(synchronizer: VidSynchronizer) -> list[SyncResult]:
    """Dask Task: Runs the video synchronization step."""
    print("WORKER: Starting video synchronization...")
    results = synchronizer.syncAll()
    print("WORKER: Video synchronization finished.")
    return results

def run_dlc_task(sync_results: list[SyncResult], dlc_processor: DLCProcessor) -> dict[Any, bool]:
    """Dask Task: Initializes DLC and runs analysis.
    Waits for sync_results to be ready before starting.
    """
    print("WORKER: Sync finished. Initializing DLC...")
    initDlc()  # Initialize DLC on the worker
    print("WORKER: Starting DLC analysis...")
    dlc_results = dlc_processor.batchProcess()
    print("WORKER: DLC analysis finished.")
    return dlc_results

def run_anipose_task(dlc_results: dict[Any, bool], note: ExpNote, model_set_name: str) -> AniposeProcessor:
    """Dask Task: Runs the Anipose triangulation step.
    Waits for dlc_results to be ready before starting.
    """
    print("WORKER: DLC finished. Starting Anipose triangulation...")
    # The runAnipose function returns the processor instance
    anipose_processor: AniposeProcessor = runAnipose(note, model_set_name)
    print("WORKER: Anipose triangulation finished.")
    return anipose_processor

def run_collect_task(anipose_processor: AniposeProcessor, clean_path: Path) -> str:
    """Dask Task: Collects the final CSV files."""
    print("WORKER: Anipose finished. Collecting final CSVs...")
    violentCollect(ani_path=anipose_processor.ani_root_path, clean_path=clean_path)
    return "SUCCESS: Pipeline finished."

# --- Main Execution Block ---

def main():
    """Main function to set up and submit the pipeline."""
    # 1. INITIAL BLOCKING SETUP (Same as original script)
    raw_path = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\06\20250620')
    dataSetup(raw_path=raw_path)
    note = ExpNote(raw_path)
    print(f"Loaded note for: {note.data_path}")

    # This manual GUI step must be completed before submitting the pipeline
    print("Please set the ROIs for LED detection in the GUI window that pops up.")
    vs = VidSynchronizer(note)
    vs.setROI()
    print("ROIs set. Submitting pipeline to Dask cluster...")

    # Create the DLC processor instance
    dp: DLCProcessor = createProcessor_Pull(note)

    # 2. DASK PIPELINE SUBMISSION
    client = Client('tcp://127.0.0.1:8786')

    # a) Submit the sync task (GPU-intensive)
    sync_future = client.submit(
        run_sync_task, vs,
        resources={"GPU": 1}, pure=False
    )

    # b) Submit the DLC task (GPU-intensive), chained to the sync task
    dlc_future = client.submit(
        run_dlc_task, sync_future, dp,
        resources={"GPU": 1}, pure=False
    )

    # c) Submit the Anipose task (CPU-intensive), chained to the DLC task
    # NOTE: The anipose model_set_name needs to be determined here.
    # It is hardcoded as in the original example.
    model_set_name = 'Pull-LR-20250620_7737' # Example name
    anipose_future = client.submit(
        run_anipose_task, dlc_future, note, model_set_name,
        pure=False
    )

    # d) Submit the final collection task, chained to the Anipose task
    clean_path = note.data_path / 'clean'
    collect_future = client.submit(
        run_collect_task, anipose_future, clean_path,
        pure=False
    )

    print("\n   All pipeline steps have been submitted to the Dask cluster!")
    print("   The workers will continue processing in the background.")
    print("   Monitor progress at the Dask dashboard: http://localhost:8787\n")

    # 3. (Optional) Wait for the final result
    print("Waiting for the final task to complete...")
    final_status: str = collect_future.result()
    print(f"\n{final_status}")

    client.close()

if __name__ == "__main__":
    main()