'''
Usage example for ammonkey, w/ annoying annotations
'''
# for actual usage one can simply do wildcat import actually.
# ===============================
# 1. data setup & create note obj
from ammonkey import Path, dataSetup, ExpNote, DAET, Task
# raw data folder to process. remember to use raw string r''
raw_path = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\06\20250620')

# create data folder & shortcuts
dataSetup(raw_path=raw_path)

# create note object
note = ExpNote(raw_path)

# print entries if you want
print(f'{note.data_path=}')
print('\n\t'.join(str(note.daets)))

# ===============================
# 2.1 setup vid sync
from ammonkey import VidSynchronizer, CamConfig, CamGroup

# create synchronizer
synchronizer = VidSynchronizer(note)

# set rois for LED detection
synchronizer.setROI()

# 2.2 examples for configuring camera setups 
# by default just check if cam2 LED is green or yellow; others no need to configure.
# camera indexing starts from 1, not 0
synchronizer.cam_config.led_colors[1] = 'Y'         # set cam1 detection to anticipate Yellow LED
synchronizer.cam_config.led_colors[2] = 'G'         # set cam2 detection to anticipate Green LED
synchronizer.cam_config.groups[3] = CamGroup.RIGHT  # set cam3 to belong to CamGroup.RIGHT (same as default)

# 2.3 detect then synchronize all daets
results = synchronizer.syncAll()
print(results)

# ================================================================
# now you should be able to see synchronized videos in the data_path
# sync detection are saved in SynchronizedVideos/SyncDetection
# recommend to check the audio plot to ensure correct sync.
# ================================================================

# ===============================
# 3. create DLC processor and run it.
from ammonkey import (
    DLCProcessor, DLCModel, initDlc,
    modelPreset, createProcessor_BBT, createProcessor_Brkm,
    createProcessor_Pull, createProcessor_TS,
)

# 3.1 for example we want to analyze pull-arm (4-cam setup)
dp = createProcessor_Pull(note)

# import deeplabcut. it's slow
initDlc()

# run deeplabcut analysis. takes a century.
dlc_results = dp.batchProcess()
print(dlc_results)

# 3.2 now try to run BBT (2-cam setup)
dp = createProcessor_BBT(note)
initDlc()
dlc_results = dp.batchProcess()
print(dlc_results)

# ================================================================
# now thou should see under each daet folder there is a DLC folder
# the results are collected and organized according to the model set used, 
# e.g. 'TS-LR-20250618_7637'. the last 4 digits are model set id.
# the 'separate' folder stores single model outputs
# ================================================================

# ===============================
# 4. anipose setup and run
from ammonkey import runAnipose, AniposeProcessor, getUnprocessedDlcData

# in case you dont know the model_set_name, here is a function to get unprocessed sets
model_set_names = getUnprocessedDlcData(note.data_path)
print(model_set_names)
if model_set_names:
    for msn in model_set_names:
        # quickly run anipose on a folder
        runAnipose(note, model_set_name='Brkm-20250620_5608')

        # or manually, create anipose processor object
        ap = AniposeProcessor(note, model_set_name='Brkm-20250620_5608')

        # check which config and calib will be used, etc.
        print(ap.info)

        # anipose calibration
        ap.setupCalibs()
        ap.calibrateCLI()

        # triangulate. another century passed by.
        ap.triangulateCLI()
else:
    print('no dlc data for anipose processing.')

# ================================================================
# now you should see under anipose/ there is a folder named after the model set
# inside are anipose standard 1-nested structure
# ================================================================

# collect csvs
from ammonkey import violentCollect
violentCollect(
    ani_path=ap.ani_root_path, 
    clean_path=(note.data_path / 'clean')
)

# now the csvs should be collected in data_path/clean. HAPPY???!





# ===========
# Supplements
# ===========

# playing with ExpNote
p = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\06\20250620')
note = ExpNote(p)

print(note.getAllTaskTypes())
# [<Task.BBT: 3>, <Task.CALIB: 6>, <Task.BRKM: 4>]

print(note.checkSanity())
# True

print(note.daets)
# [DAET('20250620-Pici-Calibration-0.0'), DAET('20250620-Pici-Brinkman-1.0'), DAET('20250620-Pici-Brinkman-2.0')...
print(note.getSummary())
# {'total_entries': 15, 'valid_entries': 15, 'void_entries': 0, 'calibration_entries': 1, 'processable_entries': 15}

# keep only calib and bbt
note_filtered = note.applyTaskFilter([Task.CALIB, Task.BBT])
# equivalent as excluding brkm.
note_filtered = note.applyTaskFilter([Task.BRKM], exclude=True)

print(note_filtered.getAllTaskTypes())
# [<Task.BBT: 3>, <Task.CALIB: 6>]

calib = note_filtered.daets[0]
bbt_8 = note_filtered.daets[1]
print(f'{calib=}, {bbt_8=}')
# calib=DAET('20250620-Pici-Calibration-0.0'), bbt_8=DAET('20250620-Pici-BBT-8.0')
print(f'{calib.isCalib=}, {bbt_8.isCalib=}')
# calib.isCalib=True, bbt_8.isCalib=False

note_filtered.getVidSetIdx(daet=calib)
# [1024, 971, 1184, 1146]
note_filtered.checkVideoExistence(no=1) # same as passing daet=bbt_8, cuz its index is 1
# {0: True, 1: True, 2: True, 3: True}

note_filtered.getDaetSyncRoot(daet=bbt_8)
# WindowsPath('P:/projects/monkeys/Chronic_VLL/DATA/Pici/2025/06/20250620/SynchronizedVideos/20250620-Pici-BBT-8.0')
note_filtered.getDaetDlcRoot(daet=bbt_8)
# WindowsPath('P:/projects/monkeys/Chronic_VLL/DATA/Pici/2025/06/20250620/SynchronizedVideos/20250620-Pici-BBT-8.0/DLC')