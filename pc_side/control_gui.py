import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import os
import socket
import threading
import requests
import json
from zeroconf import ServiceBrowser, Zeroconf

class WLEDDiscovery:
    def __init__(self, update_callback=None):
        self.wled_devices = {} # {ip: name}
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
    def __init__(self, root):
        self.root = root
        self.root.title("System Control & Monitor")
        self.root.geometry("600x1050") # Increased height for all sections
        self.root.configure(bg="#1a1a1a")
        
        self.telemetry_proc = None
        self.telemetry_proc = None
        self.web_server_proc = None
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.root_path = os.path.dirname(self.base_path)

        self.root_path = os.path.dirname(self.base_path)
        
        # WLED State
        self.config_path = os.path.join(self.base_path, "wled_config.json")
        self.wled_enabled = tk.BooleanVar(value=True)
        self.wled_purple_threshold = tk.IntVar(value=400)
        self.wled_red_threshold = tk.IntVar(value=600)
        self.wled_extreme_threshold = tk.IntVar(value=800)
        self.wled_flash_enabled = tk.BooleanVar(value=True)
        self.load_config()
        
        self.wled_discovery = WLEDDiscovery(update_callback=lambda: self.root.after(0, self.refresh_wled_list))
        self.selected_wleds = {} # {ip: BooleanVar}
        self.last_wled_state = None # Stores (r, g, b, fx)
        
        # UDP Setup for monitoring
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(("0.0.0.0", 9999))
        self.udp_sock.setblocking(False)
        
        # UI Styling
        self.title_font = ("Segoe UI", 14, "bold")
        self.val_font = ("Consolas", 12, "bold")
        self.label_font = ("Segoe UI", 9)

        # --- TOP LEVEL CONTROLS ---
        top_frame = tk.Frame(root, bg="#1a1a1a", pady=5)
        top_frame.pack(fill="x", padx=15, pady=(15, 5))
        tk.Button(top_frame, text="🚀 LAUNCH VULKAN MEMTEST", command=self.launch_vulkan_memtest, 
                  bg="#8e44ad", fg="white", font=self.val_font, pady=5).pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(top_frame, text="💎 LAUNCH SILVERBENCH", command=self.launch_silverbench, 
                  bg="#2980b9", fg="white", font=self.val_font, pady=5).pack(side="left", fill="x", expand=True, padx=(2, 0))
        
        # --- CPU MONITOR SECTION ---
        cpu_frame = tk.LabelFrame(root, text="CPU MONITOR (9950X3D)", bg="#1a1a1a", fg="#00d2ff", font=self.title_font, padx=15, pady=10)
        cpu_frame.pack(fill="x", padx=15, pady=5)
        self.cpu_usage_lbl = self.create_metric_row(cpu_frame, "Usage:", "0%", 0)
        self.cpu_pwr_lbl = self.create_metric_row(cpu_frame, "Power:", "0.0W", 1)

        # --- GPU 1 SECTION (5080) ---
        g1_frame = tk.LabelFrame(root, text="RTX 5080 (Primary)", bg="#1a1a1a", fg="#2ecc71", font=self.title_font, padx=15, pady=10)
        g1_frame.pack(fill="x", padx=15, pady=5)
        self.g1_pwr_lbl = self.create_metric_row(g1_frame, "Power:", "0.0 / 0.0W", 0)
        self.g1_temp_lbl = self.create_metric_row(g1_frame, "Temp:", "0°C", 1)
        btn_g1 = tk.Frame(g1_frame, bg="#1a1a1a")
        btn_g1.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Button(btn_g1, text="MAX (320W)", command=lambda: self.run_bat("5080_max_power_limit.bat"), bg="#27ae60", fg="white", width=12).pack(side="left", padx=2)
        tk.Button(btn_g1, text="LOW (300W)", command=lambda: self.run_bat("5080_lower_power_limit.bat"), bg="#d35400", fg="white", width=12).pack(side="left", padx=2)

        # --- GPU 2 SECTION (3090) ---
        g2_frame = tk.LabelFrame(root, text="RTX 3090 (Secondary)", bg="#1a1a1a", fg="#3498db", font=self.title_font, padx=15, pady=10)
        g2_frame.pack(fill="x", padx=15, pady=5)
        self.g2_pwr_lbl = self.create_metric_row(g2_frame, "Power:", "0.0 / 0.0W", 0)
        self.g2_temp_lbl = self.create_metric_row(g2_frame, "Temp:", "0°C", 1)
        btn_g2 = tk.Frame(g2_frame, bg="#1a1a1a")
        btn_g2.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Button(btn_g2, text="MAX (250W)", command=lambda: self.run_bat("3090_max_power_limit.bat"), bg="#2980b9", fg="white", width=12).pack(side="left", padx=2)
        tk.Button(btn_g2, text="LOW (225W)", command=lambda: self.run_bat("3090_lower_power_limit.bat"), bg="#d35400", fg="white", width=12).pack(side="left", padx=2)

        # --- SYSTEM TOTAL ---
        sys_frame = tk.Frame(root, bg="#1a1a1a")
        sys_frame.pack(fill="x", padx=15, pady=10)
        tk.Label(sys_frame, text="PSU WATTAGE (EST):", bg="#1a1a1a", fg="#f1c40f", font=self.title_font).pack(side="left")
        self.sys_pwr_lbl = tk.Label(sys_frame, text="0.0W", bg="#1a1a1a", fg="#f1c40f", font=("Consolas", 20, "bold"))
        self.sys_pwr_lbl.pack(side="right")
        self.sys_peak_lbl = tk.Label(root, text="SESSION PEAK PSU: 0.0W", bg="#1a1a1a", fg="#e67e22", font=self.label_font)
        self.sys_peak_lbl.pack()

        # --- WLED CONTROL SECTION ---
        wled_frame = tk.LabelFrame(root, text="AMBIENT WLED CONTROL", bg="#1a1a1a", fg="#9b59b6", font=self.title_font, padx=15, pady=10)
        wled_frame.pack(fill="x", padx=15, pady=5)
        
        top_wled = tk.Frame(wled_frame, bg="#1a1a1a")
        top_wled.pack(fill="x")
        tk.Checkbutton(top_wled, text="Enable Power-Reactive Lighting", variable=self.wled_enabled, 
                       bg="#1a1a1a", fg="white", selectcolor="#333", activebackground="#1a1a1a", activeforeground="white",
                       font=self.label_font, command=self.toggle_wled).pack(side="left")
        self.wled_count_lbl = tk.Label(top_wled, text="Devices: 0", bg="#1a1a1a", fg="#aaa", font=self.label_font)
        self.wled_count_lbl.pack(side="right")

        cfg_wled = tk.Frame(wled_frame, bg="#1a1a1a", pady=5)
        cfg_wled.pack(fill="x")
        
        tk.Label(cfg_wled, text="Purp(W):", bg="#1a1a1a", fg="#9b59b6", font=self.label_font).pack(side="left", padx=(0, 2))
        tk.Entry(cfg_wled, textvariable=self.wled_purple_threshold, width=4, bg="#333", fg="white").pack(side="left", padx=(0, 10))
        
        tk.Label(cfg_wled, text="Red(W):", bg="#1a1a1a", fg="#e74c3c", font=self.label_font).pack(side="left", padx=(0, 2))
        tk.Entry(cfg_wled, textvariable=self.wled_red_threshold, width=4, bg="#333", fg="white").pack(side="left", padx=(0, 10))

        tk.Label(cfg_wled, text="Crit(W):", bg="#1a1a1a", fg="#ff0000", font=self.label_font).pack(side="left", padx=(0, 2))
        tk.Entry(cfg_wled, textvariable=self.wled_extreme_threshold, width=4, bg="#333", fg="white").pack(side="left", padx=(0, 5))
        tk.Checkbutton(cfg_wled, text="Flash", variable=self.wled_flash_enabled, bg="#1a1a1a", fg="white", 
                       selectcolor="#333", font=self.label_font).pack(side="left")
        
        self.wled_list_frame = tk.Frame(wled_frame, bg="#222", pady=2)
        self.wled_list_frame.pack(fill="x", pady=5)
        tk.Label(self.wled_list_frame, text="Discovered Devices (Select to Sync):", bg="#222", fg="#888", font=("Segoe UI", 8)).pack(anchor="w", padx=5)
        self.device_container = tk.Frame(self.wled_list_frame, bg="#222")
        self.device_container.pack(fill="x")

        tk.Button(wled_frame, text="💾 SAVE SETTINGS", command=self.save_config, 
                  bg="#16a085", fg="white", font=("Segoe UI", 8, "bold")).pack(fill="x", pady=5)

        # --- WEB SERVER CONTROL SECTION ---
        web_frame = tk.LabelFrame(root, text="WEB DASHBOARD SERVER", bg="#1a1a1a", fg="#00d2ff", font=self.title_font, padx=15, pady=10)
        web_frame.pack(fill="x", padx=15, pady=5)
        
        self.web_status_label = tk.Label(web_frame, text="WEB SERVER: STOPPED", bg="#1a1a1a", fg="#95a5a6", font=self.label_font)
        self.web_status_label.pack()
        
        self.web_url_entry = tk.Entry(web_frame, bg="#333", fg="#f1c40f", font=("Consolas", 10), justify="center", borderwidth=0)
        self.web_url_entry.pack(fill="x", pady=5)
        self.web_url_entry.insert(0, "http://localhost:8000")
        self.web_url_entry.config(state="readonly")

        btn_web = tk.Frame(web_frame, bg="#1a1a1a")
        btn_web.pack(fill="x")
        self.web_start_btn = tk.Button(btn_web, text="START WEB SERVER", command=self.start_web_server, bg="#27ae60", fg="white", font=self.label_font, width=15)
        self.web_start_btn.pack(side="left", expand=True, padx=2)
        self.web_stop_btn = tk.Button(btn_web, text="STOP WEB SERVER", command=self.stop_web_server, state="disabled", bg="#333", fg="white", font=self.label_font, width=15)
        self.web_stop_btn.pack(side="left", expand=True, padx=2)

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
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.run_bat("5080_max_power_limit.bat")
        self.run_bat("3090_max_power_limit.bat")
        self.start_telemetry()
        self.start_web_server()

    def start_web_server(self):
        server_path = os.path.join(self.root_path, "web_client", "server.py")
        try:
            # Get local IP for display
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
            s.close()
            url = f"http://{ip}:8000"
            self.web_url_entry.config(state="normal")
            self.web_url_entry.delete(0, tk.END)
            self.web_url_entry.insert(0, url)
            self.web_url_entry.config(state="readonly")
            
            # Launch web server in hidden mode
            self.web_server_proc = subprocess.Popen(
                ["python", server_path],
                creationflags=0x08000000 # CREATE_NO_WINDOW
            )
            self.web_status_label.config(text="WEB SERVER: RUNNING", fg="#2ecc71")
            self.web_start_btn.config(state="disabled", bg="#333")
            self.web_stop_btn.config(state="normal", bg="#e74c3c")
        except:
            self.web_status_label.config(text="WEB SERVER: FAILED", fg="#e74c3c")

    def stop_web_server(self):
        if self.web_server_proc:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.web_server_proc.pid)], capture_output=True)
            except: pass
            self.web_server_proc = None
            self.web_status_label.config(text="WEB SERVER: STOPPED", fg="#95a5a6")
            self.web_start_btn.config(state="normal", bg="#27ae60")
            self.web_stop_btn.config(state="disabled", bg="#333")

    def create_metric_row(self, parent, label, default, row):
        tk.Label(parent, text=label, bg="#1a1a1a", fg="#aaa", font=self.label_font).grid(row=row, column=0, sticky="w")
        lbl = tk.Label(parent, text=default, bg="#1a1a1a", fg="white", font=self.val_font)
        lbl.grid(row=row, column=1, sticky="e", padx=50)
        parent.grid_columnconfigure(1, weight=1)
        return lbl

    def launch_vulkan_memtest(self):
        memtest_exe = os.path.normpath(os.path.join(self.base_path, "memtest_vulkan", "memtest_vulkan.exe"))
        try:
            # Launch in a new command window that stays open
            subprocess.Popen(["cmd.exe", "/c", "start", "cmd.exe", "/k", memtest_exe], cwd=os.path.dirname(memtest_exe))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Memtest: {e}")

    def launch_silverbench(self):
        url = "https://silver.urih.com/"
        try:
            # Launch Microsoft Edge with the specific URL
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
            except:
                pass

    def refresh_wled_list(self):
        # Clear existing
        for widget in self.device_container.winfo_children():
            widget.destroy()
            
        for ip, name in self.wled_discovery.wled_devices.items():
            if ip not in self.selected_wleds:
                # If we have saved IPs, only select if it's in the list. 
                # Otherwise default to True (first time discovery)
                is_selected = True if not self.saved_ips or ip in self.saved_ips else False
                self.selected_wleds[ip] = tk.BooleanVar(value=is_selected)
                
            f = tk.Frame(self.device_container, bg="#222")
            f.pack(fill="x", padx=10)
            tk.Checkbutton(f, text=f"{name} ({ip})", variable=self.selected_wleds[ip],
                           bg="#222", fg="#2ecc71", selectcolor="#333", activebackground="#222", 
                           activeforeground="#2ecc71", font=("Segoe UI", 9)).pack(side="left")

    def set_wled_state(self, ip, r, g, b, fx=0):
        url = f"http://{ip}/json/state"
        payload = {"on": True, "bri": 255, "seg": [{"col": [[r, g, b]], "fx": fx, "sx": 255, "ix": 200}]}
        try:requests.post(url, json=payload, timeout=0.5)
        except:pass

    def toggle_wled(self):
        if not self.wled_enabled.get(): self.last_wled_state = None

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
                    except:
                        p_limit, r_limit, e_limit = 400, 600, 800
                        
                    if sys_p > e_limit and self.wled_flash_enabled.get():
                        new_state = (255, 0, 0, 1) # Red, Blink effect
                    elif sys_p > r_limit:
                        new_state = (255, 0, 0, 0) # Red, Static
                    elif sys_p >= p_limit:
                        new_state = (255, 0, 255, 0) # Purple, Static
                    else:
                        new_state = (0, 255, 0, 0) # Green, Static
                        
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
        except:pass 
        self.root.after(500, self.update_metrics)

    def run_bat(self, filename):
        path = os.path.join(self.base_path, filename)
        try:subprocess.Popen(["cmd.exe", "/c", path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:messagebox.showerror("Error", f"Failed to run {filename}")

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
        except Exception as e:messagebox.showerror("Error", "Failed to start service")

    def stop_telemetry(self):
        if self.web_server_proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.web_server_proc.pid)])
            self.web_server_proc = None
        if self.telemetry_proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.telemetry_proc.pid)])
            self.telemetry_proc = None
            self.status_label.config(text="SERVICE: STOPPED", fg="#95a5a6")
            self.start_btn.config(state="normal", bg="#c0392b")
            self.stop_btn.config(state="disabled", bg="#333")
            self.cpu_usage_lbl.config(text="0%"); self.cpu_pwr_lbl.config(text="0.0W")
            self.g1_pwr_lbl.config(text="0.0 / 0.0W"); self.g2_pwr_lbl.config(text="0.0 / 0.0W")
            self.sys_pwr_lbl.config(text="0.0W"); self.sys_peak_lbl.config(text="SESSION PEAK: 0.0W")

    def on_closing(self):
        self.stop_telemetry()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    gui = PowerControlGUI(root)
    root.mainloop()
