import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import threading
import keyboard

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    "blocked_keys": [],
    "is_active": False
}

COMMON_KEYS = [
    "windows", "alt", "ctrl", "shift", "tab", "caps lock",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "print screen", "scroll lock", "pause",
    "insert", "delete", "home", "end", "page up", "page down",
    "left", "right", "up", "down",
    "num lock", "esc",
]

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

class KeyBlockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("키보드 차단기")
        self.root.resizable(False, False)

        self.settings = load_settings()
        self.blocked_keys = set(self.settings.get("blocked_keys", []))
        self.is_active = False
        self.hook_handlers = []
        self.capturing = False

        self._build_ui()
        self._refresh_list()

        if self.settings.get("is_active", False):
            self.root.after(300, self._start_blocking)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        top_frame = tk.LabelFrame(self.root, text="빠른 키 추가", padx=6, pady=6)
        top_frame.pack(fill="x", padx=10, pady=(10, 4))

        self.common_var = tk.StringVar()
        combo = ttk.Combobox(top_frame, textvariable=self.common_var,
                             values=COMMON_KEYS, state="readonly", width=20)
        combo.pack(side="left", **pad)
        combo.set(COMMON_KEYS[0])

        tk.Button(top_frame, text="추가", width=6,
                  command=self._add_common_key).pack(side="left", **pad)

        mid_frame = tk.LabelFrame(self.root, text="직접 입력", padx=6, pady=6)
        mid_frame.pack(fill="x", padx=10, pady=4)

        self.custom_entry = tk.Entry(mid_frame, width=22)
        self.custom_entry.pack(side="left", **pad)
        self.custom_entry.bind("<Return>", lambda e: self._add_custom_key())

        tk.Button(mid_frame, text="추가", width=6,
                  command=self._add_custom_key).pack(side="left", **pad)

        hint = tk.Label(mid_frame, text="(예: a, 1, space, enter ...)",
                        fg="gray", font=("", 8))
        hint.pack(side="left")

        capture_frame = tk.LabelFrame(self.root, text="키 입력 감지", padx=6, pady=6)
        capture_frame.pack(fill="x", padx=10, pady=4)

        self.capture_btn = tk.Button(capture_frame, text="키 입력 감지 시작",
                                     width=18, bg="#2196F3", fg="white",
                                     font=("", 9, "bold"),
                                     command=self._start_capture)
        self.capture_btn.pack(side="left", **pad)

        self.capture_label = tk.Label(capture_frame, text="버튼을 누른 후 차단할 키를 누르세요",
                                      fg="gray", font=("", 8))
        self.capture_label.pack(side="left", padx=4)

        list_frame = tk.LabelFrame(self.root, text="차단 중인 키 목록", padx=6, pady=6)
        list_frame.pack(fill="both", expand=True, padx=10, pady=4)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                  selectmode="extended", height=10, width=30)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        tk.Button(list_frame, text="선택 삭제", command=self._remove_selected).pack(
            pady=(4, 0))

        ctrl_frame = tk.Frame(self.root)
        ctrl_frame.pack(fill="x", padx=10, pady=(4, 10))

        self.toggle_btn = tk.Button(ctrl_frame, text="차단 시작", width=12,
                                    bg="#4CAF50", fg="white", font=("", 10, "bold"),
                                    command=self._toggle_blocking)
        self.toggle_btn.pack(side="left", padx=4)

        tk.Button(ctrl_frame, text="전체 삭제", width=10,
                  command=self._clear_all).pack(side="left", padx=4)

        self.status_label = tk.Label(ctrl_frame, text="● 비활성",
                                     fg="gray", font=("", 10))
        self.status_label.pack(side="right", padx=8)

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for key in sorted(self.blocked_keys):
            self.listbox.insert(tk.END, key)

    def _add_common_key(self):
        key = self.common_var.get().strip().lower()
        if key:
            self.blocked_keys.add(key)
            self._refresh_list()
            self._save_current()
            if self.is_active:
                self._restart_blocking()

    def _add_custom_key(self):
        key = self.custom_entry.get().strip().lower()
        if not key:
            return
        self.blocked_keys.add(key)
        self.custom_entry.delete(0, tk.END)
        self._refresh_list()
        self._save_current()
        if self.is_active:
            self._restart_blocking()

    def _start_capture(self):
        if self.capturing:
            return
        self.capturing = True
        self.capture_btn.config(text="감지 중... (ESC로 취소)", bg="#FF9800")
        self.capture_label.config(text="차단할 키를 누르세요!", fg="red")
        thread = threading.Thread(target=self._capture_thread, daemon=True)
        thread.start()

    def _capture_thread(self):
        try:
            while self.capturing:
                event = keyboard.read_event(suppress=True)
                if event.event_type == keyboard.KEY_DOWN:
                    key_name = event.name
                    if key_name == "esc":
                        self.root.after(0, self._cancel_capture)
                    else:
                        self.root.after(0, self._on_key_captured, key_name)
                    break
        except Exception:
            self.root.after(0, self._cancel_capture)

    def _on_key_captured(self, key_name):
        self.capturing = False
        self.capture_btn.config(text="키 입력 감지 시작", bg="#2196F3")
        self.capture_label.config(text=f"감지됨: [{key_name}]  추가 완료!", fg="#4CAF50")
        self.blocked_keys.add(key_name)
        self._refresh_list()
        self._save_current()
        if self.is_active:
            self._restart_blocking()
        self.root.after(2500, lambda: self.capture_label.config(
            text="버튼을 누른 후 차단할 키를 누르세요", fg="gray"))

    def _cancel_capture(self):
        self.capturing = False
        self.capture_btn.config(text="키 입력 감지 시작", bg="#2196F3")
        self.capture_label.config(text="취소됨", fg="gray")

    def _remove_selected(self):
        selected = self.listbox.curselection()
        items = [self.listbox.get(i) for i in selected]
        if not items: return
        for item in items:
            self.blocked_keys.discard(item)
        self._refresh_list()
        self._save_current()
        if self.is_active:
            self._restart_blocking()

    def _clear_all(self):
        if not self.blocked_keys:
            return
        if messagebox.askyesno("확인", "차단 목록을 전체 삭제할까요?"):
            self.blocked_keys.clear()
            self._refresh_list()
            self._save_current()
            if self.is_active:
                self._restart_blocking()

    def _toggle_blocking(self):
        if self.is_active:
            self._stop_blocking()
        else:
            self._start_blocking()

    def _start_blocking(self):
        if not self.blocked_keys:
            messagebox.showwarning("경고", "차단할 키를 먼저 추가하세요.")
            return
        self._apply_hooks()
        self.is_active = True
        self.toggle_btn.config(text="차단 중지", bg="#f44336")
        self.status_label.config(text="● 활성", fg="red")
        self._save_current()

    def _stop_blocking(self):
        self._remove_hooks()
        self.is_active = False
        self.toggle_btn.config(text="차단 시작", bg="#4CAF50")
        self.status_label.config(text="● 비활성", fg="gray")
        self._save_current()

    def _restart_blocking(self):
        if self.is_active:
            self._apply_hooks()

    def _apply_hooks(self):
        self._remove_hooks()
        for key in self.blocked_keys:
            try:
                cb = lambda k=key: None
                keyboard.block_key(key)
                self.hook_handlers.append(key)
            except Exception:
                pass

    def _remove_hooks(self):
        for key in self.hook_handlers:
            try:
                keyboard.unhook(key)
            except Exception:
                pass
        self.hook_handlers.clear()

    def _save_current(self):
        self.settings["blocked_keys"] = list(self.blocked_keys)
        self.settings["is_active"] = self.is_active
        save_settings(self.settings)

    def _on_close(self):
        self.capturing = False
        self._stop_blocking()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = KeyBlockerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()