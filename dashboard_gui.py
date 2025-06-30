# dashboard_gui.py

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

class DashboardWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Dashboard")
        self.resize(1024, 768)

        # WebView einrichten
        self.webview = QWebEngineView(self)
        self.webview.setUrl(QUrl("http://127.0.0.1:5000/admin"))

        # Layout
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.webview)
        self.setCentralWidget(central)
