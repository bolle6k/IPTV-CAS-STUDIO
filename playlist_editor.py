# playlist_editor.py

from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QTextEdit, QPushButton,
                               QVBoxLayout, QFileDialog, QMessageBox)
import os

class PlaylistEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Playlist-Manager (M3U8)")
        self.setMinimumSize(700, 500)
        self.init_ui()

    def init_ui(self):
        self.label = QLabel("M3U8 Playlist bearbeiten oder erstellen")
        self.playlist_edit = QTextEdit()

        self.button_load = QPushButton("Playlist laden")
        self.button_load.clicked.connect(self.load_playlist)

        self.button_save = QPushButton("Playlist speichern")
        self.button_save.clicked.connect(self.save_playlist)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.playlist_edit)
        layout.addWidget(self.button_load)
        layout.addWidget(self.button_save)

        self.setLayout(layout)

    def load_playlist(self):
        filename, _ = QFileDialog.getOpenFileName(self, "M3U8-Datei laden", "", "M3U8 Dateien (*.m3u8)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.playlist_edit.setText(content)
                self.label.setText(f"Playlist geladen: {os.path.basename(filename)}")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Laden: {e}")

    def save_playlist(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Playlist speichern unter", "", "M3U8 Dateien (*.m3u8)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.playlist_edit.toPlainText())
                QMessageBox.information(self, "Gespeichert", f"Playlist gespeichert unter: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Speichern: {e}")
