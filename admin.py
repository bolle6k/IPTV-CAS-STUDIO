
from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QHBoxLayout, QMessageBox, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt

class UserAdminWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Benutzerverwaltung")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        self.label_title = QLabel("Benutzerverwaltung")
        self.label_title.setStyleSheet("font-size: 18px; font-weight: bold")

        self.user_list = QListWidget()
        self.load_users()

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Benutzername")

        self.input_hwid = QLineEdit()
        self.input_hwid.setPlaceholderText("HWID")

        self.button_add = QPushButton("Benutzer hinzufügen")
        self.button_add.clicked.connect(self.add_user)

        self.button_delete = QPushButton("Benutzer entfernen")
        self.button_delete.clicked.connect(self.delete_user)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.input_name)
        hlayout.addWidget(self.input_hwid)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.button_add)
        button_layout.addWidget(self.button_delete)

        layout = QVBoxLayout()
        layout.addWidget(self.label_title)
        layout.addWidget(self.user_list)
        layout.addLayout(hlayout)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_users(self):
        # Placeholder für DB-Verbindung
        self.user_list.clear()
        dummy_users = [("admin", "HWID-1234"), ("testuser", "HWID-5678")]
        for name, hwid in dummy_users:
            item = QListWidgetItem(f"{name} ({hwid})")
            self.user_list.addItem(item)

    def add_user(self):
        name = self.input_name.text()
        hwid = self.input_hwid.text()
        if not name or not hwid:
            QMessageBox.warning(self, "Fehler", "Bitte Name und HWID angeben.")
            return
        item = QListWidgetItem(f"{name} ({hwid})")
        self.user_list.addItem(item)
        self.input_name.clear()
        self.input_hwid.clear()

    def delete_user(self):
        selected = self.user_list.currentItem()
        if selected:
            self.user_list.takeItem(self.user_list.row(selected))
        else:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst einen Benutzer auswählen.")
