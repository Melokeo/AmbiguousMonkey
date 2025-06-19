'''
uses py 3.10 w/ pyqt6
'''

import sys, time
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import QTimer, QEvent, QObject
from .. import monkeyUnityv1_8 as mky
from ..gui.style import DARK_STYLE
from datetime import datetime
from .tabs import tab_setup, tab_sync, tab_dlc, tab_anipose, tab_tool
from importlib import resources

class PipelineGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        with resources.path('ambiguousmonkey.gui', 'ambmky.ico') as icon:
            self.setWindowIcon(QIcon(str(icon)))
        
    def initUI(self):
        self.setWindowTitle("Ambiguous Monkey")
        self.setGeometry(100, 100, 750, 630)
        self.setStyleSheet(DARK_STYLE)

        self.cam_header = ['Camera files \n(1 LR)','Camera files \n(2 LL)', 'Camera files (3 RR)', 'Camera files (4 RL)']
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.adjust_tab_height)
        layout.addWidget(self.tabs)
                
        # Redirect Log text to log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)
        sys.stdout = QTextEditLogger(self.log_area)
        print('Test!')

        # Full auto part
        l = QHBoxLayout()
        self.lbl_fullauto = QLabel('Full auto (experimental)')
        self.lbl_fa_status = QLabel('idle')
        self.prg_fullauto = QProgressBar()
        self.btn_fullauto = QPushButton('Run full auto')
        self.btn_fullauto.clicked.connect(self.fullAuto)
        l.addWidget(self.lbl_fullauto)
        l.addWidget(self.lbl_fa_status)
        l.addWidget(self.prg_fullauto)
        l.addWidget(self.btn_fullauto)
        layout.addLayout(l)

        # Setup Tab
        self.tab_setup = tab_setup.TabSetup()
        self.filename_cam_head = ['x','x','x','x']
        self.tabs.addTab(self.tab_setup, "Data Setup")
        
        # Sync Tab
        self.tab_sync = tab_sync.TabSync(self.log_area)
        self.tabs.addTab(self.tab_sync, "Video Sync")
        
        # DLC Tab
        self.tab_dlc = tab_dlc.TabDLC(self.log_area)
        self.tabs.addTab(self.tab_dlc, "DeepLabCut")
        
        # Anipose Tab
        self.tab_anipose = tab_anipose.TabAnipose(self.log_area)
        self.tabs.addTab(self.tab_anipose, "Anipose")

        # Tool Tab
        self.tab_tool = tab_tool.TabTool(self.log_area)
        self.tabs.addTab(self.tab_tool, 'Tools')

        self.adjust_tab_height()

        mky.list_skipped_file_name = ['x', '-']     # idk whats this for
    
    def adjust_tab_height(self):
        """Adjust height dynamically based on the current tab's content."""
        current_tab = self.tabs.currentWidget()
        if current_tab:
            self.tabs.setFixedHeight(current_tab.sizeHint().height() + self.tabs.tabBar().height())

    def btnFullautoClicked(self):
        if self.btn_fullauto.text == 'Run full auto':
            self.btn_fullauto.text = 'Confirm full auto'
            task = self.tab_setup.cmb_task.currentText
            print(f'Confirm full auto processing of {mky.pm.animal}-{mky.pm.date}, Task-spec: {task}')
            QTimer.singleShot(3000, lambda: self.btn_fullauto.setText('Run full auto'))
        else:
            self.fullAuto()


    def fullAuto(self):
        try:
            mky.debugging = True
            self.tab_dlc.rdo_local_dlc.click()
            self.tab_setup.btn_data_setup.setText('Confirm by clicking again')
            self.tab_setup.btn_data_setup.click()
            self.chain_clicks([
                self.tab_sync.btn_sync_detect,
                self.tab_sync.btn_sync_run,
                self.tab_dlc.btn_run_dlc,
                self.tab_anipose.btn_setup_ani,
                self.tab_anipose.btn_run_ani,
                ])

        except Exception as e:
            print(f"Error when running full auto: {str(e)}")
            QMessageBox.critical(self, "Error", str(e))
    
    
    def chain_clicks(self, buttons: list[QPushButton]):
        if not buttons:
            return

        filters = []
        for i in range(1, len(buttons)):
            filt = EnabledChangeFilter(buttons[i])
            buttons[i-1].installEventFilter(filt)
            filters.append(filt)  # keep a reference during the chain run

        buttons[0].click()
        print(filters)

class EnabledChangeFilter(QObject):
    def __init__(self, next_button: QPushButton):
        super().__init__()
        self.next_button = next_button

    def eventFilter(self, obj:QPushButton, event:QEvent):
        if event.type() == QEvent.Type.EnabledChange and obj.isEnabled():
            # Trigger next button and remove filter to avoid affecting later independent runs.
            QTimer.singleShot(0, self.next_button.click)
            obj.removeEventFilter(self)
        return super().eventFilter(obj, event)

class QTextEditLogger:
    def __init__(self, text_edit:QTextEdit):
        self.text_edit = text_edit
    def write(self, message:str):
        self.text_edit.append(f"[{datetime.now().strftime('%H:%M:%S')}] " + message.strip())  # Append text to QTextEdit

    def flush(self):  # Required for sys.stdout
        pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = PipelineGUI()
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        with open(f"Log\GUI_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w", encoding="utf-8") as f:
            f.write(window.log_area.toPlainText())
