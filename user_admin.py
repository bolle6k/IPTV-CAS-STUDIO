from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QHBoxLayout, QMessageBox, QListWidget, QListWidgetItem, QComboBox)
from PySide6.QtCore import Qt
from db_helper import DBHelper

class UserAdminWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Benutzerverwaltung")
        self.setMinimumSize(600, 400)
        self.db = DBHelper()
        self.init_ui()
        self.load_users()

    def init_ui(self):
        self.label_title = QLabel("Benutzerverwaltung")
        self.label_title.setStyleSheet("font-size: 18px; font-weight: bold")

        self.user_list = QListWidget()

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Benutzername")

        self.input_hwid = QLineEdit()
        self.input_hwid.setPlaceholderText("HWID")

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Passwort")
        self.input_password.setEchoMode(QLineEdit.Password)
        
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("Email")

        self.input_paket = QComboBox()
        self.input_paket.addItems(["Basis", "Basis+", "Premium"])

        self.input_token = QLineEdit()
        self.input_token.setPlaceholderText("Token")

        self.button_add = QPushButton("Benutzer hinzufügen")
        self.button_add.clicked.connect(self.add_user)

        self.button_delete = QPushButton("Benutzer entfernen")
        self.button_delete.clicked.connect(self.delete_user)

        self.button_refresh = QPushButton("🔄 Aktualisieren")
        self.button_refresh.clicked.connect(self.load_users)

        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(self.input_name)
        hlayout1.addWidget(self.input_password)
        hlayout1.addWidget(self.input_hwid)
        
        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.input_paket)
        hlayout2.addWidget(self.input_token)
        hlayout2.addWidget(self.input_email)

        hlayout3 = QHBoxLayout()
        hlayout3.addWidget(self.button_add)
        hlayout3.addWidget(self.button_delete)
        hlayout3.addWidget(self.button_refresh)

        layout = QVBoxLayout()
        layout.addWidget(self.label_title)
        layout.addWidget(self.user_list)
        layout.addLayout(hlayout1)
        layout.addLayout(hlayout2)
        layout.addLayout(hlayout3)

        self.setLayout(layout)

    def load_users(self):
        self.user_list.clear()
        try:
            users = self.db.get_all_users()
            for name, hwid, paket, token, email in users:
                item = QListWidgetItem(f"{name} ({hwid}) [{paket}] Token: {token}")
                self.user_list.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Laden", str(e))

    def add_user(self):
        name = self.input_name.text().strip()
        pw = self.input_password.text().strip()
        hwid = self.input_hwid.text().strip()
        paket = self.input_paket.currentText()
        token = self.input_token.text().strip()
        email = self.input_email.text().strip()
        if not name or not pw or not hwid or not token:
            QMessageBox.warning(self, "Fehler", "Bitte alle Felder ausfüllen.")
            return
        try:
            self.db.add_user(name, pw, hwid, paket, token, email)
            self.load_users()
            self.input_name.clear()
            self.input_password.clear()
            self.input_hwid.clear()
            self.input_token.clear()
            self.input_email.clear()
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Hinzufügen", str(e))

    def delete_user(self):
        selected = self.user_list.currentItem()
        if selected:
            username = selected.text().split(" (")[0]
            try:
                self.db.delete_user(username)
                self.load_users()
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Löschen", str(e))
        else:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst einen Benutzer auswählen.")
