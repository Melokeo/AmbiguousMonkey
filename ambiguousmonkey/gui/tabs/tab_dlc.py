'''
uses py 3.10 w/ pyqt6
'''

from PyQt6.QtWidgets import *
from ... import monkeyUnityv1_8 as mky
from ...utils.workers import ToColabWorker, FromColabWorker
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
        self.local_dlc = QRadioButton("Local DLC")
        self.colab_dlc = QRadioButton("Google Colab")
        self.dlc_mode.addButton(self.local_dlc)
        self.dlc_mode.addButton(self.colab_dlc)
        self.colab_dlc.setChecked(True)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Processing Mode:"))
        mode_layout.addWidget(self.local_dlc)
        mode_layout.addWidget(self.colab_dlc)
        layout.addLayout(mode_layout)
        
        # Local DLC Settings
        self.local_dlc_group = QGroupBox("Local DLC Settings")
        local_layout = QFormLayout()
        self.edt_dlc_cfg_pathL = QLineEdit(mky.dlc_mdl_path['L'])
        self.btn_dlc_cfgL = QPushButton("Browse")
        self.edt_dlc_cfg_pathR = QLineEdit(mky.dlc_mdl_path['R'])
        self.btn_dlc_cfgR = QPushButton("Browse")
        lt = QHBoxLayout()
        lt.addWidget(self.edt_dlc_cfg_pathL)
        lt.addWidget(self.btn_dlc_cfgL)
        local_layout.addRow("Config Path Left:", lt) 
        lt = QHBoxLayout()
        lt.addWidget(self.edt_dlc_cfg_pathR)
        lt.addWidget(self.btn_dlc_cfgR)
        local_layout.addRow("Config Path Right:", lt)

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
    
    def setupConnections(self):
        self.local_dlc.toggled.connect(self.dlc_pane_stat_chg)

        self.btn_dlc_cfgL.clicked.connect(self.btnBrowseLocalDLC_L)
        self.btn_dlc_cfgR.clicked.connect(self.btnBrowseLocalDLC_R)
        self.btn_run_dlc.clicked.connect(self.btnLocalRunDLC)

        self.btn_colab_pathL.clicked.connect(self.btnBrowseColabDLCPathL)
        self.btn_colab_pathR.clicked.connect(self.btnBrowseColabDLCPathR)
        self.btn_toColab.clicked.connect(self.toColab)
        self.btn_fromColab.clicked.connect(self.fromColab)

    def dlc_pane_stat_chg(self):
        b = self.local_dlc.isChecked()
        self.colab_group.setEnabled(not b)
        self.local_dlc_group.setEnabled(b)

    def btnBrowseColabDLCPathL(self):
        #p = self.colab_pathL.text
        p = QFileDialog.getExistingDirectory(self, "Select Colab model folder LEFT", r"G:\My Drive\MonkeyModels")
        if p:
            self.edt_colab_pathL.setText(p)
            mky.model_path_colab['L'] = p

    def btnBrowseColabDLCPathR(self):
        #p = self.colab_pathL.text
        p = QFileDialog.getExistingDirectory(self, "Select Colab model folder RIGHT", r"G:\My Drive\MonkeyModels")
        if p:
            self.edt_colab_pathR.setText(p)
            mky.model_path_colab['R'] = p

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
        pass

    def btnBrowseLocalDLC_R(self):
        pass

    def btnLocalRunDLC(self):
        pass