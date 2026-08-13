import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import subprocess
import os
import re
import sys
import socket
import threading
import queue
import time
import ctypes
from ctypes import wintypes
import requests
import json
from datetime import datetime
from zeroconf import ServiceBrowser, Zeroconf

# Palette - kept in one place so the tabs stay visually consistent.
BG        = "#1a1a1a"
BG_PANEL  = "#222"
BG_INPUT  = "#333"
FG        = "white"
FG_DIM    = "#aaa"
ACCENT    = "#00d2ff"
GREEN     = "#2ecc71"
RED       = "#e74c3c"
AMBER     = "#f1c40f"


def unc_for_drive(letter):
    """Resolve a mapped drive letter to its UNC path, or None if it is local.

    This matters because Run_Control_Panel.bat elevates the app. Windows gives
    an elevated process a separate logon session, and drive mappings made by
    the normal user are not present in it, so 'X:\\photos' simply does not
    resolve. The UNC path behind the mapping works at any elevation, so every
    sync path is normalised through here before robocopy sees it.
    """
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        rc = ctypes.windll.mpr.WNetGetConnectionW(f"{letter}:", buf, ctypes.byref(size))
        return buf.value if rc == 0 else None
    except Exception:
        return None


def normalise_path(path):
    """Rewrite 'X:\\sub\\dir' to '\\\\server\\share\\sub\\dir' when X: is a network drive."""
    path = (path or "").strip().strip('"')
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", path)
    if not m:
        return path
    unc = unc_for_drive(m.group(1).upper())
    if not unc:
        return path
    rest = m.group(2)
    return os.path.join(unc, rest) if rest else unc


TELEMETRY_PORT = 9999

# Total/Copied/Skipped/Mismatch/FAILED/Extras table robocopy prints at the end.
# /BYTES is required for the byte row to be an exact integer rather than '12.7 k'.
SUMMARY_ROW = re.compile(
    r"^\s*(Dirs|Files|Bytes)\s*:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")


# Excluded from every sync. These sit at the root of a Windows volume and deny
# access even to an elevated process, so syncing a drive root without them
# costs /R:2 /W:5 of retry stalls per entry and buries the real output in
# access-denied noise. Matched by name at any depth, not by full path.
EXCLUDE_DIRS = [
    "$RECYCLE.BIN",
    "System Volume Information",
    "found.000",          # chkdsk salvage
    ".Trashes",           # macOS writes these onto shared volumes
    "#recycle",           # NAS-side recycle bin
]
EXCLUDE_FILES = [
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    "DumpStack.log",
    "DumpStack.log.tmp",
]


def parse_robocopy_summary(lines):
    """Extract the run summary. Returns {} if it could not be parsed.

    robocopy localises these row labels, so on a non-English Windows display
    language this yields nothing. Callers must treat {} as 'no totals known'
    and fall back to an indeterminate progress bar rather than reporting zero.
    """
    out = {}
    for line in lines:
        m = SUMMARY_ROW.match(line)
        if m:
            out[m.group(1).lower()] = {
                "total": int(m.group(2)), "copied": int(m.group(3)),
                "skipped": int(m.group(4)), "mismatch": int(m.group(5)),
                "failed": int(m.group(6)), "extras": int(m.group(7)),
            }
    return out


def parse_file_line(line):
    """Return (size_bytes, path) for a per-file robocopy line, else None.

    Lines are tab-delimited as '<status>\\t<size>\\t<path>', but the status
    column is padded inconsistently and is absent for some classes, so this
    anchors on the last field looking like a path and the first all-digit
    field before it rather than on column positions.
    """
    parts = [p for p in line.split("\t") if p.strip()]
    if len(parts) < 2:
        return None
    path = parts[-1].strip()
    if not (re.match(r"^[A-Za-z]:\\", path) or path.startswith("\\\\")):
        return None
    for p in parts[:-1]:
        s = p.strip()
        if s.isdigit():
            return int(s), path
    return 0, path


def human_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0


def human_time(seconds):
    if seconds is None or seconds < 0:
        return "--"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"


