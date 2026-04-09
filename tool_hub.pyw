import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import sys
import os
import json
import datetime
import winreg

import pystray
from PIL import Image, ImageDraw
import keyboard

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "hub_config.json")


# ---------------------------------------------------------------------------
# 설정 로드 / 저장
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 실행
# ---------------------------------------------------------------------------

def _get_pythonw():
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return pythonw if os.path.exists(pythonw) else sys.executable


def launch_tool(tool_config):
    launch = tool_config["launch"]
    target = os.path.join(BASE_DIR, launch["path"])
    cwd = os.path.dirname(os.path.abspath(target))

    # 새 프로세스가 OS 포커스를 가져올 수 있도록 허용
    ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY

    if launch["type"] == "exe":
        subprocess.Popen([target], cwd=cwd)
    else:
        subprocess.Popen([_get_pythonw(), target], cwd=cwd,
                         creationflags=subprocess.CREATE_NO_WINDOW
                         if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)


# ---------------------------------------------------------------------------
# 배지 감지
# ---------------------------------------------------------------------------

def check_badge(tool_config):
    bc = tool_config.get("badge_check")
    if not bc:
        return None

    if bc["type"] == "daily_scrum_json":
        history_dir = os.path.join(BASE_DIR, bc["history_dir"])
        today_file = os.path.join(history_dir,
                                   f"{datetime.date.today().isoformat()}.json")
        if not os.path.exists(today_file):
            return "!"

    elif bc["type"] == "task_urgent":
        data_file = os.path.join(BASE_DIR, bc["data_file"])
        if not os.path.exists(data_file):
            return None
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = datetime.datetime.now()
            for t in data.get("tasks", []):
                if t.get("status") in ("완료", "취소"):
                    continue
                if t.get("priority") == "긴급":
                    return "!"
                dl = t.get("deadline")
                if dl:
                    try:
                        deadline_dt = datetime.datetime.fromisoformat(dl)
                        if deadline_dt < now:
                            return "!"
                    except ValueError:
                        pass
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# 자동 실행 (레지스트리)
# ---------------------------------------------------------------------------

_AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "ToolHub"


def set_autostart(enabled):
    pythonw = _get_pythonw()
    hub_script = os.path.join(BASE_DIR, "tool_hub.pyw")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0,
                        winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ,
                              f'"{pythonw}" "{hub_script}"')
        else:
            try:
                winreg.DeleteValue(key, _AUTOSTART_NAME)
            except FileNotFoundError:
                pass


def get_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0,
                            winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _AUTOSTART_NAME)
            return True
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# 트레이 아이콘
# ---------------------------------------------------------------------------

class TrayManager:
    def __init__(self, app):
        self.app = app
        self.icon = None

    def _make_image(self):
        icon_path = os.path.join(BASE_DIR, "hub_icon.png")
        if os.path.exists(icon_path):
            return Image.open(icon_path).resize((32, 32))
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 30, 30], fill="#2563EB")
        draw.text((10, 6), "H", fill="white")
        return img

    def _build_menu(self):
        items = [pystray.MenuItem("도구 허브 열기", self._show, default=True)]
        for tool in self.app.tools:
            t = tool
            items.append(pystray.MenuItem(
                f"  {t['icon_emoji']} {t['name']}",
                lambda _, tool=t: self.app.root.after(0, launch_tool, tool)
            ))
        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", self._quit),
        ]
        return pystray.Menu(*items)

    def _show(self, icon=None, item=None):
        self.app.root.after(0, self.app.show_window)

    def _quit(self, icon=None, item=None):
        self.app.root.after(0, self.app.quit)

    def start(self):
        self.icon = pystray.Icon(
            "tool_hub",
            self._make_image(),
            "도구 허브",
            self._build_menu()
        )
        t = threading.Thread(target=self.icon.run, daemon=True)
        t.start()

    def stop(self):
        if self.icon:
            self.icon.stop()


# ---------------------------------------------------------------------------
# 전역 단축키
# ---------------------------------------------------------------------------

