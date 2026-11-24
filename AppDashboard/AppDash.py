import json
import os
import shlex
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

CONFIG_FILE = "dashboard_apps.json"


class AppConfigDialog(tk.Toplevel):
    """Modal dialog for adding or editing an application entry."""

    def __init__(self, parent, title="Configure Application", app_data=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        data = app_data or {}

        pad = {"padx": 10, "pady": 6}

        ttk.Label(self, text="Display Name:").grid(row=0, column=0, sticky="w", **pad)
        self.name_var = tk.StringVar(value=data.get("name", ""))
        ttk.Entry(self, textvariable=self.name_var, width=44).grid(row=0, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(self, text="Script Path (.py):").grid(row=1, column=0, sticky="w", **pad)
        self.path_var = tk.StringVar(value=data.get("script_path", ""))
        ttk.Entry(self, textvariable=self.path_var, width=34).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(self, text="Browse...", command=self._browse_script).grid(row=1, column=2, **pad)

        ttk.Label(self, text="Parameters / Args:").grid(row=2, column=0, sticky="w", **pad)
        self.args_var = tk.StringVar(value=data.get("args", ""))
        ttk.Entry(self, textvariable=self.args_var, width=44).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(self, text="Working Dir (optional):").grid(row=3, column=0, sticky="w", **pad)
        self.cwd_var = tk.StringVar(value=data.get("working_dir", ""))
        ttk.Entry(self, textvariable=self.cwd_var, width=34).grid(row=3, column=1, sticky="ew", **pad)
        ttk.Button(self, text="Folder...", command=self._browse_dir).grid(row=3, column=2, **pad)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=3, sticky="e", padx=10, pady=(8, 12))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="right")

        self.bind("<Return>", lambda _e: self._on_save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.wait_window(self)

    def _browse_script(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Select Python Tkinter Script",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        if path:
            self.path_var.set(path)
            if not self.name_var.get().strip():
                stem = os.path.splitext(os.path.basename(path))[0]
                self.name_var.set(stem.replace("_", " ").title())
            if not self.cwd_var.get().strip():
                self.cwd_var.set(os.path.dirname(path))

    def _browse_dir(self):
        folder = filedialog.askdirectory(parent=self, title="Select Working Directory")
        if folder:
            self.cwd_var.set(folder)

    def _on_save(self):
        name = self.name_var.get().strip()
        script_path = self.path_var.get().strip()
        args_str = self.args_var.get().strip()
        cwd = self.cwd_var.get().strip()

        if not name:
            messagebox.showwarning("Missing Name", "Please enter a display name.", parent=self)
            return
        if not script_path or not os.path.isfile(script_path):
            messagebox.showwarning("Invalid Path", "Please select a valid Python script file.", parent=self)
            return

        # Validate shell-style argument quoting early
        try:
            shlex.split(args_str)
        except ValueError as exc:
            messagebox.showwarning("Invalid Parameters", f"Could not parse parameters:\n{exc}", parent=self)
            return

        self.result = {
            "name": name,
            "script_path": os.path.abspath(script_path),
            "args": args_str,
            "working_dir": cwd or os.path.dirname(os.path.abspath(script_path)),
        }
        self.destroy()


class ApplicationDashboard(tk.Tk):
    def __init__(self, config_path=CONFIG_FILE):
        super().__init__()
        self.title("Tkinter Application Dashboard")
        self.geometry("760x480")
        self.minsize(620, 360)

        self.config_path = config_path
        self.apps = self._load_apps()
        self.running_procs = []

        self._build_ui()
        self._render_cards()

    def _load_apps(self):
        if not os.path.exists(self.config_path):
            return []
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Config Error", f"Failed to load {self.config_path}:\n{exc}")
            return []

    def _save_apps(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.apps, f, indent=2)
        except OSError as exc:
            messagebox.showerror("Save Error", f"Failed to save {self.config_path}:\n{exc}")

    def _build_ui(self):
        top_bar = ttk.Frame(self, padding=(12, 10))
        top_bar.pack(fill="x")

        ttk.Label(top_bar, text="Application Launcher", font=("TkDefaultFont", 14, "bold")).pack(side="left")
        ttk.Button(top_bar, text="+ Add Application", command=self.add_app).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # Scrollable container for a fluid number of app rows/cards
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.cards_frame = ttk.Frame(self.canvas, padding=12)

        self.cards_frame.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width),
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 4))
        status_bar.pack(fill="x", side="bottom")

    def _render_cards(self):
        for child in self.cards_frame.winfo_children():
            child.destroy()

        if not self.apps:
            empty = ttk.Label(
                self.cards_frame,
                text='No applications configured yet. Click "+ Add Application" to get started.',
                foreground="#555555",
            )
            empty.pack(pady=40)
            return

        for idx, app in enumerate(self.apps):
            card = ttk.Labelframe(self.cards_frame, text=app["name"], padding=10)
            card.pack(fill="x", pady=(0, 10))

            info = ttk.Frame(card)
            info.pack(side="left", fill="both", expand=True)

            ttk.Label(info, text=f"Script: {app['script_path']}", wraplength=440).pack(anchor="w")
            params_text = app["args"] if app.get("args") else "(none)"
            ttk.Label(info, text=f"Params: {params_text}", foreground="#444444").pack(anchor="w", pady=(2, 0))

            actions = ttk.Frame(card)
            actions.pack(side="right", padx=(10, 0))

            ttk.Button(actions, text="Launch", command=lambda i=idx: self.launch_app(i)).pack(side="left", padx=3)
            ttk.Button(actions, text="Edit", command=lambda i=idx: self.edit_app(i)).pack(side="left", padx=3)
            ttk.Button(actions, text="Remove", command=lambda i=idx: self.remove_app(i)).pack(side="left", padx=3)

    def add_app(self):
        dialog = AppConfigDialog(self, title="Add Application")
        if dialog.result:
            self.apps.append(dialog.result)
            self._save_apps()
            self._render_cards()
            self.status_var.set(f"Added '{dialog.result['name']}'")

    def edit_app(self, index):
        dialog = AppConfigDialog(self, title="Edit Application", app_data=self.apps[index])
        if dialog.result:
            self.apps[index] = dialog.result
            self._save_apps()
            self._render_cards()
            self.status_var.set(f"Updated '{dialog.result['name']}'")

    def remove_app(self, index):
        target = self.apps[index]
        if messagebox.askyesno("Remove Application", f"Remove '{target['name']}' from the dashboard?"):
            self.apps.pop(index)
            self._save_apps()
            self._render_cards()
            self.status_var.set(f"Removed '{target['name']}'")

    def launch_app(self, index):
        app = self.apps[index]
        script_path = app["script_path"]
        if not os.path.isfile(script_path):
            messagebox.showerror("File Not Found", f"Script does not exist:\n{script_path}")
            return

        args = shlex.split(app.get("args", ""))
        cwd = app.get("working_dir") or os.path.dirname(script_path) or None

        try:
            proc = subprocess.Popen(
                [sys.executable, script_path, *args],
                cwd=cwd,
            )
            self.running_procs.append(proc)
            self.status_var.set(f"Launched '{app['name']}' (PID {proc.pid})")
        except OSError as exc:
            messagebox.showerror("Launch Failed", f"Could not start '{app['name']}':\n{exc}")


if __name__ == "__main__":
    dashboard = ApplicationDashboard()
    dashboard.mainloop()
