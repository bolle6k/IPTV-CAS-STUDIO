# dashboard_gui.py

from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem)
from PySide6.QtCore import Qt
from datetime import datetime
import random

class DashboardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin-Dashboard")
        self.setMinimumSize(800, 500)
        self.init_ui()

    def init_ui(self):
        self.label_title = QLabel("Systemübersicht und Logs")
        self.label_title.setStyleSheet("font-size: 18px; font-weight: bold")

        self.stats_label = QLabel("Aktive Sessions: 0 | Letzte Rotation: -")

        self.button_refresh = QPushButton("Aktualisieren")
        self.button_refresh.clicked.connect(self.refresh_dashboard)

        self.log_table = QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["Zeit", "Aktion", "Nutzer"])
        self.log_table.horizontalHeader().setStretchLastSection(True)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.stats_label)
        top_layout.addStretch()
        top_layout.addWidget(self.button_refresh)

        layout = QVBoxLayout()
        layout.addWidget(self.label_title)
        layout.addLayout(top_layout)
        layout.addWidget(self.log_table)

        self.setLayout(layout)
        self.refresh_dashboard()

    def refresh_dashboard(self):
        sessions = random.randint(0, 100)
        now = datetime.now().strftime("%H:%M:%S")
        self.stats_label.setText(f"Aktive Sessions: {sessions} | Letzte Rotation: {now}")

        self.log_table.setRowCount(0)
        dummy_logs = [
            ("2025-06-27 14:02", "Token validiert", "admin"),
            ("2025-06-27 14:03", "EMM erstellt", "admin"),
            ("2025-06-27 14:04", "Playlist geändert", "testuser"),
        ]
        for row, (zeit, aktion, nutzer) in enumerate(dummy_logs):
            self.log_table.insertRow(row)
            self.log_table.setItem(row, 0, QTableWidgetItem(zeit))
            self.log_table.setItem(row, 1, QTableWidgetItem(aktion))
            self.log_table.setItem(row, 2, QTableWidgetItem(nutzer))
# dashboard_gui.py

from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem)
from PySide6.QtCore import Qt
from datetime import datetime
import random

class DashboardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin-Dashboard")
        self.setMinimumSize(800, 500)
        self.init_ui()

    def init_ui(self):
        self.label_title = QLabel("Systemübersicht und Logs")
        self.label_title.setStyleSheet("font-size: 18px; font-weight: bold")

        self.stats_label = QLabel("Aktive Sessions: 0 | Letzte Rotation: -")

        self.button_refresh = QPushButton("Aktualisieren")
        self.button_refresh.clicked.connect(self.refresh_dashboard)

        self.log_table = QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["Zeit", "Aktion", "Nutzer"])
        self.log_table.horizontalHeader().setStretchLastSection(True)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.stats_label)
        top_layout.addStretch()
        top_layout.addWidget(self.button_refresh)

        layout = QVBoxLayout()
        layout.addWidget(self.label_title)
        layout.addLayout(top_layout)
        layout.addWidget(self.log_table)

        self.setLayout(layout)
        self.refresh_dashboard()

    def refresh_dashboard(self):
        sessions = random.randint(0, 100)
        now = datetime.now().strftime("%H:%M:%S")
        self.stats_label.setText(f"Aktive Sessions: {sessions} | Letzte Rotation: {now}")

        self.log_table.setRowCount(0)
        dummy_logs = [
            ("2025-06-27 14:02", "Token validiert", "admin"),
            ("2025-06-27 14:03", "EMM erstellt", "admin"),
            ("2025-06-27 14:04", "Playlist geändert", "testuser"),
        ]
        for row, (zeit, aktion, nutzer) in enumerate(dummy_logs):
            self.log_table.insertRow(row)
            self.log_table.setItem(row, 0, QTableWidgetItem(zeit))
            self.log_table.setItem(row, 1, QTableWidgetItem(aktion))
            self.log_table.setItem(row, 2, QTableWidgetItem(nutzer))
