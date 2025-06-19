import sys
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from .gui.ambiguousGUI import PipelineGUI

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = PipelineGUI()
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        with open(fr"C:\Users\mkrig\Documents\GUI_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w", encoding="utf-8") as f:
            f.write(window.log_area.toPlainText())

if __name__ == "__main__":
    main()