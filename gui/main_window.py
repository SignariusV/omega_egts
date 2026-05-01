# OMEGA_EGTS GUI
from PySide6.QtWidgets import QMainWindow

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OMEGA_EGTS Tester")
        self.resize(1024, 768)