'''

'''

import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer
from ... import monkeyUnityv1_8 as mky
from ...utils.workers import *
from datetime import datetime

class TabSetup(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.setupConnections()
        
    def initUI(self):
        mky.filename_cam_head = ['x','x','x','x']
        mky.xlsx_cam_header = ['Camera files \n(1 LR)','Camera files \n(2 LL)', 'Camera files (3 RR)', 'Camera files (4 RL)']

        l = QVBoxLayout(self)
        self.data_setup_grp = QGroupBox("Data setup")
        layout = QFormLayout()

        self.raw_path = QLineEdit(mky.pm.PPATH_RAW)
        self.btn_path_refresh = QPushButton("Refresh")
        self.btn_browse_raw = QPushButton("Browse")
        self.btn_today = QPushButton("Today")
        self.btn_data_setup = QPushButton("Setup data folder")
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.raw_path)
        path_layout.addWidget(self.btn_browse_raw)
        layout.addRow("RAW Data Path:", path_layout)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.btn_today)
        path_layout.addWidget(self.btn_path_refresh)
        layout.addRow(path_layout)
        
        self.animal_list = QLineEdit(",".join(mky.ANIMALS))
        layout.addRow("Animals:", self.animal_list)
        
        ll = QHBoxLayout()
        self.lbl_hdr_key = QLabel('Header Key:')
        self.edt_header_key = QLineEdit(mky.HEADER_KEY)
        ll.addWidget(self.lbl_hdr_key)
        ll.addWidget(self.edt_header_key)
        self.lbl_task = QLabel('Specified task:')
        self.cmb_task = QComboBox()
        # displayed_task_names = ['All', 'Touch screen', 'BBT', 'Brinkman', 'Pull']
        for t in mky.Task:
            self.cmb_task.addItem(t.name, t)
        self.cmb_task.setCurrentText('All')
        ll.addWidget(self.lbl_task)
        ll.addWidget(self.cmb_task)

        layout.addRow(ll)
        layout.addRow(self.btn_data_setup)

        self.data_setup_grp.setLayout(layout)
        l.addWidget(self.data_setup_grp)

        # Create a scrollable widget to display non-void rows
        self.non_void_scroll_area = QScrollArea()
        self.non_void_scroll_area.setWidgetResizable(True)
        
        self.non_void_container = QWidget()
        self.non_void_layout = QVBoxLayout()
        self.non_void_container.setLayout(self.non_void_layout)
        
        self.non_void_scroll_area.setWidget(self.non_void_container)
        l.addWidget(self.non_void_scroll_area)
        
        # Populate non-void rows
        self.populateNonVoidRows()

        # self.setup_tab.setLayout(l)
        
    def setupConnections(self):
        self.raw_path.returnPressed.connect(self.update_raw_path)
        self.btn_browse_raw.clicked.connect(self.browseRawPath)
        self.btn_today.clicked.connect(self.setPathToday)
        self.btn_path_refresh.clicked.connect(self.pathRefresh)
        self.btn_data_setup.clicked.connect(self.dataSetup)
        self.cmb_task.currentIndexChanged.connect(self.changeTask)
        
    def update_raw_path(self):
        mem = mky.pm.PPATH_RAW
        try:
            mky.pm.PPATH_RAW = self.raw_path.text()
        except FileNotFoundError as e:
            print(f'Cannot update path: {e}')
            print('Path **NOT** updated')
            mky.pm.PPATH_RAW = mem
            self.raw_path.setText(mky.pm.PPATH_RAW) 
            return
        try:
            if mky.pm.PPATH_RAW != mem:
                self.cmb_task.setCurrentIndex(self.cmb_task.findData(mky.Task.All))
            self.populateNonVoidRows()
        except Exception as e:
            print(f'Error updating task panes {e}')
            print('Path **NOT** updated')
            mky.pm.PPATH_RAW = mem
            self.raw_path.setText(mky.pm.PPATH_RAW)
            return
        
        print(f"Updated PPATH_RAW: {mky.pm.PPATH_RAW}")
        self.animal_list.setText(mky.pm.animal)

    def browseRawPath(self):
        path = QFileDialog.getExistingDirectory(self, "Select RAW Data Directory", r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici')
        if path:
            self.raw_path.setText(path)
            self.update_raw_path()
    
    def setPathToday(self):
        try:
            path = os.path.join(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici', datetime.today().strftime('%Y'), datetime.today().strftime('%m'), datetime.today().strftime('%Y%m%d'))
            self.raw_path.setText(path)
            self.update_raw_path()
        except Exception as e:
            print(e)

    def pathRefresh(self):
        '''animal, _ = mky._infoFromPath(mky.pm.PPATH_RAW)
        self.animal_list.setText(animal)'''
        self.update_raw_path()
    
    def dataSetup(self):
        if self.btn_data_setup.text() != 'Confirm by clicking again':
            self.btn_data_setup.setText('Confirm by clicking again')
            print(f'Will setup for {mky.pm.PPATH_RAW}!')
            QTimer.singleShot(3000, lambda: self.btn_data_setup.setText('Setup data folder'))
            # dont say its stupid!
        else:
            self.btn_data_setup.setText('Setup data folder')
            if os.path.exists(mky.pm.data_path):
                print(f'Folder already exists for {os.path.basename(mky.pm.data_path)}')
                if not os.path.exists(os.path.join(mky.pm.data_path, f'{os.path.basename(mky.pm.PPATH_RAW)}.lnk')):
                    mky.two_way_shortcuts(mky.pm.data_path, mky.pm.PPATH_RAW) # still setup folder
            else:
                mky.dataSetup()       
                mky.two_way_shortcuts(mky.pm.data_path, mky.pm.PPATH_RAW)
                print('Folder has been setup')


    def populateNonVoidRows(self):
        """Populate non-void rows inside the scroll area"""
        df = mky.readExpNote(mky.pm.PPATH_RAW, header=['Experiment Number', 'Experiment', 'Task', 'VOID',
                                                    'Camera files \n(1 LR)','Camera files \n(2 LL)', 'Camera files (3 RR)', 'Camera files (4 RL)'
                                                    ])     
        animal, date = mky.pm.animal, mky.pm.date

        if mky.curr_task != mky.Task.All:
            if not any(sub in cell.lower() for sub in mky.task_match[mky.curr_task] for cell in df['Experiment'].dropna()):
                raise ValueError(f'Cannot find any task specifying "{mky.curr_task.name}"')
            
        # Remove existing widgets
        for i in reversed(range(self.non_void_layout.count())):
            widget = self.non_void_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        flag_head = [True] * mky.ncams
        for _, row in df.iterrows():
            if row["VOID"] == "T":  # Skip void rows
                continue          
            if mky.curr_task != mky.Task.All and not any([sub in row['Experiment'].lower() for sub in mky.task_match[mky.curr_task]]):
                continue

            flag_calib = False  # display sth else for calibs.
            if any([sub in row['Experiment'].lower() for sub in mky.task_match[mky.Task.Calib]]):
                flag_calib = True

            # Create a group box for each row
            exp_group = QGroupBox(f"{row['Experiment']}-{row['Task']}")
            lt = QGridLayout()

            lt.addWidget(QLabel(f"Experiment: {row['Experiment']}"),0,0)
            lt.addWidget(QLabel(f"Task: {row['Task']}"),0,2)
            # lt.addWidget(QLabel(f"Video # From: {row['Video # From']}"),1,0)
            # lt.addWidget(QLabel(f"Video # To: {row['Video # To']}"),1,2)
  
            y = '✅'
            n = '❌'
            wng = '⚠️'
            half = '🤔'
            happy = '🎊'
            try:
                for i in range(mky.ncams):  # TODO further adopt different ncams in UI.
                    try:
                        fname = f'C{int(row[mky.xlsx_cam_header[i]]):04}.{mky.vid_type}'
                        if os.path.exists(os.path.join(mky.pm.PPATH_RAW,f'cam{i+1}',fname)):
                            c = f'{fname}'
                        else: 
                            c = f'{fname} {wng}'
                            print(f'{wng} Video not found for {row["Experiment"]}-{row["Task"]}!')
                        lt.addWidget(QLabel(f'Cam {i+1}: {c}'), 1, i)

                        if flag_head[i]:
                            mky.filename_cam_head[i] = (f'C{int(row[mky.xlsx_cam_header[i]]):04}.{mky.vid_type}')  # just used for ROI check
                        if not "calib" in row["Experiment"].lower():
                            flag_head[i] = False

                    except ValueError:
                        lt.addWidget(QLabel(f'Cam {i+1}: NOT ASSIGNED'), 1, i)

            except Exception as e:
                print(f"Error generating file name labels for {row['Experiment']}-{row['Task']}, check exp notes for cam files 1~4. {e}")

            p = os.path.join(mky.pm.data_path, 'SynchronizedVideos', f"{date}-{animal}-{row['Experiment']}-{row['Task']}")

            if not flag_calib:
                caps = ['Detected', 'Sync-ed', 'DLC processed','CSV out']
                stat = []
                stat.append(y if os.path.exists(os.path.join(p, '.skipDet')) else n)
                stat.append(y if os.path.exists(os.path.join(p, '.skipSync')) else n)
                c = sum([os.path.exists(os.path.join(p, 'L', '.skipDLC')), os.path.exists(os.path.join(p, 'R', '.skipDLC'))])
                if c == 2:
                    stat.append(y)
                elif c == 1:
                    stat.append(half)
                else:
                    stat.append(n)
                if os.path.exists(os.path.join(mky.pm.data_path, 'anipose', f"{date}-{animal}-{row['Experiment']}-{row['Task']}",
                                                            "pose-3d",
                                                            f"{date}-{animal}-{row['Experiment']}-{row['Task']}.csv")):
                    stat.append(y+happy)
                else:
                    stat.append(n)
                for i in range(4):
                    lt.addWidget(QLabel(caps[i] + stat[i]), 2, i)
            else:
                caps = ['Detected', 'Sync-ed', 'Calculated','']
                stat = []
                stat.append(y if os.path.exists(os.path.join(p, '.skipDet')) else n)
                stat.append(y if os.path.exists(os.path.join(p, '.skipSync')) else n)
                stat.append(y if os.path.exists(
                    os.path.join(
                        mky.pm.data_path, 
                        'anipose', 
                        f"{date}-{animal}-{row['Experiment']}-{row['Task']}",
                        "calibration",
                        "calibration.toml"
                        )) else n)
                stat.append('')
                for i in range(4):
                    lt.addWidget(QLabel(caps[i] + stat[i]), 2, i)
            
            exp_group.setLayout(lt)
            self.non_void_layout.addWidget(exp_group)

        self.non_void_layout.addStretch()

        mky.hascam = [not x for x in flag_head]

    def changeTask(self):
        prev_task = mky.curr_task
        mky.curr_task = self.cmb_task.currentData()
        try:
            self.populateNonVoidRows()
            print(f'Updated to {mky.curr_task.name} only')
        except ValueError as e:
            print(f'Cannot specify task: {e}')
            mky.curr_task = prev_task
            self.cmb_task.setCurrentText(prev_task.name)