class HotkeyManager:
    def __init__(self, app):
        self.app = app
        self._hotkeys = []

    def register_all(self):
        for tool in self.app.tools:
            hk = tool.get("hotkey")
            if not hk:
                continue
            t = tool
            keyboard.add_hotkey(hk, lambda tool=t: self.app.root.after(0, launch_tool, tool))
            self._hotkeys.append(hk)

    def unregister_all(self):
        for hk in self._hotkeys:
            try:
                keyboard.remove_hotkey(hk)
            except Exception:
                pass
        self._hotkeys.clear()


# ---------------------------------------------------------------------------
# 설정 패널
# ---------------------------------------------------------------------------

class SettingsPanel(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("설정")
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self.update_idletasks()   # 내용 기준으로 창 크기 자동 계산

    def _build(self):
        pad = {"padx": 16, "pady": 8}

        frm = tk.Frame(self, bg="white")
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="설정", font=("맑은 고딕", 12, "bold"),
                 bg="white").pack(**pad, anchor="w")

        self.autostart_var = tk.BooleanVar(value=get_autostart())
        ttk.Checkbutton(frm, text="Windows 시작 시 자동 실행",
                        variable=self.autostart_var).pack(**pad, anchor="w")

        self.minimized_var = tk.BooleanVar(
            value=self.app.settings.get("start_minimized", False))
        ttk.Checkbutton(frm, text="시작 시 트레이로 최소화",
                        variable=self.minimized_var).pack(padx=16, anchor="w")

        tk.Label(frm, text="단축키", font=("맑은 고딕", 10, "bold"),
                 bg="white").pack(**pad, anchor="w")
        for tool in self.app.tools:
            hk = tool.get("hotkey", "")
            if hk:
                tk.Label(frm, text=f"  {tool['icon_emoji']} {tool['name']}: {hk}",
                         font=("맑은 고딕", 9), fg="#475569",
                         bg="white").pack(padx=16, anchor="w")

        btn_frm = tk.Frame(frm, bg="white")
        btn_frm.pack(side="bottom", fill="x", padx=16, pady=12)
        ttk.Button(btn_frm, text="저장", command=self._save).pack(side="right")
        ttk.Button(btn_frm, text="취소",
                   command=self.destroy).pack(side="right", padx=4)

    def _save(self):
        set_autostart(self.autostart_var.get())
        self.app.settings["start_minimized"] = self.minimized_var.get()
        cfg = load_config()
        cfg["settings"] = self.app.settings
        save_config(cfg)
        self.destroy()


# ---------------------------------------------------------------------------
# 메인 허브 앱
# ---------------------------------------------------------------------------