def bind_telemetry_socket():
    """Bind the telemetry listener, or return None if the port is already taken.

    Only one process can hold UDP 9999, so a failure here means another copy of
    this app is already running. That is a live possibility at boot: the
    shortcut sits in the Startup folder, and an instance left over from the
    previous session may still own the port. This used to raise an unhandled
    OSError, which killed the GUI and parked Run_Control_Panel.bat on
    "Press any key" - so the failure is now detected before any window or
    zeroconf thread is created.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", TELEMETRY_PORT))
    except OSError:
        sock.close()
        return None
    sock.setblocking(False)
    return sock


class WLEDDiscovery:
    def __init__(self, update_callback=None):
        self.wled_devices = {}  # {ip: name}
        self.update_callback = update_callback
        self.zeroconf = Zeroconf()
        self.browser = ServiceBrowser(self.zeroconf, "_http._tcp.local.", self)

    def remove_service(self, zeroconf, type, name):
        pass

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info and "wled" in name.lower():
            for addr in info.addresses:
                ip = socket.inet_ntoa(addr)
                clean_name = name.split(".")[0]
                if ip not in self.wled_devices:
                    self.wled_devices[ip] = clean_name
                    if self.update_callback:
                        self.update_callback()

    def update_service(self, zeroconf, type, name):
        pass


class PowerControlGUI:
    def __init__(self, root, udp_sock):
        self.root = root
        self.root.title("System Control & Monitor")
        self.root.geometry("640x760")
        self.root.configure(bg=BG)

        self.telemetry_proc = None
        self.web_server_proc = None
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.root_path = os.path.dirname(self.base_path)

        # WLED State
        self.config_path = os.path.join(self.base_path, "wled_config.json")
        self.wled_enabled = tk.BooleanVar(value=True)
        self.wled_purple_threshold = tk.IntVar(value=400)
        self.wled_red_threshold = tk.IntVar(value=600)
        self.wled_extreme_threshold = tk.IntVar(value=800)
        self.wled_flash_enabled = tk.BooleanVar(value=True)
        self.load_config()

        # Sync state
        self.sync_config_path = os.path.join(self.base_path, "sync_config.json")
        self.sync_pairs = []          # [{name, src, dst, mirror, last_run, last_result}]
        self.sync_running = False
        self.sync_queue = queue.Queue()
        # Cancellation. The worker threads are daemons, so the thing that has to
        # be stopped explicitly is the robocopy child - killing the GUI would
        # otherwise orphan it writing into a pipe nobody reads.
        self.sync_cancel = threading.Event()
        self.current_proc = None
        self.proc_lock = threading.Lock()
        self.load_sync_config()

        self.wled_discovery = WLEDDiscovery(update_callback=lambda: self.root.after(0, self.refresh_wled_list))
        self.selected_wleds = {}
        self.last_wled_state = None

        # Already bound in bind_telemetry_socket() before this window was built.
        self.udp_sock = udp_sock

        # UI Styling
        self.title_font = ("Segoe UI", 14, "bold")
        self.val_font = ("Consolas", 12, "bold")
        self.label_font = ("Segoe UI", 9)

        self.init_style()

        # --- NOTEBOOK ---------------------------------------------------
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_monitor = tk.Frame(self.notebook, bg=BG)
        self.tab_lighting = tk.Frame(self.notebook, bg=BG)
        self.tab_services = tk.Frame(self.notebook, bg=BG)
        self.tab_sync = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_monitor, text="  Monitor  ")
        self.notebook.add(self.tab_lighting, text="  Lighting  ")
        self.notebook.add(self.tab_services, text="  Services  ")
        self.notebook.add(self.tab_sync, text="  NAS Sync  ")

        self.build_monitor_tab(self.tab_monitor)
        self.build_lighting_tab(self.tab_lighting)
        self.build_services_tab(self.tab_services)
        self.build_sync_tab(self.tab_sync)

        self.update_metrics()
        self.drain_sync_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Apply the MID limits at startup - these are the everyday defaults.
        # MAX is opt-in from the buttons, not something a reboot silently sets.
        self.run_bat("5080_mid_power_limit.bat")
        self.run_bat("3090_mid_power_limit.bat")
        self.start_telemetry()
        self.start_web_server()

    def init_style(self):
        style = ttk.Style()
        # 'clam' honours background colours that the native Windows theme ignores.
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", background="#2a2a2a", foreground=FG_DIM,
                        padding=[14, 7], font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG), ("active", "#333")],
                  foreground=[("selected", ACCENT), ("active", FG)])
        style.configure("Treeview", background=BG_PANEL, fieldbackground=BG_PANEL,
                        foreground="#ddd", borderwidth=0, rowheight=24)
        style.configure("Treeview.Heading", background="#2a2a2a", foreground=ACCENT,
                        font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", "#0d5c7a")],
                  foreground=[("selected", FG)])
        style.configure("Vertical.TScrollbar", background="#2a2a2a", troughcolor=BG,
                        borderwidth=0, arrowcolor=FG_DIM)
        style.configure("Sync.Horizontal.TProgressbar", background=GREEN, troughcolor=BG_PANEL,
                        borderwidth=0, lightcolor=GREEN, darkcolor=GREEN, thickness=14)

    # ================= MONITOR TAB =================
    def build_monitor_tab(self, parent):
        cpu_frame = tk.LabelFrame(parent, text="CPU MONITOR (9950X3D)", bg=BG, fg=ACCENT,
                                  font=self.title_font, padx=15, pady=10)
        cpu_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.cpu_usage_lbl = self.create_metric_row(cpu_frame, "Usage:", "0%", 0)
        self.cpu_pwr_lbl = self.create_metric_row(cpu_frame, "Power:", "0.0W", 1)

        g1_frame = tk.LabelFrame(parent, text="RTX 5080 (Primary)", bg=BG, fg=GREEN,
                                 font=self.title_font, padx=15, pady=10)
        g1_frame.pack(fill="x", padx=10, pady=5)
        self.g1_pwr_lbl = self.create_metric_row(g1_frame, "Power:", "0.0 / 0.0W", 0)
        self.g1_temp_lbl = self.create_metric_row(g1_frame, "Temp:", "0°C", 1)
        btn_g1 = tk.Frame(g1_frame, bg=BG)
        btn_g1.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Button(btn_g1, text="LOW\n300W", command=lambda: self.run_bat("5080_lower_power_limit.bat"),
                  bg="#d35400", fg=FG, width=9, font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Button(btn_g1, text="MID (default)\n320W", command=lambda: self.run_bat("5080_mid_power_limit.bat"),
                  bg="#27ae60", fg=FG, width=12, font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Button(btn_g1, text="MAX\n350W", command=lambda: self.run_bat("5080_max_power_limit.bat"),
                  bg="#c0392b", fg=FG, width=9, font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)

        g2_frame = tk.LabelFrame(parent, text="RTX 3090 (Secondary)", bg=BG, fg="#3498db",
                                 font=self.title_font, padx=15, pady=10)
        g2_frame.pack(fill="x", padx=10, pady=5)
        self.g2_pwr_lbl = self.create_metric_row(g2_frame, "Power:", "0.0 / 0.0W", 0)
        self.g2_temp_lbl = self.create_metric_row(g2_frame, "Temp:", "0°C", 1)
        btn_g2 = tk.Frame(g2_frame, bg=BG)
        btn_g2.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Button(btn_g2, text="LOW\n225W", command=lambda: self.run_bat("3090_lower_power_limit.bat"),
                  bg="#d35400", fg=FG, width=9, font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Button(btn_g2, text="MID (default)\n250W", command=lambda: self.run_bat("3090_mid_power_limit.bat"),
                  bg="#27ae60", fg=FG, width=12, font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Button(btn_g2, text="MAX\n320W", command=lambda: self.run_bat("3090_max_power_limit.bat"),
                  bg="#c0392b", fg=FG, width=9, font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)

        sys_frame = tk.Frame(parent, bg=BG)
        sys_frame.pack(fill="x", padx=10, pady=10)
        tk.Label(sys_frame, text="PSU WATTAGE (EST):", bg=BG, fg=AMBER,
                 font=self.title_font).pack(side="left")
        self.sys_pwr_lbl = tk.Label(sys_frame, text="0.0W", bg=BG, fg=AMBER,
                                    font=("Consolas", 20, "bold"))
        self.sys_pwr_lbl.pack(side="right")
        self.sys_peak_lbl = tk.Label(parent, text="SESSION PEAK PSU: 0.0W", bg=BG,
                                     fg="#e67e22", font=self.label_font)
        self.sys_peak_lbl.pack()

    # ================= LIGHTING TAB =================
    def build_lighting_tab(self, parent):
        wled_frame = tk.LabelFrame(parent, text="AMBIENT WLED CONTROL", bg=BG, fg="#9b59b6",
                                   font=self.title_font, padx=15, pady=10)
        wled_frame.pack(fill="both", expand=True, padx=10, pady=10)

        top_wled = tk.Frame(wled_frame, bg=BG)
        top_wled.pack(fill="x")
        tk.Checkbutton(top_wled, text="Enable Power-Reactive Lighting", variable=self.wled_enabled,
                       bg=BG, fg=FG, selectcolor=BG_INPUT, activebackground=BG, activeforeground=FG,
                       font=self.label_font, command=self.toggle_wled).pack(side="left")
        self.wled_count_lbl = tk.Label(top_wled, text="Devices: 0", bg=BG, fg=FG_DIM, font=self.label_font)
        self.wled_count_lbl.pack(side="right")

        cfg_wled = tk.Frame(wled_frame, bg=BG, pady=5)
        cfg_wled.pack(fill="x")
        tk.Label(cfg_wled, text="Purp(W):", bg=BG, fg="#9b59b6", font=self.label_font).pack(side="left", padx=(0, 2))
        tk.Entry(cfg_wled, textvariable=self.wled_purple_threshold, width=4, bg=BG_INPUT, fg=FG).pack(side="left", padx=(0, 10))
        tk.Label(cfg_wled, text="Red(W):", bg=BG, fg=RED, font=self.label_font).pack(side="left", padx=(0, 2))
        tk.Entry(cfg_wled, textvariable=self.wled_red_threshold, width=4, bg=BG_INPUT, fg=FG).pack(side="left", padx=(0, 10))
        tk.Label(cfg_wled, text="Crit(W):", bg=BG, fg="#ff0000", font=self.label_font).pack(side="left", padx=(0, 2))
        tk.Entry(cfg_wled, textvariable=self.wled_extreme_threshold, width=4, bg=BG_INPUT, fg=FG).pack(side="left", padx=(0, 5))
        tk.Checkbutton(cfg_wled, text="Flash", variable=self.wled_flash_enabled, bg=BG, fg=FG,
                       selectcolor=BG_INPUT, font=self.label_font).pack(side="left")

        self.wled_list_frame = tk.Frame(wled_frame, bg=BG_PANEL, pady=2)
        self.wled_list_frame.pack(fill="both", expand=True, pady=5)
        tk.Label(self.wled_list_frame, text="Discovered Devices (Select to Sync):", bg=BG_PANEL,
                 fg="#888", font=("Segoe UI", 8)).pack(anchor="w", padx=5)
        self.device_container = tk.Frame(self.wled_list_frame, bg=BG_PANEL)
        self.device_container.pack(fill="x")

        tk.Button(wled_frame, text="💾 SAVE SETTINGS", command=self.save_config,
                  bg="#16a085", fg=FG, font=("Segoe UI", 8, "bold")).pack(fill="x", pady=5)

    # ================= SERVICES TAB =================
    def build_services_tab(self, parent):
        bench = tk.LabelFrame(parent, text="BENCHMARKS", bg=BG, fg="#8e44ad",
                              font=self.title_font, padx=15, pady=10)
        bench.pack(fill="x", padx=10, pady=(10, 5))
        tk.Button(bench, text="🚀 LAUNCH VULKAN MEMTEST", command=self.launch_vulkan_memtest,
                  bg="#8e44ad", fg=FG, font=self.val_font, pady=5).pack(fill="x", pady=2)
        tk.Button(bench, text="💎 LAUNCH SILVERBENCH", command=self.launch_silverbench,
                  bg="#2980b9", fg=FG, font=self.val_font, pady=5).pack(fill="x", pady=2)

        web_frame = tk.LabelFrame(parent, text="WEB DASHBOARD SERVER", bg=BG, fg=ACCENT,
                                  font=self.title_font, padx=15, pady=10)
        web_frame.pack(fill="x", padx=10, pady=5)
        self.web_status_label = tk.Label(web_frame, text="WEB SERVER: STOPPED", bg=BG,
                                         fg="#95a5a6", font=self.label_font)
        self.web_status_label.pack()
        self.web_url_entry = tk.Entry(web_frame, bg=BG_INPUT, fg=AMBER, font=("Consolas", 10),
                                      justify="center", borderwidth=0)
        self.web_url_entry.pack(fill="x", pady=5)
        self.web_url_entry.insert(0, "http://localhost:8000")
        self.web_url_entry.config(state="readonly")
        btn_web = tk.Frame(web_frame, bg=BG)
        btn_web.pack(fill="x")
        self.web_start_btn = tk.Button(btn_web, text="START WEB SERVER", command=self.start_web_server,
                                       bg="#27ae60", fg=FG, font=self.label_font, width=15)
        self.web_start_btn.pack(side="left", expand=True, padx=2)
        self.web_stop_btn = tk.Button(btn_web, text="STOP WEB SERVER", command=self.stop_web_server,
                                      state="disabled", bg=BG_INPUT, fg=FG, font=self.label_font, width=15)
        self.web_stop_btn.pack(side="left", expand=True, padx=2)

        ctl_frame = tk.LabelFrame(parent, text="TELEMETRY SERVICE", bg=BG, fg=ACCENT,
                                  font=self.title_font, padx=15, pady=10)
        ctl_frame.pack(fill="x", padx=10, pady=5)
        self.status_label = tk.Label(ctl_frame, text="SERVICE: STOPPED", bg=BG, fg="#95a5a6",
                                     font=self.label_font)
        self.status_label.pack()
        self.start_btn = tk.Button(ctl_frame, text="START TELEMETRY SERVICE", command=self.start_telemetry,
                                   bg="#c0392b", fg=FG, font=self.val_font)
        self.start_btn.pack(fill="x", pady=5)
        self.stop_btn = tk.Button(ctl_frame, text="STOP TELEMETRY SERVICE", command=self.stop_telemetry,
                                  state="disabled", bg=BG_INPUT, fg=FG, font=self.val_font)
        self.stop_btn.pack(fill="x")

    # ================= NAS SYNC TAB =================
    def build_sync_tab(self, parent):
        hint = tk.Label(parent, text="One-way mirror: PC  →  NAS.  Nothing is ever copied back.",
                        bg=BG, fg="#888", font=("Segoe UI", 8, "italic"))
        hint.pack(anchor="w", padx=12, pady=(8, 0))

        # --- pair list ---
        list_frame = tk.LabelFrame(parent, text="SYNC FOLDERS", bg=BG, fg=ACCENT,
                                   font=self.title_font, padx=10, pady=8)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(4, 5))

        cols = ("src", "dst", "mode", "last")
        self.sync_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=6)
        for c, t, w in (("src", "Source (PC)", 190), ("dst", "Destination (NAS)", 190),
                        ("mode", "Mode", 60), ("last", "Last Run", 110)):
            self.sync_tree.heading(c, text=t)
            self.sync_tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.sync_tree.yview)
        self.sync_tree.configure(yscrollcommand=vsb.set)
        self.sync_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- add/remove ---
        add_frame = tk.Frame(parent, bg=BG)
        add_frame.pack(fill="x", padx=10, pady=2)

        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()

        row1 = tk.Frame(add_frame, bg=BG)
        row1.pack(fill="x", pady=1)
        tk.Label(row1, text="From:", bg=BG, fg=FG_DIM, font=self.label_font, width=6, anchor="w").pack(side="left")
        tk.Entry(row1, textvariable=self.src_var, bg=BG_INPUT, fg=FG, insertbackground=FG,
                 font=("Consolas", 9)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(row1, text="Browse", command=lambda: self.browse_into(self.src_var),
                  bg="#444", fg=FG, font=("Segoe UI", 8), width=8).pack(side="left")

        row2 = tk.Frame(add_frame, bg=BG)
        row2.pack(fill="x", pady=1)
        tk.Label(row2, text="To:", bg=BG, fg=FG_DIM, font=self.label_font, width=6, anchor="w").pack(side="left")
        tk.Entry(row2, textvariable=self.dst_var, bg=BG_INPUT, fg=FG, insertbackground=FG,
                 font=("Consolas", 9)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(row2, text="Browse", command=lambda: self.browse_into(self.dst_var),
                  bg="#444", fg=FG, font=("Segoe UI", 8), width=8).pack(side="left")

        row3 = tk.Frame(add_frame, bg=BG)
        row3.pack(fill="x", pady=(4, 2))
        self.mirror_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row3, text="Mirror (delete files on NAS that are gone from the PC)",
                       variable=self.mirror_var, bg=BG, fg="#e67e22", selectcolor=BG_INPUT,
                       activebackground=BG, activeforeground="#e67e22",
                       font=("Segoe UI", 8)).pack(side="left")
        tk.Button(row3, text="+ ADD PAIR", command=self.add_sync_pair, bg="#16a085", fg=FG,
                  font=("Segoe UI", 8, "bold"), width=12).pack(side="right")

        # --- actions ---
        act = tk.Frame(parent, bg=BG)
        act.pack(fill="x", padx=10, pady=4)
        self.dry_run_var = tk.BooleanVar(value=False)
        tk.Checkbutton(act, text="Dry run", variable=self.dry_run_var, bg=BG, fg=AMBER,
                       selectcolor=BG_INPUT, activebackground=BG, activeforeground=AMBER,
                       font=("Segoe UI", 8)).pack(side="left", padx=(0, 8))
        self.skip_cloud_var = tk.BooleanVar(value=getattr(self, "saved_skip_cloud", True))
        tk.Checkbutton(act, text="Skip cloud-only files", variable=self.skip_cloud_var, bg=BG,
                       fg="#5dade2", selectcolor=BG_INPUT, activebackground=BG,
                       activeforeground="#5dade2", font=("Segoe UI", 8)).pack(side="left", padx=(0, 8))
        tk.Button(act, text="🗑 REMOVE", command=self.remove_sync_pair, bg="#7f2418", fg=FG,
                  font=("Segoe UI", 8, "bold"), width=10).pack(side="left", padx=2)
        self.sync_sel_btn = tk.Button(act, text="▶ SYNC SELECTED", command=lambda: self.start_sync(False),
                                      bg="#2980b9", fg=FG, font=("Segoe UI", 8, "bold"), width=15)
        self.sync_sel_btn.pack(side="right", padx=2)
        self.sync_all_btn = tk.Button(act, text="▶▶ SYNC ALL", command=lambda: self.start_sync(True),
                                      bg="#27ae60", fg=FG, font=("Segoe UI", 8, "bold"), width=12)
        self.sync_all_btn.pack(side="right", padx=2)
        self.sync_stop_btn = tk.Button(act, text="■ STOP", command=self.cancel_sync,
                                       state="disabled", bg=BG_INPUT, fg=FG,
                                       font=("Segoe UI", 8, "bold"), width=8)
        self.sync_stop_btn.pack(side="right", padx=2)

        # --- progress ---
        prog = tk.Frame(parent, bg=BG)
        prog.pack(fill="x", padx=10, pady=(4, 0))
        self.sync_prog = ttk.Progressbar(prog, mode="determinate", maximum=1000,
                                         style="Sync.Horizontal.TProgressbar")
        self.sync_prog.pack(fill="x")
        stat = tk.Frame(parent, bg=BG)
        stat.pack(fill="x", padx=10, pady=(1, 0))
        self.sync_status_lbl = tk.Label(stat, text="idle", bg=BG, fg=FG_DIM,
                                        font=("Consolas", 8), anchor="w")
        self.sync_status_lbl.pack(side="left")
        self.sync_eta_lbl = tk.Label(stat, text="", bg=BG, fg=AMBER,
                                     font=("Consolas", 8), anchor="e")
        self.sync_eta_lbl.pack(side="right")

        # --- log ---
        log_frame = tk.LabelFrame(parent, text="LOG", bg=BG, fg=FG_DIM,
                                  font=("Segoe UI", 9, "bold"), padx=6, pady=4)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        self.sync_log = tk.Text(log_frame, bg="#111", fg="#9fe0a0", font=("Consolas", 8),
                                height=8, borderwidth=0, wrap="none")
        log_vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.sync_log.yview)
        self.sync_log.configure(yscrollcommand=log_vsb.set, state="disabled")
        self.sync_log.pack(side="left", fill="both", expand=True)
        log_vsb.pack(side="right", fill="y")

        self.refresh_sync_tree()

    def browse_into(self, var):
        initial = var.get() or "C:\\"
        chosen = filedialog.askdirectory(initialdir=initial, title="Select folder")
        if chosen:
            var.set(os.path.normpath(chosen))

    def add_sync_pair(self):
        src = self.src_var.get().strip().strip('"')
        dst = self.dst_var.get().strip().strip('"')
        if not src or not dst:
            messagebox.showwarning("Missing path", "Both a source and a destination are required.")
            return
        if not os.path.isdir(src):
            messagebox.showerror("Bad source", f"Source folder does not exist:\n{src}")
            return
        if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
            messagebox.showerror("Bad pair", "Source and destination are the same folder.")
            return
        self.sync_pairs.append({
            "src": os.path.normpath(src),
            "dst": os.path.normpath(dst),
            "mirror": bool(self.mirror_var.get()),
            "last_run": "",
            "last_result": "",
        })
        self.src_var.set("")
        self.dst_var.set("")
        self.mirror_var.set(False)
        self.save_sync_config()
        self.refresh_sync_tree()

    def remove_sync_pair(self):
        sel = self.sync_tree.selection()
        if not sel:
            messagebox.showinfo("Nothing selected", "Select a row to remove.")
            return
        for iid in sorted((int(i) for i in sel), reverse=True):
            if 0 <= iid < len(self.sync_pairs):
                del self.sync_pairs[iid]
        self.save_sync_config()
        self.refresh_sync_tree()

    def refresh_sync_tree(self):
        for row in self.sync_tree.get_children():
            self.sync_tree.delete(row)
        for i, p in enumerate(self.sync_pairs):
            last = p.get("last_run", "")
            if p.get("last_result"):
                last = f"{last} {p['last_result']}".strip()
            self.sync_tree.insert("", "end", iid=str(i),
                                  values=(p["src"], p["dst"],
                                          "MIRROR" if p.get("mirror") else "ADD", last))

    def log(self, text):
        self.sync_log.config(state="normal")
        self.sync_log.insert("end", text.rstrip() + "\n")
        # Keep the widget bounded - a big mirror can emit tens of thousands of lines.
        if int(self.sync_log.index("end-1c").split(".")[0]) > 500:
            self.sync_log.delete("1.0", "200.0")
        self.sync_log.see("end")
        self.sync_log.config(state="disabled")

    def build_robocopy_cmd(self, src, dst, mirror, dry_run, skip_cloud=True):
        """Flags chosen for an SMB target on the WD MyCloud (Linux-backed).

        /MT:32  SMB is round-trip bound on small files; threading hides latency.
        /FFT    2-second timestamp granularity, else every file looks modified
                on each run and the whole tree is re-copied.
        /XJ     do not follow junctions.
        /R:2 /W:5  the default is a million retries at 30s - one locked file
                would otherwise wedge the run indefinitely.

        /BYTES so the summary reports exact integers, which the pre-flight
        parses to size the progress bar and ETA.

        /XA:O excludes cloud placeholder files. This is the single most
        important flag when the source contains an iCloud or OneDrive folder:
        reading a dehydrated file forces the sync client to download it, so a
        plain copy silently turns into tens of GB of downloads and appears to
        hang on every placeholder. Skipping them keeps the backup to what is
        actually on local disk.
        """
        cmd = ["robocopy", src, dst, "/MIR" if mirror else "/E",
               "/DCOPY:DAT", "/COPY:DAT", "/MT:32", "/FFT", "/XJ",
               "/R:2", "/W:5", "/NP", "/NDL", "/TEE", "/BYTES"]
        cmd += ["/XD"] + EXCLUDE_DIRS
        cmd += ["/XF"] + EXCLUDE_FILES
        if skip_cloud:
            cmd.append("/XA:O")
        if dry_run:
            cmd.append("/L")
        return cmd

    def set_sync_buttons(self, enabled):
        if enabled:
            self.sync_sel_btn.config(state="normal", bg="#2980b9")
            self.sync_all_btn.config(state="normal", bg="#27ae60")
            self.sync_stop_btn.config(state="disabled", bg=BG_INPUT)
        else:
            self.sync_sel_btn.config(state="disabled", bg=BG_INPUT)
            self.sync_all_btn.config(state="disabled", bg=BG_INPUT)
            self.sync_stop_btn.config(state="normal", bg="#c0392b")

    def spawn_robocopy(self, cmd):
        """Start robocopy and register it so cancel_sync can terminate it.

        Returns None if a cancel arrived between the check and the spawn, which
        would otherwise leave an unregistered process running past the stop.
        """
        with self.proc_lock:
            if self.sync_cancel.is_set():
                return None
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace",
                                    creationflags=0x08000000)
            self.current_proc = proc
            return proc

    def clear_proc(self):
        with self.proc_lock:
            self.current_proc = None

    def cancel_sync(self):
        """Stop the run. Safe at any point.

        robocopy writes a file then stamps its timestamp, so a file killed
        mid-write ends up with both the wrong size and the wrong timestamp and
        is simply recopied next run. Nothing already completed is damaged.
        """
        if not self.sync_running:
            return
        self.sync_cancel.set()
        self.sync_stop_btn.config(state="disabled", bg=BG_INPUT)
        self.sync_status_lbl.config(text="stopping...", fg=AMBER)
        self.log("STOP requested - terminating robocopy...")
        with self.proc_lock:
            proc = self.current_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception as e:
                self.log(f"  could not terminate: {e}")

    def start_sync(self, run_all):
        if self.sync_running:
            messagebox.showinfo("Busy", "A sync is already running.")
            return
        if run_all:
            targets = list(range(len(self.sync_pairs)))
        else:
            targets = [int(i) for i in self.sync_tree.selection()]
        if not targets:
            messagebox.showinfo("Nothing to do", "No sync pairs selected.")
            return

        self.sync_running = True
        self.sync_cancel.clear()
        self.set_sync_buttons(False)
        self.sync_prog.config(value=0)
        self.sync_status_lbl.config(text="scanning...", fg=FG_DIM)
        self.sync_eta_lbl.config(text="")
        self.log("")
        self.log("Scanning (robocopy /L) - nothing is written during this pass...")
        threading.Thread(target=self.preflight_worker, args=(targets,), daemon=True).start()

    def preflight_worker(self, targets):
        """Cost the run with /L before writing anything.

        The dry pass is what makes a determinate progress bar and an ETA
        possible at all: it produces the file count and byte total that the
        real run is then measured against.
        """
        skip_cloud = self.skip_cloud_var.get()
        plans = []
        for idx in targets:
            if self.sync_cancel.is_set():
                break
            pair = self.sync_pairs[idx]
            src = normalise_path(pair["src"])
            dst = normalise_path(pair["dst"])
            if not os.path.isdir(src):
                self.sync_queue.put(("log", f"  SKIPPED - source not found: {src}"))
                self.sync_queue.put(("result", (idx, "src missing")))
                continue
            self.sync_queue.put(("log", f"  scanning {src} ..."))
            cmd = self.build_robocopy_cmd(src, dst, pair.get("mirror"), True, skip_cloud)
            lines = []
            try:
                proc = self.spawn_robocopy(cmd)
                if proc is None:
                    break
                for line in proc.stdout:
                    lines.append(line.rstrip())
                proc.wait()
                rc = proc.returncode
                self.clear_proc()
            except FileNotFoundError:
                self.sync_queue.put(("log", "  ERROR - robocopy not found on PATH"))
                self.sync_queue.put(("result", (idx, "no robocopy")))
                continue
            except Exception as e:
                self.sync_queue.put(("log", f"  ERROR during scan - {e}"))
                self.sync_queue.put(("result", (idx, "scan failed")))
                continue
            if rc >= 8:
                self.sync_queue.put(("log", f"  SCAN FAILED ({rc}) - {dst} unreachable?"))
                self.sync_queue.put(("result", (idx, f"scan failed ({rc})")))
                continue
            plans.append({
                "idx": idx, "src": src, "dst": dst,
                "mirror": bool(pair.get("mirror")),
                "summary": parse_robocopy_summary(lines),
                "lines": lines,
            })
        if self.sync_cancel.is_set():
            self.sync_queue.put(("log", "Scan stopped - nothing was written."))
            self.sync_queue.put(("cancelled", None))
        else:
            self.sync_queue.put(("preflight", plans))

    def on_preflight(self, plans):
        """Main-thread handler: report the dry run, or show totals and confirm."""
        if not plans:
            self.log("Nothing to sync.")
            self.sync_status_lbl.config(text="nothing to do", fg=FG_DIM)
            self.finish_sync()
            return

        files = sum(p["summary"].get("files", {}).get("copied", 0) for p in plans)
        byts = sum(p["summary"].get("bytes", {}).get("copied", 0) for p in plans)
        extras = sum(p["summary"].get("files", {}).get("extras", 0) for p in plans)
        parsed = all(p["summary"] for p in plans)

        if self.dry_run_var.get():
            for p in plans:
                self.log("=" * 62)
                self.log(f"[DRY RUN] {p['src']}  ->  {p['dst']}")
                shown = 0
                for line in p["lines"]:
                    if parse_file_line(line):
                        self.log("  " + line)
                        shown += 1
                        if shown >= 200:
                            self.log("  ... list truncated")
                            break
            self.log("")
            self.log(f"DRY RUN TOTAL: {files} file(s), {human_bytes(byts)}"
                     + (f", {extras} extra on destination" if extras else ""))
            self.sync_status_lbl.config(
                text=f"dry run: {files} file(s), {human_bytes(byts)}", fg=AMBER)
            self.finish_sync()
            return

        if files == 0 and extras == 0:
            self.log("Already up to date - nothing to copy.")
            self.sync_status_lbl.config(text="already up to date", fg=GREEN)
            for p in plans:
                self.sync_pairs[p["idx"]]["last_run"] = datetime.now().strftime("%d-%m %H:%M")
                self.sync_pairs[p["idx"]]["last_result"] = "no changes"
            self.finish_sync()
            return

        detail = [f"{files} file(s) to copy", f"{human_bytes(byts)} to transfer"]
        if extras:
            if any(p["mirror"] for p in plans):
                detail.append(f"{extras} file(s) on the NAS will be DELETED")
            else:
                detail.append(f"{extras} extra file(s) on the NAS will be left in place")
        if not parsed:
            detail.append("totals unavailable - progress will be approximate")

        routes = "\n".join(f"  {p['src']}\n     -> {p['dst']}"
                           + ("   [MIRROR]" if p["mirror"] else "") for p in plans)
        body = "\n".join("  - " + d for d in detail)
        if not messagebox.askyesno("Confirm sync", f"{routes}\n\n{body}\n\nProceed?"):
            self.log("Cancelled - nothing was written.")
            self.sync_status_lbl.config(text="cancelled", fg=FG_DIM)
            self.finish_sync()
            return

        self.sync_status_lbl.config(text="starting...", fg=GREEN)
        threading.Thread(target=self.run_sync_worker,
                         args=(plans, files, byts), daemon=True).start()

    def run_sync_worker(self, plans, total_files, total_bytes):
        skip_cloud = self.skip_cloud_var.get()
        started = time.time()
        done_files = 0
        done_bytes = 0
        for p in plans:
            if self.sync_cancel.is_set():
                break
            idx, src, dst = p["idx"], p["src"], p["dst"]
            self.sync_queue.put(("log", "=" * 62))
            self.sync_queue.put(("log", f"{src}  ->  {dst}"))
            cmd = self.build_robocopy_cmd(src, dst, p["mirror"], False, skip_cloud)
            try:
                proc = self.spawn_robocopy(cmd)
                if proc is None:
                    break
                for line in proc.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    hit = parse_file_line(line)
                    if hit:
                        # Per-file lines drive the bar, not the log: a large tree
                        # emits tens of thousands and would swamp the text widget.
                        size, path = hit
                        done_files += 1
                        done_bytes += size
                        self.sync_queue.put(("progress", (done_files, total_files,
                                                          done_bytes, total_bytes,
                                                          started, os.path.basename(path))))
                    else:
                        self.sync_queue.put(("log", "  " + line))
                proc.wait()
                rc = proc.returncode
                self.clear_proc()
            except FileNotFoundError:
                self.sync_queue.put(("log", "  ERROR - robocopy not found on PATH"))
                self.sync_queue.put(("result", (idx, "no robocopy")))
                continue
            except Exception as e:
                self.sync_queue.put(("log", f"  ERROR - {e}"))
                self.sync_queue.put(("result", (idx, "error")))
                continue

            if self.sync_cancel.is_set():
                # Terminated mid-run: the exit code is from the kill, not the copy.
                self.sync_queue.put(("log", "  -> STOPPED"))
                self.sync_queue.put(("result", (idx, "stopped")))
                break

            # robocopy: 0-7 success (0 nothing to do, 1 copied, 2 extras, 4 mismatch);
            # 8+ is a real failure.
            if rc >= 8:
                verdict = f"FAILED ({rc})"
                self.sync_queue.put(("log",
                    "  Hint: if the destination was a mapped drive, note this app runs "
                    "elevated and elevated sessions do not see user drive mappings. "
                    "Use the \\\\server\\share form instead."))
            elif rc == 0:
                verdict = "no changes"
            else:
                verdict = f"OK ({rc})"
            self.sync_queue.put(("log", f"  -> {verdict}"))
            self.sync_queue.put(("result", (idx, verdict)))

        if self.sync_cancel.is_set():
            self.sync_queue.put(("log",
                f"STOPPED after {done_files} file(s), {human_bytes(done_bytes)}. "
                "Any part-written file is recopied on the next run."))
            self.sync_queue.put(("cancelled", None))
        else:
            self.sync_queue.put(("finished", (done_files, done_bytes, time.time() - started)))
            self.sync_queue.put(("done", None))

    def apply_progress(self, dfiles, tfiles, dbytes, tbytes, started, current):
        elapsed = max(time.time() - started, 0.001)
        if tbytes > 0:
            frac = min(dbytes / float(tbytes), 1.0)
        elif tfiles > 0:
            frac = min(dfiles / float(tfiles), 1.0)
        else:
            frac = 0.0
        self.sync_prog.config(value=frac * 1000)
        rate = dbytes / elapsed
        eta = (tbytes - dbytes) / rate if rate > 0 and tbytes > dbytes else None
        self.sync_status_lbl.config(
            text=f"{dfiles}/{tfiles or '?'}  {human_bytes(dbytes)}/{human_bytes(tbytes)}  {current[:26]}",
            fg=GREEN)
        self.sync_eta_lbl.config(text=f"{human_bytes(rate)}/s  ETA {human_time(eta)}")

    def finish_sync(self):
        self.sync_running = False
        self.sync_cancel.clear()
        self.clear_proc()
        self.set_sync_buttons(True)
        self.save_sync_config()
        self.refresh_sync_tree()

    def drain_sync_queue(self):
        last_progress = None
        try:
            while True:
                kind, payload = self.sync_queue.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "progress":
                    last_progress = payload      # coalesce: only the newest matters
                elif kind == "preflight":
                    self.on_preflight(payload)
                elif kind == "cancelled":
                    self.sync_status_lbl.config(text="stopped", fg=AMBER)
                    self.sync_eta_lbl.config(text="")
                    self.finish_sync()
                elif kind == "finished":
                    n, b, secs = payload
                    self.sync_prog.config(value=1000)
                    self.sync_status_lbl.config(
                        text=f"done: {n} file(s), {human_bytes(b)} in {human_time(secs)}",
                        fg=GREEN)
                    self.sync_eta_lbl.config(text="")
                elif kind == "result":
                    idx, verdict = payload
                    if 0 <= idx < len(self.sync_pairs):
                        self.sync_pairs[idx]["last_run"] = datetime.now().strftime("%d-%m %H:%M")
                        self.sync_pairs[idx]["last_result"] = verdict
                elif kind == "done":
                    self.finish_sync()
        except queue.Empty:
            pass
        if last_progress:
            self.apply_progress(*last_progress)
        self.root.after(200, self.drain_sync_queue)

    def load_sync_config(self):
        self.saved_skip_cloud = True
        if os.path.exists(self.sync_config_path):
            try:
                with open(self.sync_config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.sync_pairs = data.get("pairs", [])
                self.saved_skip_cloud = data.get("skip_cloud", True)
            except Exception:
                self.sync_pairs = []

    def save_sync_config(self):
        try:
            with open(self.sync_config_path, "w", encoding="utf-8") as f:
                json.dump({"pairs": self.sync_pairs,
                           "skip_cloud": bool(self.skip_cloud_var.get())}, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save sync config: {e}")

    # ================= SHARED / EXISTING =================
    def start_web_server(self):
        server_path = os.path.join(self.root_path, "web_client", "server.py")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            url = f"http://{ip}:8000"
            self.web_url_entry.config(state="normal")
            self.web_url_entry.delete(0, tk.END)
            self.web_url_entry.insert(0, url)
            self.web_url_entry.config(state="readonly")

            self.web_server_proc = subprocess.Popen(
                ["python", server_path],
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
            self.web_status_label.config(text="WEB SERVER: RUNNING", fg=GREEN)
            self.web_start_btn.config(state="disabled", bg=BG_INPUT)
            self.web_stop_btn.config(state="normal", bg=RED)
        except Exception:
            self.web_status_label.config(text="WEB SERVER: FAILED", fg=RED)

    def stop_web_server(self):
        if self.web_server_proc:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.web_server_proc.pid)],
                               capture_output=True)
            except Exception:
                pass
            self.web_server_proc = None
            self.web_status_label.config(text="WEB SERVER: STOPPED", fg="#95a5a6")
            self.web_start_btn.config(state="normal", bg="#27ae60")
            self.web_stop_btn.config(state="disabled", bg=BG_INPUT)

    def create_metric_row(self, parent, label, default, row):
        tk.Label(parent, text=label, bg=BG, fg=FG_DIM, font=self.label_font).grid(row=row, column=0, sticky="w")
        lbl = tk.Label(parent, text=default, bg=BG, fg=FG, font=self.val_font)
        lbl.grid(row=row, column=1, sticky="e", padx=50)
        parent.grid_columnconfigure(1, weight=1)
        return lbl

    def launch_vulkan_memtest(self):
        memtest_exe = os.path.normpath(os.path.join(self.base_path, "memtest_vulkan", "memtest_vulkan.exe"))
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "cmd.exe", "/k", memtest_exe],
                             cwd=os.path.dirname(memtest_exe))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Memtest: {e}")

    def launch_silverbench(self):
        url = "https://silver.urih.com/"
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "msedge", url])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Silverbench: {e}")

    def save_config(self):
        config = {
            "enabled": self.wled_enabled.get(),
            "purple": self.wled_purple_threshold.get(),
            "red": self.wled_red_threshold.get(),
            "extreme": self.wled_extreme_threshold.get(),
            "flash": self.wled_flash_enabled.get(),
            "selected_ips": [ip for ip, var in self.selected_wleds.items() if var.get()]
        }
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f)
            messagebox.showinfo("Success", "WLED settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def load_config(self):
        self.saved_ips = []
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                self.wled_enabled.set(config.get("enabled", True))
                self.wled_purple_threshold.set(config.get("purple", 400))
                self.wled_red_threshold.set(config.get("red", 600))
                self.wled_extreme_threshold.set(config.get("extreme", 800))
                self.wled_flash_enabled.set(config.get("flash", True))
                self.saved_ips = config.get("selected_ips", [])
            except Exception:
                pass

    def refresh_wled_list(self):
        for widget in self.device_container.winfo_children():
            widget.destroy()
        for ip, name in self.wled_discovery.wled_devices.items():
            if ip not in self.selected_wleds:
                is_selected = True if not self.saved_ips or ip in self.saved_ips else False
                self.selected_wleds[ip] = tk.BooleanVar(value=is_selected)
            f = tk.Frame(self.device_container, bg=BG_PANEL)
            f.pack(fill="x", padx=10)
            tk.Checkbutton(f, text=f"{name} ({ip})", variable=self.selected_wleds[ip],
                           bg=BG_PANEL, fg=GREEN, selectcolor=BG_INPUT, activebackground=BG_PANEL,
                           activeforeground=GREEN, font=("Segoe UI", 9)).pack(side="left")

    def set_wled_state(self, ip, r, g, b, fx=0):
        url = f"http://{ip}/json/state"
        payload = {"on": True, "bri": 255, "seg": [{"col": [[r, g, b]], "fx": fx, "sx": 255, "ix": 200}]}
        try:
            requests.post(url, json=payload, timeout=0.5)
        except Exception:
            pass

    def toggle_wled(self):
        if not self.wled_enabled.get():
            self.last_wled_state = None

    def update_metrics(self):
        try:
            self.wled_count_lbl.config(text=f"Devices: {len(self.wled_discovery.wled_devices)}")
            data, _ = self.udp_sock.recvfrom(2048)
            msg = data.decode("ascii")
            vals = msg.split(",")
            if len(vals) >= 15:
                sys_p = float(vals[9])
                self.cpu_usage_lbl.config(text=f"{int(float(vals[0]))}%")
                self.cpu_pwr_lbl.config(text=f"{vals[1]}W (Peak: {vals[10]}W)")
                self.g1_pwr_lbl.config(text=f"{vals[3]} / {vals[5]}W")
                self.g1_temp_lbl.config(text=f"{vals[4]}°C")
                self.g2_pwr_lbl.config(text=f"{vals[6]} / {vals[8]}W")
                self.g2_temp_lbl.config(text=f"{vals[7]}°C")
                self.sys_pwr_lbl.config(text=f"{vals[9]}W")
                self.sys_peak_lbl.config(text=f"SESSION PEAK: {vals[13]}W | SYNC: {vals[14]}")

                if self.wled_enabled.get():
                    try:
                        p_limit = self.wled_purple_threshold.get()
                        r_limit = self.wled_red_threshold.get()
                        e_limit = self.wled_extreme_threshold.get()
                    except Exception:
                        p_limit, r_limit, e_limit = 400, 600, 800

                    if sys_p > e_limit and self.wled_flash_enabled.get():
                        new_state = (255, 0, 0, 1)      # Red, Blink
                    elif sys_p > r_limit:
                        new_state = (255, 0, 0, 0)      # Red, Static
                    elif sys_p >= p_limit:
                        new_state = (255, 0, 255, 0)    # Purple, Static
                    else:
                        new_state = (0, 255, 0, 0)      # Green, Static

                    if new_state != self.last_wled_state:
                        active_ips = [ip for ip, var in self.selected_wleds.items() if var.get()]
                        for ip in active_ips:
                            threading.Thread(target=self.set_wled_state, args=(ip, *new_state), daemon=True).start()
                        self.last_wled_state = new_state
            elif len(vals) == 10:
                self.cpu_usage_lbl.config(text=f"{int(float(vals[0]))}%")
                self.cpu_pwr_lbl.config(text=f"{vals[1]}W")
                self.g1_pwr_lbl.config(text=f"{vals[3]} / {vals[5]}W")
                self.g1_temp_lbl.config(text=f"{vals[4]}°C")
                self.g2_pwr_lbl.config(text=f"{vals[6]} / {vals[8]}W")
                self.g2_temp_lbl.config(text=f"{vals[7]}°C")
                self.sys_pwr_lbl.config(text=f"{vals[9]}W")
        except Exception:
            pass
        self.root.after(500, self.update_metrics)

    def run_bat(self, filename):
        path = os.path.join(self.base_path, filename)
        try:
            subprocess.Popen(["cmd.exe", "/c", path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception:
            messagebox.showerror("Error", f"Failed to run {filename}")

    def start_telemetry(self):
        script_path = os.path.join(self.base_path, "PowerCheck_Serial.ps1")
        try:
            self.telemetry_proc = subprocess.Popen(
                ["powershell.exe", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script_path],
                creationflags=0x08000000
            )
            self.status_label.config(text="SERVICE: RUNNING", fg=GREEN)
            self.start_btn.config(state="disabled", bg=BG_INPUT)
            self.stop_btn.config(state="normal", bg=RED)
        except Exception:
            messagebox.showerror("Error", "Failed to start service")

    def stop_telemetry(self):
        if self.web_server_proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.web_server_proc.pid)])
            self.web_server_proc = None
        if self.telemetry_proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.telemetry_proc.pid)])
            self.telemetry_proc = None
            self.status_label.config(text="SERVICE: STOPPED", fg="#95a5a6")
            self.start_btn.config(state="normal", bg="#c0392b")
            self.stop_btn.config(state="disabled", bg=BG_INPUT)
            self.cpu_usage_lbl.config(text="0%")
            self.cpu_pwr_lbl.config(text="0.0W")
            self.g1_pwr_lbl.config(text="0.0 / 0.0W")
            self.g2_pwr_lbl.config(text="0.0 / 0.0W")
            self.sys_pwr_lbl.config(text="0.0W")
            self.sys_peak_lbl.config(text="SESSION PEAK: 0.0W")

    def on_closing(self):
        # Without this the robocopy child outlives the window, writing into a
        # pipe with no reader until the buffer fills and it blocks forever.
        if self.sync_running:
            if not messagebox.askyesno(
                    "Sync running",
                    "A sync is still running. Closing will stop it.\n\n"
                    "Part-written files are recopied next run. Close anyway?"):
                return
            self.cancel_sync()
        self.stop_telemetry()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    sock = bind_telemetry_socket()
    if sock is None:
        messagebox.showerror(
            "Already running",
            f"System Control & Monitor could not start.\n\n"
            f"UDP port {TELEMETRY_PORT} is already in use, which normally means "
            f"another copy of this app is running. Check the taskbar, or close "
            f"the existing window and try again.")
        root.destroy()
        sys.exit(0)

    root.deiconify()
    gui = PowerControlGUI(root, sock)
    root.mainloop()
