import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import os
import socket
import threading

class PowerControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("System Control & Monitor")
        self.root.geometry("500x680")
        self.root.configure(bg="#1a1a1a")
        
        self.telemetry_proc = None
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        
        # UDP Setup for monitoring
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(("127.0.0.1", 9999))
        self.udp_sock.setblocking(False)
        
        # UI Styling
        self.title_font = ("Segoe UI", 14, "bold")
        self.val_font = ("Consolas", 12, "bold")
        self.label_font = ("Segoe UI", 9)
        
        # --- CPU MONITOR SECTION ---
        cpu_frame = tk.LabelFrame(root, text="CPU MONITOR (9950X3D)", bg="#1a1a1a", fg="#00d2ff", font=self.title_font, padx=15, pady=10)
        cpu_frame.pack(fill="x", padx=15, pady=5)
        self.cpu_usage_lbl = self.create_metric_row(cpu_frame, "Usage:", "0%", 0)
        self.cpu_pwr_lbl = self.create_metric_row(cpu_frame, "Power:", "0.0W", 1)

        # --- GPU 1 SECTION ---
        g1_frame = tk.LabelFrame(root, text="RTX 5080 (Primary)", bg="#1a1a1a", fg="#2ecc71", font=self.title_font, padx=15, pady=10)
        g1_frame.pack(fill="x", padx=15, pady=5)
        self.g1_pwr_lbl = self.create_metric_row(g1_frame, "Power:", "0.0 / 0.0W", 0)
        self.g1_temp_lbl = self.create_metric_row(g1_frame, "Temp:", "0°C", 1)
        btn_g1 = tk.Frame(g1_frame, bg="#1a1a1a")
        btn_g1.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Button(btn_g1, text="MAX (360W)", command=lambda: self.run_bat("5080_max_power_limit.bat"), bg="#27ae60", fg="white", width=15).pack(side="left", padx=5)
        tk.Button(btn_g1, text="LOW (300W)", command=lambda: self.run_bat("5080_lower_power_limit.bat"), bg="#d35400", fg="white", width=15).pack(side="left", padx=5)

        # --- GPU 2 SECTION ---
        g2_frame = tk.LabelFrame(root, text="RTX 3090 (Secondary)", bg="#1a1a1a", fg="#3498db", font=self.title_font, padx=15, pady=10)
        g2_frame.pack(fill="x", padx=15, pady=5)
        self.g2_pwr_lbl = self.create_metric_row(g2_frame, "Power:", "0.0 / 0.0W", 0)
        self.g2_temp_lbl = self.create_metric_row(g2_frame, "Temp:", "0°C", 1)
        btn_g2 = tk.Frame(g2_frame, bg="#1a1a1a")
        btn_g2.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Button(btn_g2, text="MAX (350W)", command=lambda: self.run_bat("3090_max_power_limit.bat"), bg="#2980b9", fg="white", width=15).pack(side="left", padx=5)
        tk.Button(btn_g2, text="LOW (225W)", command=lambda: self.run_bat("3090_lower_power_limit.bat"), bg="#d35400", fg="white", width=15).pack(side="left", padx=5)

        # --- SYSTEM TOTAL ---
        sys_frame = tk.Frame(root, bg="#1a1a1a")
        sys_frame.pack(fill="x", padx=15, pady=10)
        tk.Label(sys_frame, text="SYSTEM TOTAL:", bg="#1a1a1a", fg="#f1c40f", font=self.title_font).pack(side="left")
        self.sys_pwr_lbl = tk.Label(sys_frame, text="0.0W", bg="#1a1a1a", fg="#f1c40f", font=("Consolas", 20, "bold"))
        self.sys_pwr_lbl.pack(side="right")
        self.sys_peak_lbl = tk.Label(root, text="SESSION PEAK: 0.0W", bg="#1a1a1a", fg="#e67e22", font=self.label_font)
        self.sys_peak_lbl.pack()

        # --- SERVICE CONTROLS ---
        ctl_frame = tk.Frame(root, bg="#1a1a1a", pady=10)
        ctl_frame.pack(fill="x", padx=15)
        self.status_label = tk.Label(ctl_frame, text="SERVICE: STOPPED", bg="#1a1a1a", fg="#95a5a6", font=self.label_font)
        self.status_label.pack()
        self.start_btn = tk.Button(ctl_frame, text="START TELEMETRY SERVICE", command=self.start_telemetry, bg="#c0392b", fg="white", font=self.val_font)
        self.start_btn.pack(fill="x", pady=5)
        self.stop_btn = tk.Button(ctl_frame, text="STOP TELEMETRY SERVICE", command=self.stop_telemetry, state="disabled", bg="#333", fg="white", font=self.val_font)
        self.stop_btn.pack(fill="x")

        self.update_metrics()

        # --- AUTO-LAUNCH ACTIONS ---
        # 1. Set 3090 to Low Power (225W)
        self.run_bat("3090_lower_power_limit.bat")
        # 2. Start Telemetry Service
        self.start_telemetry()

    def create_metric_row(self, parent, label, default, row):
        tk.Label(parent, text=label, bg="#1a1a1a", fg="#aaa", font=self.label_font).grid(row=row, column=0, sticky="w")
        lbl = tk.Label(parent, text=default, bg="#1a1a1a", fg="white", font=self.val_font)
        lbl.grid(row=row, column=1, sticky="e", padx=50)
        parent.grid_columnconfigure(1, weight=1)
        return lbl

    def update_metrics(self):
        try:
            data, _ = self.udp_sock.recvfrom(2048)
            msg = data.decode("ascii")
            vals = msg.split(",")
            # New format: usage[0], cpuP[1], cpuT[2], g1P[3], g1T[4], g1L[5], g2P[6], g2T[7], g2L[8], sysP[9], peakCpu[10], peakG1[11], peakG2[12], peakSys[13], time[14]
            if len(vals) >= 15:
                self.cpu_usage_lbl.config(text=f"{int(float(vals[0]))}%")
                self.cpu_pwr_lbl.config(text=f"{vals[1]}W (Peak: {vals[10]}W)")
                self.g1_pwr_lbl.config(text=f"{vals[3]} / {vals[5]}W")
                self.g1_temp_lbl.config(text=f"{vals[4]}°C")
                self.g2_pwr_lbl.config(text=f"{vals[6]} / {vals[8]}W")
                self.g2_temp_lbl.config(text=f"{vals[7]}°C")
                self.sys_pwr_lbl.config(text=f"{vals[9]}W")
                self.sys_peak_lbl.config(text=f"SESSION PEAK: {vals[13]}W | SYNC: {vals[14]}")
            elif len(vals) == 10:
                self.cpu_usage_lbl.config(text=f"{int(float(vals[0]))}%")
                self.cpu_pwr_lbl.config(text=f"{vals[1]}W")
                self.g1_pwr_lbl.config(text=f"{vals[3]} / {vals[5]}W")
                self.g1_temp_lbl.config(text=f"{vals[4]}°C")
                self.g2_pwr_lbl.config(text=f"{vals[6]} / {vals[8]}W")
                self.g2_temp_lbl.config(text=f"{vals[7]}°C")
                self.sys_pwr_lbl.config(text=f"{vals[9]}W")
        except:
            pass 
        self.root.after(500, self.update_metrics)

    def run_bat(self, filename):
        path = os.path.join(self.base_path, filename)
        try:
            subprocess.Popen(["cmd.exe", "/c", path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run {filename}")

    def start_telemetry(self):
        script_path = os.path.join(self.base_path, "PowerCheck_Serial.ps1")
        try:
            self.telemetry_proc = subprocess.Popen(
                ["powershell.exe", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script_path], 
                creationflags=0x08000000 
            )
            self.status_label.config(text="SERVICE: RUNNING", fg="#2ecc71")
            self.start_btn.config(state="disabled", bg="#333")
            self.stop_btn.config(state="normal", bg="#e74c3c")
        except Exception as e:
            messagebox.showerror("Error", "Failed to start service")

    def stop_telemetry(self):
        if self.telemetry_proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.telemetry_proc.pid)])
            self.telemetry_proc = None
            self.status_label.config(text="SERVICE: STOPPED", fg="#95a5a6")
            self.start_btn.config(state="normal", bg="#c0392b")
            self.stop_btn.config(state="disabled", bg="#333")
            self.cpu_usage_lbl.config(text="0%")
            self.cpu_pwr_lbl.config(text="0.0W")
            self.g1_pwr_lbl.config(text="0.0 / 0.0W")
            self.g2_pwr_lbl.config(text="0.0 / 0.0W")
            self.sys_pwr_lbl.config(text="0.0W")
            self.sys_peak_lbl.config(text="SESSION PEAK: 0.0W")

if __name__ == "__main__":
    root = tk.Tk()
    gui = PowerControlGUI(root)
    root.mainloop()
