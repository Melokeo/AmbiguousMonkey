'''
uses py 3.10 w/ pyqt6
'''

import os
from PyQt6.QtWidgets import *
from ... import monkeyUnityv1_8 as mky
from ...utils.workers import SetupAniposeWorker, RunAniposeWorker
# import vid_play_v0_7 as vid_player # save for later.

class TabAnipose(QWidget):
    def __init__(self, log_area:QTextEdit):
        super().__init__()
        self.initUI()
        self.setupConnections()
        self.log_area = log_area
        
    def initUI(self):
        layout = QFormLayout(self)
        
        '''
        # this is discarded since currently we dont add points
        self.ref_table = QTableWidget()
        self.ref_table.setColumnCount(5)
        self.ref_table.setHorizontalHeaderLabels(["Cam", "Point", "X", "Y", "Scale"])
        self.populateRefTable()
        layout.addRow("Reference Points:", self.ref_table)
        
        self.scale_factor = QDoubleSpinBox()
        self.scale_factor.setValue(mky.SCALE_FACTOR)
        layout.addRow("Scale Factor:", self.scale_factor)'''

        self.chk_ani_label_combined = QCheckBox('Run `label-combined`')
        self.btn_run_ani = QPushButton('Run Anipose!')
        self.edt_anicfg = QLineEdit(mky.ani_cfg_mothercopy)
        self.btn_anicfg = QPushButton("Browse")
        self.btn_setup_ani = QPushButton('Setup anipose folder')
        lt = QHBoxLayout()
        lt.addWidget(self.edt_anicfg)
        lt.addWidget(self.btn_anicfg)
        layout.addRow(lt)
        layout.addRow(self.chk_ani_label_combined)
        lt = QHBoxLayout()
        lt.addWidget(self.btn_setup_ani)
        lt.addWidget(self.btn_run_ani)
        layout.addRow(lt)
        
    def setupConnections(self):
        self.btn_setup_ani.clicked.connect(self.setupAnipose)
        self.btn_run_ani.clicked.connect(self.runAnipose)

    def setupAnipose(self):
        if mky.pm.vid_path is None:
            print("Plz Run detect LED first") # TODO need a new logic to update pm.vid_path
            return
        
        self.btn_run_ani.setEnabled(False)
        self.btn_setup_ani.setEnabled(False)
        self.btn_setup_ani.setText('Setting up anipose folder...')

        self.setup_anipose_worker = SetupAniposeWorker(mky.pm.ani_base_path, mky.pm.vid_path)
        self.setup_anipose_worker.log_signal.connect(self.log_area.append)
        self.setup_anipose_worker.finished.connect(self.setupWorkerFinished)
        self.setup_anipose_worker.start()
    
    def setupWorkerFinished(self):
        self.setup_anipose_worker.deleteLater()
        self.btn_run_ani.setEnabled(True)
        self.btn_setup_ani.setEnabled(True)
        self.btn_setup_ani.setText('Setup anipose folder')

    def runAnipose(self):
        if not os.path.exists(os.path.join(mky.pm.ani_base_path, mky.ani_cfg_mothercopy)):
            print("RuntimeError('anipose folder not set up yet!')")
            return
        
        self.btn_run_ani.setEnabled(False)
        self.btn_setup_ani.setEnabled(False)
        self.btn_run_ani.setText('Running anipose...')

        self.run_anipose_worker = RunAniposeWorker(mky.pm.ani_base_path, self.chk_ani_label_combined.isChecked())
        self.run_anipose_worker.log_signal.connect(self.log_area.append)
        self.run_anipose_worker.finished.connect(self.aniWorkerFinished)
        self.run_anipose_worker.start()
    
    def aniWorkerFinished(self):
        self.run_anipose_worker.deleteLater()
        self.btn_run_ani.setEnabled(True)
        self.btn_setup_ani.setEnabled(True)
        self.btn_run_ani.setText('Run Anipose!')
