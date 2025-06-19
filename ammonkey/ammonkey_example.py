'''
Usage example for ammonkey
'''

from ammonkey import (
    dataSetup, ExpNote, VidSynchronizer,
    initDlc, DLCProcessor, DLCModel, modelPreset,
    createProcessor_Pull,
    AniposeProcessor, violentCollect,
    CamGroup
)

# raw data folder to process, remember to use raw string r''
raw_path = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\06\20250610'

# create data folder
dataSetup(raw_path=raw_path)

# create note object
note = ExpNote(raw_path)

# print entries if you want
print(note.data_path)
print('\n'.join(note.daets))

# create synchronizer
synchronizer = VidSynchronizer(note)

# set rois for LED detection
synchronizer.setROI()

# examples for configuring camera setups 
synchronizer.cam_config.led_colors[2] = 'Y'
synchronizer.cam_config.groups[3] = CamGroup.RIGHT

# detect then synchronize all daets
results = synchronizer.syncAll()
print(results)

# ================================================================
# now you should be able to see synchronized videos in the data_path
# sync detection are saved in SynchronizedVideos/SyncDetection
# recommend to check the audio plot to ensure correct sync.
# ================================================================

# model set dictionary, used to determine which model to use on each cam group folders
model_dict = {
    CamGroup.LEFT:  modelPreset('Pull-L'),
    CamGroup.RIGHT: modelPreset('Pull-R'),
}

# create dlc processor object
dp = DLCProcessor(note, model_dict=model_dict)

# or, just use preset defined in the package
dp = createProcessor_Pull(note)

# import deeplabcut. it's slow
initDlc()

# run deeplabcut analysis. takes a century.
dlc_results = dp.batchProcess()
print(dlc_results)

# ================================================================
# now thou should see under each daet folder there is a DLC folder
# the results are collected and organized according to the model set used, 
# e.g. 'TS-LR-20250618_7637'. the last 4 digits are model set id.
# the 'separate' folder stores single model outputs
# ================================================================

# create anipose processor object
ap = AniposeProcessor(note)

# check which config will be used, etc.
print(ap.info)

# anipose calibration
ap.setupCalibs()
ap.calibrate()

# triangulate. another century passed by.
ap.triangulate()

# ================================================================
# now you should see under anipose/ there is a folder named after the model set
# inside are anipose standard 1-nested structure
# ================================================================

# collect csvs
violentCollect(
    ani_path=ap.ani_root_path, 
    clean_path=(note.data_path / 'clean')
)

# now the csvs should be collected in data_path/clean. HAPPY???