
import tkinter as tk
from tkinter import ttk
from datetime import datetime

class DashboardGUI(tk.Tk):
    def __init__(self, api_client):
        super().__init__()
        self.api = api_client
        self.title("Admin Dashboard (GUI)")
        self.geometry("1024x768")
        self.create_widgets()
        self.refresh_data()

    def create_widgets(self):
        # Top Frame: Filter
        top = ttk.Frame(self, padding="10")
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Paket:").pack(side=tk.LEFT)
        self.paket_var = tk.StringVar()
        ttk.Combobox(top, textvariable=self.paket_var,
                     values=["", "Basis", "Basis+", "Premium"], width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(top, text="HWID:").pack(side=tk.LEFT)
        self.hwid_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.hwid_var, width=15).pack(side=tk.LEFT, padx=5)

        ttk.Label(top, text="Token:").pack(side=tk.LEFT)
        self.token_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.token_var, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Button(top, text="Filter anwenden", command=self.refresh_data).pack(side=tk.LEFT, padx=5)

        # Middle Frame: Table of Users
        mid = ttk.Frame(self, padding="10")
        mid.pack(fill=tk.BOTH, expand=True)

        columns = ("username", "hwid", "active_packages", "token", "email")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.replace("_", " ").title())
            self.tree.column(col, width=150)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Frame: Controls
        bot = ttk.Frame(self, padding="10")
        bot.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(bot, text="Manuelle Schlüsselrotation", command=self.manual_rotate).pack(side=tk.LEFT, padx=5)
        ttk.Button(bot, text="Backup erstellen", command=self.trigger_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(bot, text="Daten neu laden", command=self.refresh_data).pack(side=tk.RIGHT, padx=5)

    def refresh_data(self):
        # Holt gefilterte Nutzerdaten vom Server und zeigt sie an
        paket = self.paket_var.get() or None
        hwid = self.hwid_var.get()
        token = self.token_var.get()
        users = self.api.list_users(paket_filter=paket, hwid_filter=hwid, token_filter=token)
        # users ist Liste von Dicts: {'user':(...), 'subscriptions':[...], 'best':...}
        self.tree.delete(*self.tree.get_children())
        for u in users:
            subs = ", ".join(f"{s['paket']} ({s['rest_days']}d)" for s in u['subscriptions'])
            self.tree.insert("", tk.END, values=(
                u['user'][0], u['user'][1], subs, u['user'][3], u['user'][4]
            ))

    def manual_rotate(self):
        # manuelle Rotation auslösen
        self.api.rotate_key()
        tk.messagebox.showinfo("Rotation", "Neue Schlüsselrotation ausgelöst")
        self.refresh_data()

    def trigger_backup(self):
        name = self.api.trigger_backup()
        tk.messagebox.showinfo("Backup", f"Backup erstellt: {name}")

if __name__ == "__main__":
    # Beispiel: importiere Deinen API-Client aus admin_dashboard.py oder separatem Modul
    from admin_dashboard import AdminAPIClient
    client = AdminAPIClient(base_url="http://127.0.0.1:5000")
    app = DashboardGUI(client)
    app.mainloop()
