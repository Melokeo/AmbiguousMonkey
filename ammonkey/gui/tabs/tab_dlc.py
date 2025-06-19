'''
uses py 3.10 w/ pyqt6
'''

import os
from PyQt6.QtWidgets import *
from ... import monkeyUnityv1_8 as mky
from ...utils.workers import ToColabWorker, FromColabWorker, RunDlcWorker
from pathlib import Path
import re
# import vid_play_v0_7 as vid_player # save for later.

class TabDLC(QWidget):
    def __init__(self, log_area:QTextEdit):
        super().__init__()
        self.initUI()
        self.setupConnections()
        self.log_area = log_area
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        self.dlc_mode = QButtonGroup()
        self.rdo_local_dlc = QRadioButton("Local DLC")
        self.rdo_colab_dlc = QRadioButton("Google Colab")
        self.dlc_mode.addButton(self.rdo_local_dlc)
        self.dlc_mode.addButton(self.rdo_colab_dlc)
        self.rdo_colab_dlc.setChecked(True)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Processing Mode:"))
        mode_layout.addWidget(self.rdo_local_dlc)
        mode_layout.addWidget(self.rdo_colab_dlc)
        layout.addLayout(mode_layout)
        
        # Local DLC Settings
        self.local_dlc_group = QGroupBox("Local DLC Settings")
        local_layout = QFormLayout()
        self.edt_dlc_cfg_pathL = QLineEdit(mky.pm.dlc_cfg_path['L'])
        self.btn_dlc_cfgL = QPushButton("Browse")
        self.cmb_mdl_L = QComboBox()
        self.edt_dlc_cfg_pathR = QLineEdit(mky.pm.dlc_cfg_path['R'])
        self.btn_dlc_cfgR = QPushButton("Browse")
        self.cmb_mdl_R = QComboBox()
        lt = QHBoxLayout()
        lt.addWidget(self.edt_dlc_cfg_pathL)
        lt.addWidget(self.btn_dlc_cfgL)
        local_layout.addRow("Config Path Left:", lt) 
        local_layout.addRow("Select model Left:", self.cmb_mdl_L)
        lt = QHBoxLayout()
        lt.addWidget(self.edt_dlc_cfg_pathR)
        lt.addWidget(self.btn_dlc_cfgR)
        local_layout.addRow("Config Path Right:", lt)
        local_layout.addRow("Select model Right:", self.cmb_mdl_R)

        self.btn_run_dlc = QPushButton('今已知汝名，汝急速去--急急如律令!!')
        local_layout.addRow(self.btn_run_dlc)

        self.local_dlc_group.setLayout(local_layout)
        layout.addWidget(self.local_dlc_group)
        
        # Colab Settings
        self.colab_group = QGroupBox("Colab Settings")
        colab_layout = QFormLayout()

        self.edt_colab_pathL = QLineEdit(mky.model_path_colab['L'])
        self.btn_colab_pathL = QPushButton("Browse")
        lt = QHBoxLayout()
        lt.addWidget(self.edt_colab_pathL)
        lt.addWidget(self.btn_colab_pathL)
        colab_layout.addRow("Colab Path Left:", lt)

        self.edt_colab_pathR = QLineEdit(mky.model_path_colab['R'])
        self.btn_colab_pathR = QPushButton("Browse")
        lt = QHBoxLayout()
        lt.addWidget(self.edt_colab_pathR)
        lt.addWidget(self.btn_colab_pathR)
        colab_layout.addRow("Colab Path Right:", lt)

        self.btn_toColab = QPushButton("Move *.mp4 to Colab")
        self.btn_fromColab = QPushButton("Fetch *.h5 from Colab")
        lt = QHBoxLayout()
        lt.addWidget(self.btn_toColab)
        lt.addWidget(self.btn_fromColab)
        colab_layout.addRow(lt)

        self.colab_group.setLayout(colab_layout)
        self.colab_group.setEnabled(False)
        layout.addWidget(self.colab_group)

        self.dlc_pane_stat_chg()
        self.dlcPathChangeL(mky.pm.dlc_mdl_path['L'])
        self.dlcPathChangeR(mky.pm.dlc_mdl_path['R'])
    
    def setupConnections(self):
        self.rdo_local_dlc.toggled.connect(self.dlc_pane_stat_chg)

        self.btn_dlc_cfgL.clicked.connect(self.btnBrowseLocalDLC_L)
        self.btn_dlc_cfgR.clicked.connect(self.btnBrowseLocalDLC_R)
        self.btn_run_dlc.clicked.connect(self.btnLocalRunDLC)

        self.btn_colab_pathL.clicked.connect(self.btnBrowseColabDLCPathL)
        self.btn_colab_pathR.clicked.connect(self.btnBrowseColabDLCPathR)
        self.btn_toColab.clicked.connect(self.toColab)
        self.btn_fromColab.clicked.connect(self.fromColab)
        # self.cmb_mdl_L.currentIndexChanged.connect()

    def dlc_pane_stat_chg(self):
        b = self.rdo_local_dlc.isChecked()
        self.colab_group.setEnabled(not b)
        self.local_dlc_group.setEnabled(b)

    def btnBrowseColabDLCPathL(self):
        #p = self.colab_pathL.text
        p = QFileDialog.getExistingDirectory(self, "Select Colab model folder LEFT", r"G:\My Drive\MonkeyModels")
        if p:
            self.edt_colab_pathL.setText(p)
            mky.model_path_colab['L'] = p
            print(f'Updated Colab DLC L to {p}')

    def btnBrowseColabDLCPathR(self):
        #p = self.colab_pathL.text
        p = QFileDialog.getExistingDirectory(self, "Select Colab model folder RIGHT", r"G:\My Drive\MonkeyModels")
        if p:
            self.edt_colab_pathR.setText(p)
            mky.model_path_colab['R'] = p
            print(f'Updated Colab DLC R to {p}')

    def toColab(self):
        if mky.pm.vid_path is None:
            print('Plz have videos synced before running DLC')
            return      # TODO here test .skipSync instead
        
        self.to_colab_worker = ToColabWorker(mky.pm.vid_path)
        self.to_colab_worker.log_signal.connect(self.log_area.append)
        self.to_colab_worker.finished.connect(self.to_colab_worker.deleteLater)
        self.to_colab_worker.start()

    def fromColab(self):
        self.from_colab_worker = FromColabWorker(mky.pm.animal, mky.pm.date)
        self.from_colab_worker.log_signal.connect(self.log_area.append)
        self.from_colab_worker.finished.connect(self.from_colab_worker.deleteLater)
        self.from_colab_worker.start()

    def btnBrowseLocalDLC_L(self):
        p = QFileDialog.getExistingDirectory(self, "Select Colab model folder Left", r"D:\DeepLabCut")  #TODO future add memory here and use edt text for default
        if p:
            try:
                mky.pm.dlc_mdl_path = {'L': p}       # looks weird but it's how pm is written
                self.edt_dlc_cfg_pathL.setText(mky.pm.dlc_cfg_path['L'])
                self.dlcPathChangeL(p)
                print(f'Updated local DLC left to {p}')
            except FileNotFoundError as e:
                QMessageBox.warning(self, 'Failed setting path', 'Config.yaml is not found in given folder')

    def btnBrowseLocalDLC_R(self):
        p = QFileDialog.getExistingDirectory(self, "Select Colab model folder RIGHT", r"D:\DeepLabCut")
        if p:
            try:
                mky.pm.dlc_mdl_path = {'R': p}       # looks weird but it's how pm is written
                self.edt_dlc_cfg_pathR.setText( mky.pm.dlc_cfg_path['R'])
                self.dlcPathChangeR(p)
                print(f'Updated local DLC right to {p}')
            except FileNotFoundError as e:
                QMessageBox.warning(self, 'Failed setting path', 'Config.yaml is not found in given folder')

    def btnLocalRunDLC(self):
        if mky.pm.vid_path is None:
            print('Plz have videos synced before running DLC')
            return      # TODO here test .skipSync instead or implement pm.vid_path logic
        
        shuffle = {}
        side = []
        if not self.cmb_mdl_L.currentData() is None:
            shuffle['L'] = self.cmb_mdl_L.currentData()['shuffle']
            side.append('L')
        if not self.cmb_mdl_R.currentData() is None:
            shuffle['R'] = self.cmb_mdl_R.currentData()['shuffle']
            side.append('R')
        if len(side)==0:
            print('[Error] No model to run!')
            return
        
        self.run_dlc_worker = RunDlcWorker(mky.pm.vid_path, shuffle=shuffle, side=side)
        self.run_dlc_worker.log_signal.connect(self.log_area.append)
        self.run_dlc_worker.finished.connect(self.dlcWorkerComplete)
        self.run_dlc_worker.start()
        self.btn_run_dlc.setEnabled(False)
        self.btn_run_dlc.setText('DLC is braising... Go grab a yogurt!')

    def dlcWorkerComplete(self):
        self.run_dlc_worker.deleteLater()
        print('Finished DLC!')
        self.btn_run_dlc.setEnabled(True)
        self.btn_run_dlc.setText('今已知汝名，汝急速去--急急如律令!!')

    def dlcPathChangeL(self, base):
        models = self.lookForModels(base)
        self.cmb_mdl_L.clear()

        if len(models) == 0:
            self.cmb_mdl_L.addItem('No available models', None)
        else:
            for mdl in models:
                self.cmb_mdl_L.addItem(mdl['model_name'], mdl)

        self.cmb_mdl_L.setCurrentIndex(self.cmb_mdl_L.count()-1)

    def dlcPathChangeR(self, base):
        models = self.lookForModels(base)
        self.cmb_mdl_R.clear()
        
        if len(models) == 0:
            self.cmb_mdl_R.addItem('No available models', None)
        else:
            for mdl in models:
                self.cmb_mdl_R.addItem(mdl['model_name'], mdl)

        self.cmb_mdl_R.setCurrentIndex(self.cmb_mdl_R.count()-1)

    def lookForModels(self, base):
        base = Path(base) / 'dlc-models'
        if not base.exists():
            return []
        
        pattern = re.compile(r"(.+)-trainset(\d+)shuffle(\d+)")

        models = []

        for iter_path in base.iterdir():
            if not iter_path.is_dir() or not iter_path.name.startswith("iteration-"):
                continue
            iteration = iter_path.name
            for model_path in iter_path.iterdir():
                if not model_path.is_dir():
                    continue
                m = pattern.fullmatch(model_path.name)
                if not m:
                    continue
                models.append({
                    'iteration': iteration,
                    'trainset_fraction': int(m.group(2)),
                    'shuffle': int(m.group(3)),
                    'model_path': model_path,
                    'model_name': model_path.name
                })

        return models