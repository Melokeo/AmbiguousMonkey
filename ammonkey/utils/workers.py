'''
united worker class (?)
collected all the time-consuming steps in QThread here.

EmittingStream
ConfigSyncWorker
RunSyncWorker
ToColabWorker
FromColabWorker
RunDlcWorker
SetupAniposeWorker
RunAniposeWorker
RunCalibrationWorker
'''

import sys
from PyQt6.QtCore import QThread, pyqtSignal
from .. import monkeyUnityv1_8 as mky
import subprocess

ani_env = 'anipose-3d'

class EmittingStream:
    """ Redirects stdout to a PyQt signal. """
    def __init__(self, signal):
        self.signal = signal

    def write(self, text):
        if text.strip():
            self.signal.emit(str(text))

    def flush(self):
        pass  # Required for file-like objects

class ConfigSyncWorker(QThread):
    log_signal = pyqtSignal(str)
    return_signal = pyqtSignal(list, list, list)

    def __init__(self, aud_len:int, override:bool):
        super().__init__()
        self.aud_len = aud_len
        self.override = override

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Starting LED detection...")

            #if not mky.debugging:
            vid_path, cfg_path, calib_idx = mky.configSync(
                aud_test_len=self.aud_len, 
                override_skip=self.override,
                )
            #else:
                #self.log_signal.emit("Pretending to finish configSync.")

            self.return_signal.emit(vid_path, cfg_path, calib_idx)
            self.log_signal.emit("Finished LED detection\n")
        except Exception as e:
            self.log_signal.emit(f"Error during configSync: {str(e)}\n")
        finally:
            sys.stdout = original_stdout 

class RunSyncWorker(QThread):
    log_signal = pyqtSignal(str)
    # return_signal = pyqtSignal(list, list)

    def __init__(self, vid_path, cfg_path):
        super().__init__()
        self.vid_path = vid_path
        self.cfg_path = cfg_path

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Starting vid sync...")

            if not mky.debugging:
                mky.syncVid(self.vid_path, self.cfg_path)
            else:
                self.log_signal.emit("Pretending to finish sync.")

            # self.return_signal.emit(vid_path, cfg_path)
            self.log_signal.emit("Finished vid sync\n")
        except Exception as e:
            self.log_signal.emit(f"Error during Sync: {str(e)}\n")
        finally:
            sys.stdout = original_stdout 

class ToColabWorker(QThread):
    log_signal = pyqtSignal(str)
    # return_signal = pyqtSignal(list, list)

    def __init__(self, vid_path):
        super().__init__()
        self.vid_path = vid_path

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Moving videos to Colab...")
            mky.copyToGoogle(self.vid_path)
            # self.return_signal.emit(vid_path, cfg_path)
            self.log_signal.emit("Moved videos to Colab!\n")
        except Exception as e:
            self.log_signal.emit(f"Error during moving: {str(e)}\n")
        finally:
            sys.stdout = original_stdout 

class FromColabWorker(QThread):
    log_signal = pyqtSignal(str)
    # return_signal = pyqtSignal(list, list)

    def __init__(self, animal, date):
        super().__init__()
        self.animal = animal
        self.date = date

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Fetching h5 from Colab...")
            mky.pickupFromGoogle(self.animal, self.date)
            # self.return_signal.emit(vid_path, cfg_path)
            self.log_signal.emit("Fetched h5 from Colab!\n")
        except Exception as e:
            self.log_signal.emit(f"Error during moving: {str(e)}\n")
        finally:
            sys.stdout = original_stdout

class RunDlcWorker(QThread):
    log_signal = pyqtSignal(str)
    # return_signal = pyqtSignal(list, list)

    def __init__(self, vid_path, shuffle=[1, 1], side=['L','R']):
        super().__init__()
        self.vid_path = vid_path
        self.shuffle = shuffle
        self.side = side

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Starting DLC...")
            self.log_signal.emit("Check status in command lines")

            if not mky.debugging:
                mky.runDLC(self.vid_path, shuffle=self.shuffle, side=self.side)
            else:
                self.log_signal.emit("Pretending to finish DLC.")

            # self.return_signal.emit(vid_path, cfg_path)
            self.log_signal.emit("Finished DeepLabCut!\n")
        except Exception as e:
            self.log_signal.emit(f"Error during DLC: {str(e)}\n")
        finally:
            sys.stdout = original_stdout

class SetupAniposeWorker(QThread):
    log_signal = pyqtSignal(str)
    # return_signal = pyqtSignal(list, list)

    def __init__(self, ani_base_path, vid_path):
        super().__init__()
        self.ani_base_path = ani_base_path
        self.vid_path = vid_path

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Setting up anipose folder structure...")
            if not mky.debugging:
                mky.setupAnipose(self.ani_base_path, self.vid_path)
            else:
                self.log_signal.emit("Pretending to finish anipose setup.")
            # self.return_signal.emit(vid_path, cfg_path)
            self.log_signal.emit("Set up anipose folder structure!\n")
        except Exception as e:
            self.log_signal.emit(f"Error during setting up: {str(e)}\n")
        finally:
            sys.stdout = original_stdout

class RunAniposeWorker(QThread):
    log_signal = pyqtSignal(str)
    # return_signal = pyqtSignal(list, list)

    def __init__(self, ani_base_path, run_combined):
        super().__init__()
        self.ani_base_path = ani_base_path
        self.run_combined = run_combined

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Starting anipose... Don't click anything else nor exit!!")
            self.log_signal.emit("Check status in command lines")
            if not mky.debugging:
                mky.runAnipose(self.ani_base_path, self.run_combined)
            else:
                self.log_signal.emit("Pretending to finish anipose.")
            # self.return_signal.emit(vid_path, cfg_path)
            self.log_signal.emit("Finished anipose!\n")
        except Exception as e:
            self.log_signal.emit(f"Error during anipose analysis: {str(e)}\n")
        finally:
            sys.stdout = original_stdout

class RunCalibrationWorker(QThread):
    log_signal = pyqtSignal(str)
    # return_signal = pyqtSignal(list, list)

    def __init__(self, ani_base_path):
        super().__init__()
        self.ani_base_path = ani_base_path

    def run(self):
        original_stdout = sys.stdout 
        sys.stdout = EmittingStream(self.log_signal)
        try:
            self.log_signal.emit("Starting anipose calibration...")

            cmd = ['conda', 'activate', ani_env, '&&', 'P:', '&&', 'cd', self.ani_base_path, '&&',
                    'anipose', 'calibrate']
            if not mky.debugging:
                result = subprocess.run(cmd, shell=True, check=True)
            else:
                self.log_signal.emit("Pretending to finish calibration.")

            self.log_signal.emit(result.stderr)

            self.log_signal.emit("Finished anipose!\n")
        except Exception as e:
            self.log_signal.emit(f"Error during calib: {str(e)}\n")
        finally:
            sys.stdout = original_stdout