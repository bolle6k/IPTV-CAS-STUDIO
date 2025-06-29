# vlc_preview.py

import vlc
import time

class VLCPreview:
    def __init__(self, stream_url):
        self.stream_url = stream_url
        self.player = None

    def start_preview(self):
        instance = vlc.Instance()
        self.player = instance.media_player_new()
        media = instance.media_new(self.stream_url)
        self.player.set_media(media)
        self.player.play()
        print(f"[INFO] VLC-Vorschau gestartet: {self.stream_url}")

    def stop_preview(self):
        if self.player:
            self.player.stop()
            print("[INFO] VLC-Vorschau gestoppt")

if __name__ == "__main__":
    # Beispiel-Stream (lokal oder online)
    url = "http://localhost:8080/test.m3u8"
    preview = VLCPreview(url)
    preview.start_preview()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        preview.stop_preview()
