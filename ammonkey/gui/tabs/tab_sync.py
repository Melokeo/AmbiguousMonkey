'''

'''

import os
from PyQt6.QtWidgets import *
from ... import monkeyUnityv1_8 as mky
from ...utils import ROIConfig
from ...utils.workers import *
import shutil
# import vid_play_v0_7 as vid_player # save for later.

class TabSync(QWidget):
    def __init__(self, log_area:QTextEdit):
        super().__init__()
        self.initUI()
        self.setupConnections()
        self.log_area = log_area

    def showEvent(self, event):
        super().showEvent(event)
        for i, state in enumerate(mky.hascam):
            self.sync_cam_chk[i].setChecked(state) # deactivate non-existing view by default
        
    def initUI(self):
        # Sync Tab
        mky.list_skipped_file_name = ['x', '-']

        layout = QFormLayout(self)
        
        self.roi_table = QTableWidget()
        self.roi_table.setColumnCount(6)
        self.roi_table.setHorizontalHeaderLabels(["Cam", "X", "Y", "W", "H", 'LED'])
        self.populateROITable()
        self.roi_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.roi_table.setMaximumHeight(180)
        self.roi_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.roi_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addRow("Sync ROI config:", self.roi_table)

        self.sync_cam_chk:list[QCheckBox] = []
        self.sync_cam_btn_check:list[QPushButton] = []
        self.sync_cam_btn_set:list[QPushButton] = []
        self.sync_cam_cmb:list[QComboBox] = []
        for j in range(2):
            cam_layout = QHBoxLayout()
            for i in range(1,3):
                chk = QCheckBox(f"CAM {i + 2*j}")
                chk.setChecked(True)
                cam_layout.addWidget(chk)
                btn1 = QPushButton("Check ROI")
                btn2 = QPushButton("Set ROI")
                cmb = QComboBox()
                cmb.addItems(['Y', 'G'])
                cmb.setCurrentText(mky.LEDs[i + 2*j]) 
                cam_layout.addWidget(btn1)
                cam_layout.addWidget(btn2)
                cam_layout.addWidget(cmb)
                cam_layout.addStretch()
                self.sync_cam_chk.append(chk)
                self.sync_cam_btn_check.append(btn1)
                self.sync_cam_btn_set.append(btn2)
                self.sync_cam_cmb.append(cmb)
            layout.addRow("",cam_layout)
        
        self.thres = QSpinBox()
        self.thres.setRange(100, 255)
        self.thres.setValue(mky.THRES)
        self.aud_len = QSpinBox()
        self.aud_len.setRange(15, 240)
        self.aud_len.setValue(60)
        self.aud_thres = QDoubleSpinBox()
        self.aud_thres.setDecimals(2)
        self.aud_thres.setRange(1.00, 3.00)
        self.aud_thres.setSingleStep(0.01)
        self.aud_thres.setValue(mky.SyncAud.THRES_PEAK)
        ll = QHBoxLayout()
        ll.addWidget(QLabel('LED Threshold'))
        ll.addWidget(self.thres)
        ll.addWidget(QLabel('Audio Detection len (s)'))
        ll.addWidget(self.aud_len)
        ll.addWidget(QLabel('Audio Thres'))
        ll.addWidget(self.aud_thres)
        self.chk_override_sync = QCheckBox('Override existing sync')
        self.chk_override_sync.setChecked(False)
        ll.addWidget(self.chk_override_sync)
        layout.addRow(ll)

        self.btn_sync_detect = QPushButton("Detect LED")
        self.btn_sync_run = QPushButton("Run sync")
        lt = QHBoxLayout()
        lt.addWidget(self.btn_sync_detect)
        lt.addWidget(self.btn_sync_run)
        layout.addRow(lt)

    def setupConnections(self):
        self.btn_sync_detect.clicked.connect(self.btnDetect)
        self.btn_sync_run.clicked.connect(self.btnRunSync)
        for i in range(4):
            self.sync_cam_btn_set[i].clicked.connect(self.setROI)
            self.sync_cam_btn_check[i].clicked.connect(self.checkROI)
            self.sync_cam_cmb[i].currentIndexChanged.connect(self.cmbCamLED)

    def populateROITable(self):
        self.roi_table.setRowCount(0)#len(mky.ROIs))
        for i, (cam, vals) in enumerate(mky.ROIs.items()):
            self.roi_table.insertRow(i)
            self.roi_table.setItem(i, 0, QTableWidgetItem(str(cam)))
            for j in range(4):
                self.roi_table.setItem(i, j+1, QTableWidgetItem(str(vals[j])))
            self.roi_table.setItem(i, 5, QTableWidgetItem(str(mky.LEDs[i+1])))
    
    def checkROI(self):
        if self.sender() in self.sync_cam_btn_check:
            try:
                idx = self.sync_cam_btn_check.index(self.sender())
            except Exception:
                print('Alien invasion detected when trying to locate check button')   

            if mky.filename_cam_head[idx] in mky.list_skipped_file_name:
                print('Alien invasion detected when trying to determine file name')
                return
            p = os.path.join(mky.pm.PPATH_RAW, f'cam{idx+1}', mky.filename_cam_head[idx])
            r = mky.ROIs[idx+1]
            print(f'Trying to check {p}, {r}, frame {2000}!')
            ROIConfig.show_saved_rois(p, r, 2000)
                
        # ROIConfig.

    def setROI(self):
        try:
            if self.sender() in self.sync_cam_btn_set:
                idx = self.sync_cam_btn_set.index(self.sender())
                # print(idx)
                path = os.path.join(mky.pm.PPATH_RAW, f'cam{idx+1}', mky.filename_cam_head[idx])
                frame = 500
                ROI = ROIConfig.draw_roi(path, frame)
                if ROI is None:
                    # print('No ROI is selected')
                    return
                mky.ROIs[idx+1] = ROI
                print(f'Updated ROI: cam {idx} path {os.path.basename(path)} at frame {frame+1}, ROI {ROI}')
                self.populateROITable()
            else:
                print('Unidentified button!')
        except Exception as e:
            print(f'Error in self.setROI: {e}')
    
    def btnDetect(self):
        mky.dataSetup()
        mky.SyncAud.THRES_PEAK = self.aud_thres.value()
        # Threaded execution of configSync
        self.config_sync_worker = ConfigSyncWorker(
            aud_len = self.aud_len.value(),
            override = self.chk_override_sync.isChecked(),
            )
        self.config_sync_worker.log_signal.connect(self.log_area.append)
        self.config_sync_worker.return_signal.connect(self.handleConfigSyncResult)
        self.config_sync_worker.finished.connect(self.btnDetSyncDone)
        self.config_sync_worker.start()
        self.btn_sync_run.setEnabled(False)
        self.btn_sync_detect.setEnabled(False)
        self.btn_sync_run.setText('Detecting...')
        self.btn_sync_detect.setText('Detecting...')

    def handleConfigSyncResult(self, vid_path, cfg_path, calib_idx):
        mky.pm.vid_path = vid_path
        mky.pm.cfg_path = cfg_path
        mky.pm.calib_idx = calib_idx
        self.log_area.append("configSync results received. Ready for the next step.\n")
    
    def btnDetSyncDone(self):
        self.config_sync_worker.deleteLater()
        self.syncDone()
    
    def cmbCamLED(self):
        try:
            if self.sender() in self.sync_cam_cmb:
                idx = self.sync_cam_cmb.index(self.sender())
                # print(idx)
                LED = self.sync_cam_cmb[idx].currentText()
                if LED in ['Y', 'G']:
                    mky.LEDs[idx+1] = LED
                else:
                    print('sth strange happened in LED setting')
                print(f'Updated LED: cam {idx+1} LED {LED}')
                self.populateROITable()
            else:
                print('Unidentified button!')
        except Exception as e:
            print(f'Error in self.cmbCamLED: {e}')

    def btnRunSync(self):
        if not mky.pm.vid_path or not mky.pm.cfg_path:
            print('Plz wait for configSync() and run again later')
            self.btnDetect()
            return
        self.run_sync_worker = RunSyncWorker(mky.pm.vid_path, mky.pm.cfg_path)
        self.run_sync_worker.log_signal.connect(self.log_area.append)
        self.run_sync_worker.finished.connect(self.btnRunSyncDone)
        self.run_sync_worker.start()
        self.btn_sync_run.setEnabled(False)
        self.btn_sync_detect.setEnabled(False)
        self.btn_sync_run.setText('Synchronizing...')
        self.btn_sync_detect.setText('Synchronizing...')
    
    def btnRunSyncDone(self):
        self.run_sync_worker.deleteLater()
        self.syncDone()
    
    def syncDone(self):
        self.btn_sync_run.setEnabled(True)
        self.btn_sync_detect.setEnabled(True)
        self.btn_sync_run.setText('Run sync')
        self.btn_sync_detect.setText('Detect LED')

    def sendToCalib(self, vid_path_: list, folder_name=['Calib']):
        '''
        if a calibration is found recorded, set up for calib and run it
        '''
        for vp, f in vid_path_, folder_name:
            fname = os.path.join(mky.pm.ani_base_path, f, 'calibration')
            os.makedirs(fname, exist_ok=True)
            for v in os.listdir(vp):
                if mky.vid_type in v:
                    shutil.copy(os.path.join(vp, v), fname)
        shutil.copy(mky.ani_cfg_mothercopy, mky.pm.ani_base_path)
        self.run_calib_worker = RunCalibrationWorker(mky.pm.ani_base_path)
        self.run_calib_worker.log_signal.connect(self.log_area.append)
        self.run_calib_worker.finished.connect(self.run_calib_worker.deleteLater)
        self.run_calib_worker.start()

    def calibDone(self):
        # collect calibration.toml
        for dirpath, dirnames, filenames in os.walk(mky.pm.ani_base_path):
            if "calibration" in dirnames:
                calibration_path = os.path.join(dirpath, "calibration", "calibration.toml")
                if os.path.isfile(calibration_path):
                    parent_folder = os.path.basename(dirpath)
                    shutil.copy(calibration_path, os.path.join(r'C:\Users\rnel\Documents\Python Scripts\calib history', f'calibration-{parent_folder}.toml'))
                    shutil.copy(calibration_path, r'C:\Users\rnel\Documents\Python Scripts')
        self.run_calib_worker.deleteLater()