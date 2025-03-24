'''
uses py 3.10 w/ pyqt6
'''

import sys
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QFont, QIcon
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

    def fullAuto(self):
        try:
            pass
            
        except Exception as e:
            self.log_area.append(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", str(e))

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
