"""
Test script for the Dask-based pipeline using the mimic library.
This version fixes the hanging issue by creating processor objects on the
workers, which avoids serialization problems.
"""
import tempfile
import shutil
from pathlib import Path
from typing import List

from dask.distributed import Client, progress

from ammonkey import (
    dataSetup, ExpNote, VidSynchronizer, DAET,
    initDlc, DLCProcessor, AniposeProcessor, runAnipose,
    violentCollect, createProcessor_Pull
)

# --- Wrapper functions now create their own objects ---

def run_sync_for_daet(raw_path: str, daet: DAET) -> str:
    """Worker task: Creates its own objects to run sync."""
    print(f"WORKER: Sync task started for {daet}")
    note = ExpNote(raw_path)
    synchronizer = VidSynchronizer(note)
    # In a real scenario, you might need to re-run setROI if it's not saved
    # synchronizer.setROI() 
    synchronizer.syncAll(task=str(daet))
    print(f"WORKER: Sync task finished for {daet}")
    return f"synced_{daet}"

def run_dlc_for_daet(sync_status: str, raw_path: str, daet: DAET) -> str:
    """Worker task: Creates its own objects to run DLC."""
    print(f"WORKER: DLC task started for {daet}")
    note = ExpNote(raw_path)
    dlc_processor = createProcessor_Pull(note)
    initDlc()
    dlc_processor.analyzeSingleDaet(daet)
    print(f"WORKER: DLC task finished for {daet}")
    return f"analyzed_{daet}"

def run_anipose_for_daet(dlc_status: str, raw_path: str, daet: DAET, model_set_name: str) -> str:
    """Worker task: Creates its own objects to run Anipose."""
    print(f"WORKER: Anipose task started for {daet}")
    note = ExpNote(raw_path)
    # Filter the note to the specific DAET for this task
    single_daet_note = note.dupWithWhiteList([daet])
    anipose_processor = runAnipose(single_daet_note, model_set_name)
    # Return a simple path string instead of the whole object
    result_path = str(anipose_processor.ani_root_path)
    print(f"WORKER: Anipose task finished for {daet}")
    return result_path

def run_collect_for_daet(anipose_result_path: str, raw_path: str) -> str:
    """Worker task: Collects final files."""
    print(f"WORKER: Collect task started for {anipose_result_path}")
    note = ExpNote(raw_path)
    clean_path = note.data_path / 'clean'
    violentCollect(ani_path=Path(anipose_result_path), clean_path=clean_path)
    return f"Collected {Path(anipose_result_path).name}"


# --- Main Execution Block ---

def main():
    """Main function to set up and submit the test pipeline."""
    temp_dir = tempfile.mkdtemp(prefix="ammonkey_test_")
    print(f"Created temporary directory for test: {temp_dir}")

    try:
        # 1. INITIAL SETUP (Client-side)
        # The client only needs to know the path and get the list of DAETs
        raw_path = temp_dir
        dataSetup(raw_path=raw_path)
        note = ExpNote(raw_path)
        valid_daets = note.getValidDaets()

        # Simulate the one-time GUI interaction
        print("Simulating ROI selection...")
        VidSynchronizer(note).setROI()
        print("Submitting test pipeline to Dask cluster...")

        client = Client('tcp://127.0.0.1:8786')

        # 2. DASK PIPELINE SUBMISSION
        final_futures: List = []
        model_set_name = 'TestModelSet'

        print(f"\nSubmitting {len(valid_daets)} mock DAETs to the pipeline...")

        for daet in valid_daets:
            # Pass simple, serializable arguments (str, DAET) to the workers
            sync_future = client.submit(run_sync_for_daet, raw_path, daet, resources={"GPU": 1}, pure=False)
            dlc_future = client.submit(run_dlc_for_daet, sync_future, raw_path, daet, resources={"GPU": 1}, pure=False)
            anipose_future = client.submit(run_anipose_for_daet, dlc_future, raw_path, daet, model_set_name, pure=False)
            collect_future = client.submit(run_collect_for_daet, anipose_future, raw_path, pure=False)
            
            final_futures.append(collect_future)

        print("\n🚀 All mock DAET processing chains have been submitted!")
        print("   Monitor progress at the Dask dashboard: http://localhost:8787\n")

        # 3. Wait for all tasks to complete
        print("Waiting for all tasks to complete...")
        progress(final_futures)

        print("\nSUCCESS: All mock DAETs have been processed.")
        client.close()

    finally:
        # Clean up the temporary directory
        print(f"Cleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
