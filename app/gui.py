import os
import threading
import asyncio
import zipfile
from datetime import datetime
from PIL import Image as PilImage
import qrcode
import pystray
import customtkinter as ctk
from tkinter import filedialog

from app.state import state
from app.utils import ZC_AVAILABLE, generate_thumbnail
from app.i18n import t, LANGUAGE_MAP

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_IMPORTED = True
except Exception:
    DND_IMPORTED = False

if DND_IMPORTED:
    class BaseWindow(ctk.CTk, TkinterDnD.DnDWrapper):
        pass
else:
    class BaseWindow(ctk.CTk):
        pass


class WebdropGUI(BaseWindow):
    def __init__(self, local_ip: str, port: int, zc_instance=None):
        super().__init__()
        self.local_ip = local_ip
        self.port = port
        self.zc_instance = zc_instance
        self.tray_icon = None
        self.current_lang = "en"
        state.gui_instance = self

        self.dnd_available = False
        if DND_IMPORTED:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_available = True
            except Exception:
                pass

        ctk.set_appearance_mode("Dark")
        self.configure(fg_color="#0f172a")

        self.title("Webdrop Pro")
        self.geometry("1020x720")
        self.minsize(980, 660)
        self.protocol('WM_DELETE_WINDOW', self.hide_to_tray)

        if self.dnd_available:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.on_drop_files)

        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()
        self.update_translations()

    def _build_left_panel(self):
        self.left_frame = ctk.CTkFrame(self, width=340, corner_radius=12, fg_color="#1e293b", border_width=1, border_color="#334155")
        self.left_frame.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        self.left_frame.pack_propagate(False)

        top_bar = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(10, 5), padx=12)

        self.lbl_header = ctk.CTkLabel(top_bar, text="Webdrop", font=ctk.CTkFont(size=20, weight="bold"), text_color="#38bdf8")
        self.lbl_header.pack(side="left")

        self.lang_combo = ctk.CTkComboBox(top_bar, values=list(LANGUAGE_MAP.keys()), width=105, height=26,
                                          font=ctk.CTkFont(size=11), fg_color="#0f172a", border_color="#475569",
                                          command=self._on_lang_selected)
        self.lang_combo.set("English")
        self.lang_combo.pack(side="right", padx=(5, 0))

        self.btn_exit = ctk.CTkButton(top_bar, text="Exit", width=60, height=26, fg_color="#dc2626", hover_color="#991b1b",
                                     font=ctk.CTkFont(size=11, weight="bold"), command=self.exit_app)
        self.btn_exit.pack(side="right")

        self.lbl_ip = ctk.CTkLabel(self.left_frame, text=f"https://{self.local_ip}:{self.port}",
                                   font=ctk.CTkFont(size=13, family="Courier", weight="bold"), text_color="#10b981")
        self.lbl_ip.pack(pady=(6, 0))

        if ZC_AVAILABLE:
            self.lbl_zc = ctk.CTkLabel(self.left_frame, text="Or: https://webdrop.local:8080",
                                       font=ctk.CTkFont(size=11, family="Courier"), text_color="#0ea5e9")
            self.lbl_zc.pack(pady=(0, 6))

        self.lbl_clients_title = ctk.CTkLabel(self.left_frame, text="Devices (0):", text_color="#94a3b8", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_clients_title.pack(pady=(8, 2), padx=14, anchor="w")

        self.client_list_box = ctk.CTkTextbox(self.left_frame, height=52, fg_color="#0f172a", text_color="#f8fafc",
                                              border_width=1, border_color="#334155", font=ctk.CTkFont(size=11))
        self.client_list_box.pack(fill="x", padx=14, pady=2)
        self.client_list_box.insert("1.0", "No connected devices.")
        self.client_list_box.configure(state="disabled")

        pin_frame = ctk.CTkFrame(self.left_frame, fg_color="#0f172a", corner_radius=8, border_width=1, border_color="#334155")
        pin_frame.pack(pady=10, fill="x", padx=14)

        self.chk_pin = ctk.CTkCheckBox(pin_frame, text="PIN Protection", font=ctk.CTkFont(size=12),
                                       fg_color="#0284c7", hover_color="#0369a1", command=self.toggle_pin)
        self.chk_pin.pack(pady=8, padx=12, anchor="w")
        self.lbl_pin = ctk.CTkLabel(pin_frame, text=f"PIN: {state.current_pin}", font=ctk.CTkFont(size=15, family="Courier", weight="bold"), text_color="#f59e0b")

        inc_frame = ctk.CTkFrame(self.left_frame, fg_color="#0f172a", corner_radius=8, border_width=1, border_color="#334155")
        inc_frame.pack(pady=4, fill="x", padx=14)

        self.lbl_inc_title = ctk.CTkLabel(inc_frame, text="Incoming Mode:", text_color="#94a3b8", font=ctk.CTkFont(size=11))
        self.lbl_inc_title.pack(pady=(6, 2), padx=12, anchor="w")

        self.combo_inc = ctk.CTkComboBox(inc_frame, values=["Normal", "Timestamp Folder", "Auto ZIP"],
                                         fg_color="#1e293b", border_color="#475569", command=self._on_incoming_mode_change)
        self.combo_inc.pack(pady=(0, 8), padx=12, fill="x")
        self.combo_inc.set("Normal")

        self.lbl_save_dir = ctk.CTkLabel(self.left_frame, text=f"...{state.save_dir[-28:]}", text_color="#64748b", font=ctk.CTkFont(size=10))
        self.lbl_save_dir.pack(pady=(6, 0))
        self.btn_save_dir = ctk.CTkButton(self.left_frame, text="Change Folder", height=24, fg_color="#334155", hover_color="#475569",
                                          font=ctk.CTkFont(size=11), command=self.change_dir)
        self.btn_save_dir.pack(pady=4)

        self.qr_label = ctk.CTkLabel(self.left_frame, text="")
        self.qr_label.pack(pady=10)
        self.generate_qr()

    def _build_right_panel(self):
        right_main = ctk.CTkFrame(self, fg_color="transparent")
        right_main.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="nsew")
        right_main.grid_columnconfigure(0, weight=1)
        right_main.grid_rowconfigure(0, weight=1)

        self.right_tab = ctk.CTkTabview(right_main, corner_radius=12, fg_color="#1e293b",
                                        segmented_button_selected_color="#0284c7",
                                        segmented_button_selected_hover_color="#0369a1",
                                        segmented_button_unselected_color="#0f172a")
        self.right_tab.grid(row=0, column=0, sticky="nsew")

        self.tab_share = self.right_tab.add("Send")
        self.tab_clip = self.right_tab.add("Clipboard")
        self.tab_hist = self.right_tab.add("Log")

        self.lbl_drop_hint = ctk.CTkLabel(self.tab_share, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        self.lbl_drop_hint.pack(pady=(15, 6))

        btn_bar = ctk.CTkFrame(self.tab_share, fg_color="transparent")
        btn_bar.pack(pady=4)
        self.btn_add_files = ctk.CTkButton(btn_bar, text="Add Files", command=lambda: self.select_multi(False, False),
                                           fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=12, weight="bold"))
        self.btn_add_files.pack(side="left", padx=5)

        self.file_list_frame = ctk.CTkScrollableFrame(self.tab_share, height=200, fg_color="#0f172a",
                                                     border_width=1, border_color="#334155")
        self.file_list_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self.refresh_file_list_ui()

        action_f = ctk.CTkFrame(self.tab_share, fg_color="transparent")
        action_f.pack(pady=6)
        self.combo_zip = ctk.CTkComboBox(action_f, values=["Standard (DEFLATED)", "No compression"],
                                         fg_color="#0f172a", border_color="#475569", width=180)
        self.combo_zip.pack(side="left", padx=5)
        self.btn_pack_zip = ctk.CTkButton(action_f, text="Pack to ZIP", command=self.pack_to_zip,
                                          fg_color="#6366f1", hover_color="#4f46e5", width=130)
        self.btn_pack_zip.pack(side="left", padx=5)
        self.btn_clear_all = ctk.CTkButton(action_f, text="Clear All", command=self.clear_file,
                                           fg_color="#dc2626", hover_color="#991b1b", width=110)
        self.btn_clear_all.pack(side="left", padx=5)

        self.txt_clip = ctk.CTkTextbox(self.tab_clip, font=ctk.CTkFont("Consolas", 12), fg_color="#0f172a",
                                      border_width=1, border_color="#334155", text_color="#f8fafc")
        self.txt_clip.pack(fill="both", expand=True, padx=8, pady=8)
        self.txt_clip.bind("<KeyRelease>", self.on_clip_change)

        clip_btns = ctk.CTkFrame(self.tab_clip, fg_color="transparent")
        clip_btns.pack(fill="x", pady=6)
        self.btn_save_txt = ctk.CTkButton(clip_btns, text="Save as TXT", command=self.save_clip_txt,
                                          fg_color="#059669", hover_color="#047857")
        self.btn_save_txt.pack(side="left", expand=True, padx=5)
        self.btn_copy_sys = ctk.CTkButton(clip_btns, text="Copy to System Clipboard", command=self.copy_clip_sys,
                                          fg_color="#0284c7", hover_color="#0369a1")
        self.btn_copy_sys.pack(side="left", expand=True, padx=5)

        self.txt_hist = ctk.CTkTextbox(self.tab_hist, font=ctk.CTkFont("Consolas", 11), state="disabled",
                                      fg_color="#0f172a", border_width=1, border_color="#334155", text_color="#cbd5e1")
        self.txt_hist.pack(fill="both", expand=True, padx=8, pady=8)

        bottom_f = ctk.CTkFrame(right_main, fg_color="transparent")
        bottom_f.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.lbl_prog = ctk.CTkLabel(bottom_f, text="Ready...", text_color="#94a3b8", font=ctk.CTkFont(size=11))
        self.lbl_prog.pack(anchor="w")
        self.pbar = ctk.CTkProgressBar(bottom_f, height=6, fg_color="#334155", progress_color="#38bdf8")
        self.pbar.pack(fill="x", pady=2)
        self.pbar.set(0)

    def _on_lang_selected(self, choice: str):
        self.current_lang = LANGUAGE_MAP.get(choice, "en")
        self.update_translations()

    def _on_incoming_mode_change(self, choice: str):
        idx = self.combo_inc._values.index(choice) if choice in self.combo_inc._values else 0
        internal_modes = ["Normal", "Timestamp Mappa", "Automata ZIP"]
        setattr(state, 'incoming_mode', internal_modes[idx])

    def update_translations(self):
        lang = self.current_lang
        self.btn_exit.configure(text=t("exit", lang))
        if ZC_AVAILABLE and hasattr(self, 'lbl_zc'):
            self.lbl_zc.configure(text=t("or_address", lang))

        self.chk_pin.configure(text=t("pin_protection", lang))
        self.lbl_pin.configure(text=t("pin_label", lang, pin=state.current_pin))
        self.lbl_inc_title.configure(text=t("incoming_mode", lang))

        self.combo_inc.configure(values=[t("mode_normal", lang), t("mode_timestamp", lang), t("mode_zip", lang)])
        self.combo_inc.set(t("mode_normal", lang))

        self.btn_save_dir.configure(text=t("change_dir", lang))
        self.lbl_drop_hint.configure(text=t("drop_hint_dnd" if self.dnd_available else "drop_hint_nodnd", lang))
        self.btn_add_files.configure(text=t("add_files", lang))

        self.combo_zip.configure(values=[t("zip_deflated", lang), t("zip_stored", lang)])
        self.combo_zip.set(t("zip_deflated", lang))
        self.btn_pack_zip.configure(text=t("pack_zip", lang))
        self.btn_clear_all.configure(text=t("clear_all", lang))

        self.btn_save_txt.configure(text=t("save_txt", lang))
        self.btn_copy_sys.configure(text=t("copy_clip", lang))
        self.lbl_prog.configure(text=t("ready", lang))

        self.safe_update_clients()
        self.refresh_file_list_ui()

    def log(self, message: str, level: str = "INFO"):
        self.add_to_history(level, message, "")

    def add_to_history(self, action: str, fn: str, p: str):
        self.after(0, lambda: self._insert_history(f"[{datetime.now().strftime('%H:%M')}] {action}: {fn}\n"))

    def _insert_history(self, line: str):
        self.txt_hist.configure(state="normal")
        self.txt_hist.insert("1.0", line)
        self.txt_hist.configure(state="disabled")

    def copy_clip_sys(self):
        self.clipboard_clear()
        self.clipboard_append(self.txt_clip.get("1.0", "end-1c"))
        self.lbl_prog.configure(text=t("copied", self.current_lang))

    def save_clip_txt(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="webdrop_export.txt", filetypes=[("Text files", "*.txt")])
        if f:
            with open(f, "w", encoding="utf-8") as file:
                file.write(self.txt_clip.get("1.0", "end-1c"))

    def refresh_file_list_ui(self):
        for widget in self.file_list_frame.winfo_children():
            widget.destroy()
        if not state.shared_files:
            ctk.CTkLabel(self.file_list_frame, text=t("no_shares", self.current_lang), text_color="#64748b").pack(pady=20)
            return

        for path in state.shared_files:
            row = ctk.CTkFrame(self.file_list_frame, fg_color="#1e293b", corner_radius=6, border_width=1, border_color="#334155")
            row.pack(fill="x", pady=3, padx=2)
            size_mb = os.path.getsize(path) / (1024 * 1024) if os.path.exists(path) else 0.0
            lbl_text = f"{os.path.basename(path)}  ({size_mb:.1f} MB)"
            ctk.CTkLabel(row, text=lbl_text, font=ctk.CTkFont(size=12), text_color="#f8fafc").pack(side="left", padx=10, pady=6)
            ctk.CTkButton(row, text="Remove", width=65, height=24, fg_color="#dc2626", hover_color="#991b1b",
                          font=ctk.CTkFont(size=11), command=lambda p=path: self.remove_single_file(p)).pack(side="right", padx=6)

    def remove_single_file(self, path: str):
        if path in state.shared_files:
            state.shared_files.remove(path)
            self.refresh_file_list_ui()
            self._notify_file_update()

    def toggle_pin(self):
        state.pin_enabled = self.chk_pin.get()
        if state.pin_enabled:
            self.lbl_pin.pack(pady=(0, 6))
        else:
            self.lbl_pin.pack_forget()

        # Értesítjük az összes aktív klienst a biztonsági állapot változásáról
        if state.server_loop:
            from app.server import notify_clients
            asyncio.run_coroutine_threadsafe(
                notify_clients({"event": "security_status", "enabled": state.pin_enabled}),
                state.server_loop
            )

    def on_drop_files(self, event):
        paths = self.tk.splitlist(event.data)
        self.process_selected_paths(paths)

    def process_selected_paths(self, paths):
        added = False
        for p in paths:
            if os.path.isdir(p):
                for r, _, fs in os.walk(p):
                    for f in fs:
                        full_path = os.path.join(r, f)
                        if full_path not in state.shared_files:
                            state.shared_files.append(full_path)
                            added = True
            else:
                if p not in state.shared_files:
                    state.shared_files.append(p)
                    added = True
        if added:
            self.refresh_file_list_ui()
            self._notify_file_update()

    def _notify_file_update(self):
        payload = [
            {"filename": os.path.basename(p), "thumbnail": generate_thumbnail(p), "url": f"/download/{i}", "source": "pc"}
            for i, p in enumerate(state.shared_files)
        ]
        if state.server_loop:
            from app.server import notify_clients
            asyncio.run_coroutine_threadsafe(notify_clients({"event": "files_shared", "files": payload, "is_relay": False}), state.server_loop)

    def hide_to_tray(self):
        self.withdraw()
        img = PilImage.new('RGB', (64, 64), color=(2, 132, 199))
        self.tray_icon = pystray.Icon("Webdrop", img, "Webdrop Active", (
            pystray.MenuItem('Open', lambda i, it: self.after(0, self.deiconify) or self.tray_icon.stop()),
            pystray.MenuItem('Exit', lambda: self.exit_app())
        ))
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def select_multi(self, is_folder: bool, as_zip: bool):
        targets = [filedialog.askdirectory()] if is_folder else list(filedialog.askopenfilenames())
        if targets and targets[0]:
            if as_zip:
                threading.Thread(target=self._zip_worker, args=(targets, is_folder), daemon=True).start()
            else:
                self.process_selected_paths(targets)

    def pack_to_zip(self):
        if not state.shared_files:
            return
        threading.Thread(target=self._zip_worker, args=(state.shared_files, False), daemon=True).start()

    def _zip_worker(self, paths, is_folder):
        zp = os.path.join(state.save_dir, "webdrop_package.zip")
        is_deflate = "DEFLATED" in self.combo_zip.get()
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED if is_deflate else zipfile.ZIP_STORED) as zf:
            for p in paths:
                if os.path.isdir(p):
                    for r, _, fs in os.walk(p):
                        for f in fs:
                            zf.write(os.path.join(r, f), os.path.relpath(os.path.join(r, f), p))
                else:
                    zf.write(p, os.path.basename(p))
        state.shared_files = [zp]
        self.after(0, self.refresh_file_list_ui)
        self._notify_file_update()

    def update_upload_progress(self, fn, idx, tot):
        self.after(0, lambda: self.pbar.set(idx / tot) or self.lbl_prog.configure(text=t("receiving", self.current_lang, filename=fn)))

    def on_clip_change(self, e=None):
        val = self.txt_clip.get("1.0", "end-1c")
        if val != state.clipboard_text:
            state.clipboard_text = val
            if state.server_loop:
                from app.server import notify_clients
                asyncio.run_coroutine_threadsafe(notify_clients({"event": "clipboard", "text": val}), state.server_loop)

    def sync_clipboard_to_pc_ui(self, txt):
        self.after(0, lambda: (self.txt_clip.delete("1.0", "end"), self.txt_clip.insert("1.0", txt))
                   if self.txt_clip.get("1.0", "end-1c") != txt else None)

    def change_dir(self):
        if nd := filedialog.askdirectory(initialdir=state.save_dir):
            state.save_dir = nd
            self.lbl_save_dir.configure(text=f"...{nd[-28:]}")

    def clear_file(self):
        state.shared_files = []
        self.refresh_file_list_ui()
        if state.server_loop:
            from app.server import notify_clients
            asyncio.run_coroutine_threadsafe(notify_clients({"event": "file_cleared"}), state.server_loop)

    def generate_qr(self):
        qr = qrcode.QRCode(box_size=5, border=2)
        qr.add_data(f"https://{self.local_ip}:{self.port}")
        qr.make()
        self.qr_label.configure(image=ctk.CTkImage(qr.make_image(fill_color="black", back_color="white").convert("RGB"), size=(175, 175)))

    def safe_update_clients(self):
        count = len(state.connected_clients)
        self.after(0, lambda: self.lbl_clients_title.configure(text=t("devices", self.current_lang, count=count)))
        names_text = "\n".join([info["name"] for info in state.connected_clients.values() if info["name"] != "Unknown"]) or t("no_devices", self.current_lang)
        self.after(0, lambda: (
            self.client_list_box.configure(state="normal"),
            self.client_list_box.delete("1.0", "end"),
            self.client_list_box.insert("1.0", names_text),
            self.client_list_box.configure(state="disabled")
        ))

    def exit_app(self):
        if self.tray_icon:
            self.tray_icon.stop()
        if self.zc_instance:
            try:
                self.zc_instance.unregister_all_services()
                self.zc_instance.close()
            except Exception:
                pass
        self.destroy()
        os._exit(0)