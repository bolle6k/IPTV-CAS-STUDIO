# ecm_emm_gui.py

from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QHBoxLayout, QMessageBox, QTextEdit)
from PySide6.QtCore import Qt

class ECMEMMWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECM/EMM Verwaltung")
        self.setMinimumSize(700, 500)
        self.init_ui()

    def init_ui(self):
        self.label_title = QLabel("ECM/EMM Verwaltung")
        self.label_title.setStyleSheet("font-size: 18px; font-weight: bold")

        self.input_key = QLineEdit()
        self.input_key.setPlaceholderText("Session Key eingeben (AES-128 Hex)")

        self.input_entitlement = QLineEdit()
        self.input_entitlement.setPlaceholderText("Entitlement (z. B. Paketkennung)")

        self.button_generate_ecm = QPushButton("ECM generieren")
        self.button_generate_ecm.clicked.connect(self.generate_ecm)

        self.button_generate_emm = QPushButton("EMM generieren")
        self.button_generate_emm.clicked.connect(self.generate_emm)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.input_key)
        hlayout.addWidget(self.input_entitlement)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.button_generate_ecm)
        button_layout.addWidget(self.button_generate_emm)

        layout = QVBoxLayout()
        layout.addWidget(self.label_title)
        layout.addLayout(hlayout)
        layout.addLayout(button_layout)
        layout.addWidget(self.output_box)

        self.setLayout(layout)

    def generate_ecm(self):
        key = self.input_key.text()
        entitlement = self.input_entitlement.text()
        if not key or not entitlement:
            QMessageBox.warning(self, "Fehler", "Bitte Key und Entitlement eingeben.")
            return
        # Platzhalter für echte ECM-Erzeugung
        ecm = f"ECM-Block für {entitlement} mit Key {key} erzeugt."
        self.output_box.append(ecm)

    def generate_emm(self):
        key = self.input_key.text()
        entitlement = self.input_entitlement.text()
        if not key or not entitlement:
            QMessageBox.warning(self, "Fehler", "Bitte Key und Entitlement eingeben.")
            return
        # Platzhalter für echte EMM-Erzeugung
        emm = f"EMM-Block für {entitlement} mit Key {key} erzeugt."
        self.output_box.append(emm)