class HubApp:
    COLS = 2
    CARD_BG = "white"
    CARD_HOVER_BG = "#EFF6FF"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("도구 허브")
        self.root.configure(bg="#F8FAFC")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        cfg = load_config()
        self.tools = cfg["tools"]
        self.settings = cfg.get("settings", {})

        self._badge_labels = {}

        self._build_ui()
        self._apply_geometry()

    def _apply_geometry(self):
        cols = self.COLS
        rows = (len(self.tools) + cols - 1) // cols
        w = cols * 210 + 40
        h = rows * 130 + 100
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(w, h)

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1E40AF", pady=10)
        header.pack(fill="x")

        tk.Label(header, text="🛠 도구 허브", bg="#1E40AF", fg="white",
                 font=("맑은 고딕", 13, "bold")).pack(side="left", padx=16)

        tk.Button(header, text="⚙", bg="#1E40AF", fg="white",
                  font=("맑은 고딕", 11), relief="flat", bd=0,
                  activebackground="#1D4ED8", activeforeground="white",
                  cursor="hand2",
                  command=self._open_settings).pack(side="right", padx=12)

        # Card area
        container = tk.Frame(self.root, bg="#F8FAFC")
        container.pack(fill="both", expand=True, padx=12, pady=12)

        for i, tool in enumerate(self.tools):
            row, col = divmod(i, self.COLS)
            card = self._make_card(container, tool)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            container.columnconfigure(col, weight=1)
            container.rowconfigure(row, weight=1)

        # Status bar
        self.status_var = tk.StringVar(value="준비")
        tk.Label(self.root, textvariable=self.status_var, anchor="w",
                 bg="#E2E8F0", fg="#475569", font=("맑은 고딕", 8),
                 pady=3, padx=8).pack(fill="x", side="bottom")

        self._refresh_badges()

    def _make_card(self, parent, tool):
        tid = tool["id"]

        card = tk.Frame(parent, bg=self.CARD_BG, bd=1, relief="solid",
                        cursor="hand2")

        # Badge (top-right)
        badge = tk.Label(card, text="", bg="#EF4444", fg="white",
                         font=("맑은 고딕", 8, "bold"), width=2, height=1)
        badge.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)
        self._badge_labels[tid] = badge

        inner = tk.Frame(card, bg=self.CARD_BG, padx=14, pady=12)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text=tool["icon_emoji"],
                 font=("맑은 고딕", 22), bg=self.CARD_BG).pack()
        tk.Label(inner, text=tool["name"],
                 font=("맑은 고딕", 10, "bold"), bg=self.CARD_BG).pack(pady=(2, 0))
        tk.Label(inner, text=tool.get("description", ""),
                 font=("맑은 고딕", 8), fg="#64748B", bg=self.CARD_BG,
                 wraplength=170).pack(pady=(2, 6))

        hk = tool.get("hotkey", "")
        if hk:
            tk.Label(inner, text=hk, font=("Consolas", 8), fg="#94A3B8",
                     bg="#F1F5F9", padx=4, pady=1).pack()

        # Bind click + hover on all child widgets
        def _launch(event, t=tool):
            self._launch(t)

        def _enter(event, c=card, i=inner):
            c.config(bg=self.CARD_HOVER_BG)
            i.config(bg=self.CARD_HOVER_BG)
            for w in i.winfo_children():
                try:
                    w.config(bg=self.CARD_HOVER_BG)
                except Exception:
                    pass

        def _leave(event, c=card, i=inner):
            c.config(bg=self.CARD_BG)
            i.config(bg=self.CARD_BG)
            for w in i.winfo_children():
                try:
                    w.config(bg=self.CARD_BG)
                except Exception:
                    pass

        for widget in [card, inner] + list(inner.winfo_children()):
            widget.bind("<Button-1>", _launch)
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)

        return card

    def _launch(self, tool):
        try:
            launch_tool(tool)
            self.status_var.set(f"✅ {tool['name']} 실행됨")
            self.root.after(3000, lambda: self.status_var.set("준비"))
        except Exception as e:
            self.status_var.set(f"❌ 오류: {e}")

    def _refresh_badges(self):
        for tool in self.tools:
            badge_text = check_badge(tool)
            lbl = self._badge_labels.get(tool["id"])
            if lbl:
                lbl.config(text=badge_text if badge_text else "")
        self.root.after(60_000, self._refresh_badges)

    def _open_settings(self):
        SettingsPanel(self.root, self)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        self.root.withdraw()

    def quit(self):
        self.root.destroy()

    def run(self):
        if self.settings.get("start_minimized", False):
            self.root.withdraw()
        self.root.mainloop()


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main():
    app = HubApp()

    tray = TrayManager(app)
    tray.start()

    hotkeys = HotkeyManager(app)
    hotkeys.register_all()

    app.run()

    hotkeys.unregister_all()
    tray.stop()


if __name__ == "__main__":
    # 단일 인스턴스 체크 — Named Mutex
    _MUTEX_NAME = "ToolHub_SingleInstance_Mutex"
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            0,
            "도구 허브가 이미 실행 중입니다.\n\n트레이 아이콘을 확인하세요.",
            "도구 허브",
            0x40 | 0x1000  # MB_ICONINFORMATION | MB_SYSTEMMODAL
        )
        sys.exit(0)

    main()
