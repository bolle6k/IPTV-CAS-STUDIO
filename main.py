import sys
import threading
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QPushButton, QComboBox, QTextEdit, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QInputDialog, QHBoxLayout
)
from configparser import ConfigParser
import os

from user_admin import UserAdminWindow
from ecm_emm_gui import ECMEMMWindow
from playlist_editor import PlaylistEditor
from dashboard_gui import DashboardWindow
from aes_hls import AESHLSManager
from db_helper import DBHelper

CONFIG_PATH = "config/config.ini"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPTV CAS Studio")
        self.setGeometry(200, 200, 1100, 800)
        self.drm_output = None
        self.db = DBHelper()
        self.init_ui()
        self.load_config()
        self.start_key_rotation()

    def init_ui(self):
        main_layout = QVBoxLayout()

        self.label = QLabel("Willkommen im IPTV CAS Studio")
        main_layout.addWidget(self.label)

        self.language_selector = QComboBox()
        self.language_selector.addItems(["Deutsch", "English"])
        self.language_selector.currentIndexChanged.connect(self.change_language)
        main_layout.addWidget(self.language_selector)

        btn_layout = QHBoxLayout()

        self.button_open_user_admin = QPushButton("Benutzerverwaltung")
        self.button_open_user_admin.clicked.connect(self.open_user_admin)
        btn_layout.addWidget(self.button_open_user_admin)

        self.button_open_ecm_emm = QPushButton("ECM/EMM Verwaltung")
        self.button_open_ecm_emm.clicked.connect(self.open_ecm_emm)
        btn_layout.addWidget(self.button_open_ecm_emm)

        self.button_open_drm = QPushButton("DRM-Manager (AES-HLS)")
        self.button_open_drm.clicked.connect(self.open_drm_manager)
        btn_layout.addWidget(self.button_open_drm)

        self.button_open_playlist = QPushButton("Playlist-Manager")
        self.button_open_playlist.clicked.connect(self.open_playlist_manager)
        btn_layout.addWidget(self.button_open_playlist)

        self.button_open_dashboard = QPushButton("Admin-Dashboard")
        self.button_open_dashboard.clicked.connect(self.open_dashboard)
        btn_layout.addWidget(self.button_open_dashboard)

        main_layout.addLayout(btn_layout)

        # DRM-Log Ausgabe
        self.drm_output = QTextEdit()
        self.drm_output.setReadOnly(True)
        self.drm_output.setPlaceholderText("DRM-Log erscheint hier…")
        main_layout.addWidget(self.drm_output)

        # Watermark-Manager UI
        wm_label = QLabel("Watermark Verwaltung")
        wm_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 15px;")
        main_layout.addWidget(wm_label)

        wm_btn_layout = QHBoxLayout()
        self.btn_add_watermark = QPushButton("Watermark hinzufügen")
        self.btn_add_watermark.clicked.connect(self.add_watermark)
        wm_btn_layout.addWidget(self.btn_add_watermark)

        self.btn_toggle_watermark = QPushButton("Sichtbarkeit umschalten")
        self.btn_toggle_watermark.clicked.connect(self.toggle_visibility)
        wm_btn_layout.addWidget(self.btn_toggle_watermark)

        main_layout.addLayout(wm_btn_layout)

        self.wm_list = QListWidget()
        main_layout.addWidget(self.wm_list)

        self.load_watermarks()

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def load_config(self):
        self.config = ConfigParser()
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            self.config["Einstellungen"] = {"Sprache": "Deutsch"}
            with open(CONFIG_PATH, 'w') as f:
                self.config.write(f)
        else:
            self.config.read(CONFIG_PATH)
            sprache = self.config.get("Einstellungen", "Sprache", fallback="Deutsch")
            index = self.language_selector.findText(sprache)
            if index != -1:
                self.language_selector.setCurrentIndex(index)

    def change_language(self):
        selected = self.language_selector.currentText()
        self.config.set("Einstellungen", "Sprache", selected)
        with open(CONFIG_PATH, 'w') as f:
            self.config.write(f)
        print(f"Sprache geändert zu: {selected}")

    def open_user_admin(self):
        self.user_admin_window = UserAdminWindow()
        self.user_admin_window.show()

    def open_ecm_emm(self):
        self.ecm_emm_window = ECMEMMWindow()
        self.ecm_emm_window.show()

    def open_drm_manager(self):
        drm = AESHLSManager()
        key = drm.generate_key()
        keyinfo = drm.write_keyinfo()
        self.drm_output.append(f"Neuer Key generiert: {key}")
        self.drm_output.append(f"Keyinfo-Datei: {keyinfo}\n")

    def open_playlist_manager(self):
        self.playlist_window = PlaylistEditor()
        self.playlist_window.show()

    def open_dashboard(self):
        self.dashboard_window = DashboardWindow()
        self.dashboard_window.show()

    def start_key_rotation(self):
        def rotate_loop():
            interval = int(self.config.get("DRM", "Key_Rotation_Minuten", fallback="60"))
            drm = AESHLSManager()
            while True:
                time.sleep(interval * 60)
                path = drm.rotate_key()
                if self.drm_output:
                    self.drm_output.append(f"[Auto] Neuer Schlüssel gespeichert: {path}")
        thread = threading.Thread(target=rotate_loop, daemon=True)
        thread.start()

    def load_watermarks(self):
        self.wm_list.clear()
        watermarks = self.db.get_watermarks()
        for wm in watermarks:
            visible_text = "Ja" if wm[4] else "Nein"
            item_text = f"ID: {wm[0]} | {wm[1]} | Position: {wm[3]} | Sichtbar: {visible_text}"
            item = QListWidgetItem(item_text)
            item.setData(1000, wm[0])  # wm_id
            self.wm_list.addItem(item)

    def add_watermark(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Wähle Watermark-Bild", "", "Bilder (*.png *.jpg *.jpeg *.gif)")
        if fname:
            basename = os.path.basename(fname)
            save_dir = os.path.join(os.getcwd(), "static", "watermarks")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, basename)
            try:
                with open(fname, "rb") as fsrc, open(save_path, "wb") as fdst:
                    fdst.write(fsrc.read())
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Datei konnte nicht kopiert werden: {e}")
                return

            name, ok = QInputDialog.getText(self, "Name", "Name für Watermark:")
            if not ok or not name.strip():
                name = basename
            position, ok = QInputDialog.getItem(self, "Position", "Position:", ["top-left", "top-right", "bottom-left", "bottom-right"], 3, False)
            if not ok:
                position = "bottom-right"

            self.db.add_watermark(name.strip(), save_path, position, True)
            self.load_watermarks()

    def toggle_visibility(self):
        item = self.wm_list.currentItem()
        if not item:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Watermark auswählen.")
            return
        wm_id = item.data(1000)
        watermarks = self.db.get_watermarks()
        visible = None
        for wm in watermarks:
            if wm[0] == wm_id:
                visible = wm[4]
                break
        if visible is None:
            QMessageBox.warning(self, "Fehler", "Watermark nicht gefunden.")
            return
        self.db.update_watermark(wm_id, visible=not visible)
        self.load_watermarks()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
