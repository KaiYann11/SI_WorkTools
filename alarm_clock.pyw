import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import sys
import datetime
import time
import winsound

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "alarm_data.json")

FONT        = ("맑은 고딕", 10)
FONT_S      = ("맑은 고딕", 9)
FONT_B      = ("맑은 고딕", 11, "bold")
FONT_MONO   = ("Consolas", 32, "bold")
FONT_MONO_S = ("Consolas", 14)
FONT_MINI   = ("맑은 고딕", 8)
FONT_MINI_M = ("Consolas", 8)

BG        = "#F8FAFC"
HEADER_BG = "#1E40AF"
CARD_BG   = "white"

WEEKDAYS = [0, 1, 2, 3, 4]
WEEKEND  = [5, 6]
REPEAT_OPTIONS = ["한 번", "매일", "평일(월~금)", "주말(토~일)"]


# ---------------------------------------------------------------------------
# 데이터
# ---------------------------------------------------------------------------

def load_alarms():
    if not os.path.exists(DATA_PATH):
        return {"next_id": 1, "alarms": []}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_alarms(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def remaining_minutes(alarm_time):
    """알람까지 남은 분(int) 반환. 오류 시 9999."""
    try:
        now = datetime.datetime.now()
        h, m = map(int, alarm_time.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return int((target - now).total_seconds()) // 60
    except Exception:
        return 9999


def remaining_str(alarm_time):
    """알람까지 남은 시간 문자열 반환."""
    try:
        now = datetime.datetime.now()
        h, m = map(int, alarm_time.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        mins = int((target - now).total_seconds()) // 60
        if mins < 1:
            return "곧"
        hh, mm = divmod(mins, 60)
        return f"{hh}h {mm}m 후" if hh else f"{mm}분 후"
    except Exception:
        return "—"


# ---------------------------------------------------------------------------
# 알림 팝업
# ---------------------------------------------------------------------------

class NotificationPopup(tk.Toplevel):
    def __init__(self, parent, title, message, on_click=None, on_confirm=None):
        super().__init__(parent)
        self.on_click   = on_click
        self.on_confirm = on_confirm
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=HEADER_BG)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = 320
        h  = 100 if on_confirm else 80
        self._target_y = sh - h - 60
        self._cur_y    = sh
        self.geometry(f"{w}x{h}+{sw - w - 10}+{sh}")

        frm = tk.Frame(self, bg=HEADER_BG, padx=12, pady=8)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text=title, bg=HEADER_BG, fg="white",
                 font=("맑은 고딕", 10, "bold")).pack(anchor="w")
        tk.Label(frm, text=message, bg=HEADER_BG, fg="#BFDBFE",
                 font=FONT_S).pack(anchor="w")
        tk.Button(frm, text="✕", bg=HEADER_BG, fg="white", relief="flat",
                  font=FONT_S, cursor="hand2",
                  command=self._safe_destroy).place(relx=1.0, rely=0.0, anchor="ne")

        if on_confirm:
            btn_row = tk.Frame(frm, bg=HEADER_BG)
            btn_row.pack(anchor="w", pady=(6, 0))
            tk.Button(btn_row, text="✔ 확인", bg="#16A34A", fg="white",
                      font=FONT_S, relief="flat", cursor="hand2", padx=10, pady=3,
                      command=self._confirm).pack(side="left")

        self.after(10000, self._safe_destroy)
        self._animate()

    def _animate(self):
        if self._cur_y > self._target_y:
            self._cur_y = max(self._cur_y - 10, self._target_y)
            sw = self.winfo_screenwidth()
            self.geometry(f"320x80+{sw - 330}+{self._cur_y}")
            self.after(10, self._animate)

    def _confirm(self):
        if self.on_confirm:
            self.on_confirm()
        self._safe_destroy()

    def _click(self, event=None):
        if self.on_click:
            self.on_click()
        self._safe_destroy()

    def _safe_destroy(self):
        try:
            self.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 알람 편집 다이얼로그
# ---------------------------------------------------------------------------

class AlarmEditorDialog(tk.Toplevel):
    def __init__(self, parent, alarm=None, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self._alarm  = alarm or {}
        self.title("알람 추가" if alarm is None else "알람 수정")
        self.resizable(False, False)
        self.grab_set()
        self.attributes("-topmost", True)
        self.configure(bg="white")
        self._build()
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.lift()

    def _build(self):
        frm = tk.Frame(self, bg="white", padx=28, pady=20)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="알람 시간", bg="white", font=FONT_S,
                 fg="#374151").grid(row=0, column=0, sticky="w", pady=6)

        t = self._alarm.get("time", "08:00")
        h_val, m_val = (t.split(":") + ["00"])[:2]
        self._v_hour = tk.StringVar(value=h_val)
        self._v_min  = tk.StringVar(value=m_val)

        time_frm = tk.Frame(frm, bg="white")
        time_frm.grid(row=0, column=1, sticky="w", padx=(12, 0), pady=6)
        ttk.Spinbox(time_frm, from_=0, to=23, textvariable=self._v_hour,
                    format="%02.0f", width=4, font=FONT_B).pack(side="left")
        tk.Label(time_frm, text=":", bg="white", font=FONT_B).pack(side="left", padx=4)
        ttk.Spinbox(time_frm, from_=0, to=59, textvariable=self._v_min,
                    format="%02.0f", width=4, font=FONT_B).pack(side="left")

        tk.Label(frm, text="라벨", bg="white", font=FONT_S,
                 fg="#374151").grid(row=1, column=0, sticky="w", pady=6)
        self._v_label = tk.StringVar(value=self._alarm.get("label", ""))
        ttk.Entry(frm, textvariable=self._v_label, width=22,
                  font=FONT).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=6)

        tk.Label(frm, text="반복", bg="white", font=FONT_S,
                 fg="#374151").grid(row=2, column=0, sticky="w", pady=6)
        self._v_repeat = tk.StringVar(value=self._alarm.get("repeat", "한 번"))
        ttk.Combobox(frm, textvariable=self._v_repeat, values=REPEAT_OPTIONS,
                     state="readonly", width=20,
                     font=FONT).grid(row=2, column=1, sticky="w", padx=(12, 0), pady=6)

        btn_frm = tk.Frame(frm, bg="white")
        btn_frm.grid(row=3, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(btn_frm, text="저장",  command=self._save).pack(side="right")
        ttk.Button(btn_frm, text="취소",  command=self.destroy).pack(side="right", padx=4)

    def _save(self):
        try:
            h = int(self._v_hour.get())
            m = int(self._v_min.get())
            assert 0 <= h <= 23 and 0 <= m <= 59
        except Exception:
            messagebox.showerror("오류", "올바른 시간을 입력하세요.", parent=self)
            return
        alarm = dict(self._alarm)
        alarm["time"]   = f"{h:02d}:{m:02d}"
        alarm["label"]  = self._v_label.get().strip() or "알람"
        alarm["repeat"] = self._v_repeat.get()
        alarm.setdefault("enabled", True)
        alarm.setdefault("fired_dates", [])
        if self.on_save:
            self.on_save(alarm)
        self.destroy()


# ---------------------------------------------------------------------------
# 알람 탭
# ---------------------------------------------------------------------------

class AlarmTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()
        self.refresh()

    def _build(self):
        toolbar = tk.Frame(self, bg=BG, pady=8)
        toolbar.pack(fill="x", padx=12)
        tk.Button(toolbar, text="+ 알람 추가", bg="#2563EB", fg="white",
                  font=FONT_S, relief="flat", cursor="hand2", padx=10, pady=4,
                  command=self._add).pack(side="left")

        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._canvas = tk.Canvas(frm, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        _wid = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(_wid, width=e.width))

    def refresh(self):
        for w in self._inner.winfo_children():
            w.destroy()
        data   = load_alarms()
        alarms = sorted(data.get("alarms", []), key=lambda a: a.get("time", ""))
        if not alarms:
            tk.Label(self._inner, text="등록된 알람이 없습니다.\n'+ 알람 추가'로 추가하세요.",
                     bg=BG, fg="#94A3B8", font=FONT, justify="center").pack(pady=40)
            return
        for alarm in alarms:
            self._make_card(alarm)

    def _make_card(self, alarm):
        enabled   = alarm.get("enabled", True)
        confirmed = alarm.get("confirmed", False)

        card_bg = "#F0FDF4" if confirmed else CARD_BG
        card = tk.Frame(self._inner, bg=card_bg, bd=1, relief="solid")
        card.pack(fill="x", pady=4)
        inner = tk.Frame(card, bg=card_bg, padx=14, pady=10)
        inner.pack(fill="x")

        left = tk.Frame(inner, bg=card_bg)
        left.pack(side="left", fill="x", expand=True)

        if confirmed:
            time_color  = "#15803D"
            label_color = "#4B7C5E"
        elif enabled:
            time_color  = "#1E40AF"
            label_color = "#374151"
        else:
            time_color  = "#94A3B8"
            label_color = "#94A3B8"

        time_row = tk.Frame(left, bg=card_bg)
        time_row.pack(anchor="w")
        tk.Label(time_row, text=alarm["time"], font=("맑은 고딕", 22, "bold"),
                 bg=card_bg, fg=time_color).pack(side="left")
        if confirmed:
            tk.Label(time_row, text=" ✔ 확인됨", font=FONT_S,
                     bg=card_bg, fg="#16A34A").pack(side="left", padx=6)

        tk.Label(left, text=f"{alarm.get('label','알람')}  ·  {alarm.get('repeat','한 번')}",
                 bg=card_bg, fg=label_color, font=FONT_S).pack(anchor="w")

        right = tk.Frame(inner, bg=card_bg)
        right.pack(side="right")

        # 확인 체크 버튼
        chk_txt = "✔ 확인" if not confirmed else "✔ 확인됨"
        chk_bg  = "#16A34A" if confirmed else "#F1F5F9"
        chk_fg  = "white"   if confirmed else "#374151"
        tk.Button(right, text=chk_txt, bg=chk_bg, fg=chk_fg,
                  font=FONT_S, relief="flat", cursor="hand2", padx=8, pady=4,
                  command=lambda a=alarm: self._check(a)).pack(side="left", padx=4)

        # 켜짐/꺼짐 토글
        tog_txt = "켜짐" if enabled else "꺼짐"
        tog_bg  = "#2563EB" if enabled else "#E2E8F0"
        tog_fg  = "white"   if enabled else "#64748B"
        tk.Button(right, text=tog_txt, bg=tog_bg, fg=tog_fg,
                  font=FONT_S, relief="flat", cursor="hand2", padx=8, pady=4,
                  command=lambda a=alarm: self._toggle(a)).pack(side="left", padx=4)

        tk.Button(right, text="✏", bg="#F1F5F9", fg="#374151",
                  font=FONT_S, relief="flat", cursor="hand2", padx=6, pady=4,
                  command=lambda a=alarm: self._edit(a)).pack(side="left", padx=2)
        tk.Button(right, text="🗑", bg="#F1F5F9", fg="#EF4444",
                  font=FONT_S, relief="flat", cursor="hand2", padx=6, pady=4,
                  command=lambda a=alarm: self._delete(a)).pack(side="left", padx=2)

    def _add(self):
        AlarmEditorDialog(self, on_save=self._on_save)

    def _edit(self, alarm):
        AlarmEditorDialog(self, alarm=alarm,
                          on_save=lambda a: self._on_update(alarm["id"], a))

    def _on_save(self, alarm):
        data = load_alarms()
        alarm["id"] = data["next_id"]
        data["next_id"] += 1
        data["alarms"].append(alarm)
        save_alarms(data)
        self.refresh()

    def _on_update(self, alarm_id, alarm):
        data = load_alarms()
        for i, a in enumerate(data["alarms"]):
            if a["id"] == alarm_id:
                alarm["id"]          = alarm_id
                alarm["fired_dates"] = a.get("fired_dates", [])
                data["alarms"][i]    = alarm
                break
        save_alarms(data)
        self.refresh()

    def _toggle(self, alarm):
        data = load_alarms()
        for a in data["alarms"]:
            if a["id"] == alarm["id"]:
                a["enabled"] = not a.get("enabled", True)
                break
        save_alarms(data)
        self.refresh()

    def _delete(self, alarm):
        if messagebox.askyesno("삭제 확인",
                               f"'{alarm['label']}' 알람을 삭제하시겠습니까?",
                               parent=self):
            data = load_alarms()
            data["alarms"] = [a for a in data["alarms"] if a["id"] != alarm["id"]]
            save_alarms(data)
            self.refresh()

    def _check(self, alarm):
        data = load_alarms()
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        for a in data["alarms"]:
            if a["id"] == alarm["id"]:
                new_confirmed = not a.get("confirmed", False)
                a["confirmed"] = new_confirmed
                if new_confirmed:
                    a["confirmed_date"] = today_str
                else:
                    a.pop("confirmed_date", None)
                break
        save_alarms(data)
        self.refresh()
        # 미니 뷰 중이면 함께 갱신
        if hasattr(self.app, "_refresh_mini") and self.app._mini_mode:
            self.app._refresh_mini()


# ---------------------------------------------------------------------------
# 타이머 탭 (카운트다운)
# ---------------------------------------------------------------------------

class TimerTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app      = app
        self._remaining = 0
        self._running   = False
        self._after_id  = None
        self._build()

    def _build(self):
        center = tk.Frame(self, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        # ── 시/분/초 입력 ─────────────────────────────────────────────────
        inp = tk.Frame(center, bg=BG)
        inp.pack(pady=(0, 12))
        self._v_h = tk.StringVar(value="0")
        self._v_m = tk.StringVar(value="25")
        self._v_s = tk.StringVar(value="0")

        for col, (label, var, to) in enumerate([("시", self._v_h, 23),
                                                ("분", self._v_m, 59),
                                                ("초", self._v_s, 59)]):
            tk.Label(inp, text=label, bg=BG, fg="#64748B", font=FONT_S).grid(
                row=0, column=col, padx=8)
            ttk.Spinbox(inp, from_=0, to=to, textvariable=var,
                        format="%02.0f", width=4, font=FONT_B).grid(
                row=1, column=col, padx=8)

        # ── 프리셋 ─────────────────────────────────────────────────────────
        pf = tk.Frame(center, bg=BG)
        pf.pack(pady=(0, 16))
        for lbl, secs in [("5분", 300), ("10분", 600), ("15분", 900),
                           ("25분", 1500), ("30분", 1800), ("1시간", 3600)]:
            tk.Button(pf, text=lbl, bg="#EFF6FF", fg="#2563EB",
                      font=FONT_S, relief="flat", cursor="hand2", padx=8, pady=3,
                      command=lambda s=secs: self._preset(s)).pack(side="left", padx=3)

        # ── 디스플레이 ────────────────────────────────────────────────────
        self._disp = tk.StringVar(value="00:00:00")
        tk.Label(center, textvariable=self._disp,
                 font=FONT_MONO, bg=BG, fg="#1E40AF").pack(pady=6)

        self._status = tk.StringVar(value="")
        tk.Label(center, textvariable=self._status,
                 bg=BG, fg="#64748B", font=FONT_S).pack()

        # ── 버튼 ──────────────────────────────────────────────────────────
        bf = tk.Frame(center, bg=BG)
        bf.pack(pady=16)
        self._btn = tk.Button(bf, text="▶ 시작", bg="#2563EB", fg="white",
                              font=FONT_B, relief="flat", cursor="hand2",
                              padx=20, pady=8, command=self._toggle)
        self._btn.pack(side="left", padx=6)
        tk.Button(bf, text="↺ 초기화", bg="#F1F5F9", fg="#374151",
                  font=FONT_B, relief="flat", cursor="hand2",
                  padx=14, pady=8, command=self._reset).pack(side="left", padx=6)

    def _preset(self, secs):
        self._reset()
        h, r = divmod(secs, 3600); m, s = divmod(r, 60)
        self._v_h.set(str(h)); self._v_m.set(str(m)); self._v_s.set(str(s))
        self._remaining = secs
        self._refresh_disp()

    def _toggle(self):
        (self._pause if self._running else self._start)()

    def _start(self):
        if self._remaining == 0:
            try:
                self._remaining = (int(self._v_h.get()) * 3600
                                   + int(self._v_m.get()) * 60
                                   + int(self._v_s.get()))
            except ValueError:
                return
        if self._remaining <= 0:
            return
        self._running = True
        self._btn.config(text="⏸ 일시정지", bg="#64748B")
        self._status.set("타이머 진행 중…")
        self._tick()

    def _pause(self):
        self._running = False
        if self._after_id:
            self.after_cancel(self._after_id)
        self._btn.config(text="▶ 재개", bg="#2563EB")
        self._status.set("일시정지")

    def _reset(self):
        self._running = False
        if self._after_id:
            self.after_cancel(self._after_id)
        self._remaining = 0
        self._btn.config(text="▶ 시작", bg="#2563EB")
        self._status.set("")
        self._disp.set("00:00:00")

    def _tick(self):
        if not self._running:
            return
        if self._remaining <= 0:
            self._running = False
            self._disp.set("00:00:00")
            self._status.set("⏰ 타이머 완료!")
            self._btn.config(text="▶ 시작", bg="#2563EB")
            NotificationPopup(self.app.root, "⏰ 타이머 완료", "설정한 시간이 됐습니다!")
            threading.Thread(target=self._beep, args=(5, 880, 300), daemon=True).start()
            return
        self._refresh_disp()
        self._remaining -= 1
        self._after_id = self.after(1000, self._tick)

    def _refresh_disp(self):
        h, r = divmod(self._remaining, 3600); m, s = divmod(r, 60)
        self._disp.set(f"{h:02d}:{m:02d}:{s:02d}")

    @staticmethod
    def _beep(count, freq, dur):
        for _ in range(count):
            try:
                winsound.Beep(freq, dur)
                time.sleep(0.2)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 스톱워치 탭
# ---------------------------------------------------------------------------

class StopwatchTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app               = app
        self._elapsed          = 0.0
        self._running          = False
        self._after_id         = None
        self._t0               = None   # perf_counter base
        self._laps             = []     # list of (lap_no, lap_time, total)
        self._last_lap_elapsed = 0.0
        self._build()

    def _build(self):
        # ── 메인 디스플레이 ────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", pady=16)

        self._disp = tk.StringVar(value="00:00:00.00")
        tk.Label(top, textvariable=self._disp,
                 font=FONT_MONO, bg=BG, fg="#1E40AF").pack()

        self._lap_disp = tk.StringVar(value="")
        tk.Label(top, textvariable=self._lap_disp,
                 bg=BG, fg="#64748B", font=FONT_MONO_S).pack()

        # ── 버튼 ──────────────────────────────────────────────────────────
        bf = tk.Frame(self, bg=BG)
        bf.pack(pady=4)

        self._btn_start = tk.Button(bf, text="▶ 시작", bg="#2563EB", fg="white",
                                    font=FONT_B, relief="flat", cursor="hand2",
                                    padx=20, pady=8, command=self._toggle)
        self._btn_start.pack(side="left", padx=6)

        self._btn_lap = tk.Button(bf, text="⊙ 랩", bg="#F1F5F9", fg="#374151",
                                  font=FONT_B, relief="flat", cursor="hand2",
                                  padx=16, pady=8, state="disabled",
                                  command=self._lap)
        self._btn_lap.pack(side="left", padx=6)

        tk.Button(bf, text="↺ 초기화", bg="#F1F5F9", fg="#374151",
                  font=FONT_B, relief="flat", cursor="hand2",
                  padx=14, pady=8, command=self._reset).pack(side="left", padx=6)

        # ── 랩 목록 ────────────────────────────────────────────────────────
        lap_frm = tk.Frame(self, bg=BG)
        lap_frm.pack(fill="both", expand=True, padx=20, pady=(8, 12))

        hdr = tk.Frame(lap_frm, bg="#E2E8F0")
        hdr.pack(fill="x")
        for txt, anchor in [("랩", "center"), ("랩 타임", "center"), ("누적", "center")]:
            tk.Label(hdr, text=txt, bg="#E2E8F0", fg="#475569",
                     font=FONT_S, width=12, anchor=anchor).pack(side="left", pady=4)

        outer = tk.Frame(lap_frm, bg=BG)
        outer.pack(fill="both", expand=True)

        self._lc = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=self._lc.yview)
        self._lc.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._lc.pack(side="left", fill="both", expand=True)

        self._li = tk.Frame(self._lc, bg=BG)
        _wid = self._lc.create_window((0, 0), window=self._li, anchor="nw")
        self._li.bind("<Configure>", lambda e: self._lc.configure(
            scrollregion=self._lc.bbox("all")))
        self._lc.bind("<Configure>", lambda e: self._lc.itemconfig(_wid, width=e.width))

    # ── 스톱워치 로직 ──────────────────────────────────────────────────────

    def _toggle(self):
        (self._stop if self._running else self._start)()

    def _start(self):
        self._running = True
        self._t0 = time.perf_counter() - self._elapsed
        self._btn_start.config(text="⏸ 정지", bg="#EF4444")
        self._btn_lap.config(state="normal")
        self._tick()

    def _stop(self):
        self._running = False
        if self._after_id:
            self.after_cancel(self._after_id)
        self._elapsed = time.perf_counter() - self._t0
        self._btn_start.config(text="▶ 재개", bg="#2563EB")
        self._btn_lap.config(state="disabled")

    def _reset(self):
        self._running          = False
        self._elapsed          = 0.0
        self._t0               = None
        self._laps             = []
        self._last_lap_elapsed = 0.0
        if self._after_id:
            self.after_cancel(self._after_id)
        self._disp.set("00:00:00.00")
        self._lap_disp.set("")
        self._btn_start.config(text="▶ 시작", bg="#2563EB")
        self._btn_lap.config(state="disabled")
        self._render_laps()

    def _lap(self):
        lap_t = self._elapsed - self._last_lap_elapsed
        self._laps.append((len(self._laps) + 1, lap_t, self._elapsed))
        self._last_lap_elapsed = self._elapsed
        self._render_laps()

    def _tick(self):
        if not self._running:
            return
        self._elapsed = time.perf_counter() - self._t0
        self._disp.set(self._fmt(self._elapsed))
        cur_lap = self._elapsed - self._last_lap_elapsed
        self._lap_disp.set(f"현재 랩  {self._fmt(cur_lap)}" if self._laps else "")
        self._after_id = self.after(30, self._tick)

    @staticmethod
    def _fmt(secs):
        h  = int(secs // 3600)
        m  = int((secs % 3600) // 60)
        s  = int(secs % 60)
        cs = int((secs * 100) % 100)
        return f"{h:02d}:{m:02d}:{s:02d}.{cs:02d}"

    def _render_laps(self):
        for w in self._li.winfo_children():
            w.destroy()
        if not self._laps:
            return

        times = [t for _, t, _ in self._laps]
        best  = min(times)
        worst = max(times)

        for lap_no, lap_t, total in reversed(self._laps):
            is_best  = (lap_t == best  and len(self._laps) > 1)
            is_worst = (lap_t == worst and len(self._laps) > 1)
            row_bg = "#EFF6FF" if lap_no == len(self._laps) else BG
            row = tk.Frame(self._li, bg=row_bg, pady=2)
            row.pack(fill="x")

            lap_fg = ("#16A34A" if is_best else "#EF4444" if is_worst else "#374151")
            font_w = "bold" if (is_best or is_worst) else "normal"

            tk.Label(row, text=f"랩 {lap_no}", bg=row_bg, fg="#2563EB",
                     font=FONT_S, width=12, anchor="center").pack(side="left")
            tk.Label(row, text=self._fmt(lap_t), bg=row_bg, fg=lap_fg,
                     font=("Consolas", 11, font_w),
                     width=14, anchor="center").pack(side="left")
            tk.Label(row, text=self._fmt(total), bg=row_bg, fg="#64748B",
                     font=("Consolas", 11), width=14, anchor="center").pack(side="left")

        self._lc.yview_moveto(0.0)


# ---------------------------------------------------------------------------
# 알람 백그라운드 체크 스레드
# ---------------------------------------------------------------------------

class AlarmNotifier:
    def __init__(self, app):
        self.app          = app
        self._fired_today = set()   # (alarm_id, date_str)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                self._check()
            except Exception:
                pass
            time.sleep(10)

    def _check(self):
        n            = datetime.datetime.now()
        today_str    = n.strftime("%Y-%m-%d")
        current_time = n.strftime("%H:%M")
        weekday      = n.weekday()
        changed      = False

        data = load_alarms()
        for alarm in data.get("alarms", []):
            if not alarm.get("enabled", True):
                continue

            # 반복 알람: 날짜가 바뀌었거나 오늘 알람 시간이 지나면 자동 해제
            repeat = alarm.get("repeat", "한 번")
            if repeat != "한 번" and alarm.get("confirmed", False):
                confirmed_date = alarm.get("confirmed_date", "")
                alarm_time_str = alarm.get("time", "")
                should_reset = (
                    confirmed_date != today_str or
                    (confirmed_date == today_str and current_time > alarm_time_str)
                )
                if should_reset:
                    alarm["confirmed"] = False
                    alarm.pop("confirmed_date", None)
                    changed = True

            # confirmed 상태면 알람 울리지 않음
            if alarm.get("confirmed", False):
                continue

            if alarm.get("time") != current_time:
                continue

            key = (alarm["id"], today_str)
            if key in self._fired_today:
                continue

            should = False
            if repeat == "한 번":
                should = today_str not in alarm.get("fired_dates", [])
            elif repeat == "매일":
                should = True
            elif repeat == "평일(월~금)":
                should = weekday in WEEKDAYS
            elif repeat == "주말(토~일)":
                should = weekday in WEEKEND

            if not should:
                continue

            self._fired_today.add(key)
            if repeat == "한 번":
                alarm.setdefault("fired_dates", []).append(today_str)
                changed = True

            label = alarm.get("label", "알람")
            t     = alarm["time"]
            aid   = alarm["id"]
            self.app.root.after(0, lambda l=label, tm=t, i=aid: self._notify(l, tm, i))

        if changed:
            save_alarms(data)

    def _notify(self, label, alarm_time, alarm_id):
        def on_confirm():
            self.app.confirm_alarm(alarm_id)
        NotificationPopup(self.app.root, f"⏰ {alarm_time}", label, on_confirm=on_confirm)
        threading.Thread(target=TimerTab._beep, args=(5, 660, 400), daemon=True).start()


# ---------------------------------------------------------------------------
# 메인 앱
# ---------------------------------------------------------------------------

class AlarmClockApp:
    _FULL_GEO = "480x580"
    _MINI_W   = 420

    def __init__(self):
        self.root            = tk.Tk()
        self._mini_mode      = False
        self._topmost        = False
        self._mini_after_id  = None
        self._blink_after_ids = []
        self.root.title("알람 설정기")
        self.root.configure(bg=BG)
        self.root.geometry(self._FULL_GEO)
        self.root.minsize(440, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._build_ui()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # 헤더
        self._hdr_frame = tk.Frame(self.root, bg=HEADER_BG, pady=10)
        self._hdr_frame.pack(fill="x")

        # 버튼 먼저 pack (right side 우선)
        self._btn_mini = tk.Button(
            self._hdr_frame, text="⊟", bg=HEADER_BG, fg="white",
            font=("맑은 고딕", 13), relief="flat", cursor="hand2",
            activebackground="#1D4ED8", activeforeground="white",
            command=self._toggle_mini)
        self._btn_mini.pack(side="right", padx=4)

        self._btn_top = tk.Button(
            self._hdr_frame, text="📌", bg=HEADER_BG, fg="#93C5FD",
            font=("맑은 고딕", 11), relief="flat", cursor="hand2",
            activebackground="#1D4ED8", activeforeground="white",
            command=self._toggle_topmost)
        self._btn_top.pack(side="right", padx=4)

        # + 알람 추가 버튼 (미니 모드 전용, 고정/최소화 버튼 왼쪽)
        self._btn_mini_add = tk.Button(
            self._hdr_frame, text="+ 알람", bg="#2563EB", fg="white",
            font=("맑은 고딕", 9), relief="flat", cursor="hand2",
            activebackground="#1D4ED8", activeforeground="white",
            command=self._mini_add)
        # 미니 모드 진입 시에만 pack

        # 타이틀 (right 버튼들 이후 left pack)
        self._hdr_title = tk.Label(
            self._hdr_frame, text="⏰ 알람 설정기", bg=HEADER_BG, fg="white",
            font=("맑은 고딕", 13, "bold"))
        self._hdr_title.pack(side="left", padx=16)

        # 풀 뷰: Notebook
        self._nb = ttk.Notebook(self.root)
        self._nb.pack(fill="both", expand=True)

        self._alarm_tab = AlarmTab(self._nb, self)
        self._timer_tab = TimerTab(self._nb, self)
        self._sw_tab    = StopwatchTab(self._nb, self)

        self._nb.add(self._alarm_tab, text="  알람  ")
        self._nb.add(self._timer_tab, text="  타이머  ")
        self._nb.add(self._sw_tab,    text="  스톱워치  ")

        # 미니 뷰 프레임 (숨김 상태로 준비)
        self._mini_frame = tk.Frame(self.root, bg=BG)

    # ── 최소화 토글 ──────────────────────────────────────────────────────────

    def _toggle_mini(self):
        if self._mini_mode:
            self._expand()
        else:
            self._minimize()

    def _minimize(self):
        self._mini_mode = True
        self._nb.pack_forget()
        self._hdr_title.pack_forget()
        self._hdr_frame.config(pady=0)
        self._btn_mini.config(font=("맑은 고딕", 9), padx=3, pady=1)
        self._btn_top.config(font=("맑은 고딕", 9), padx=3, pady=1)

        # KST/UTC 시계 레이블
        self._mini_clock_var = tk.StringVar()
        self._mini_clock_lbl = tk.Label(
            self._hdr_frame, textvariable=self._mini_clock_var,
            bg=HEADER_BG, fg="#BFDBFE", font=("Consolas", 8))
        self._mini_clock_lbl.pack(side="left", padx=6)
        self._mini_clock_after = None
        self._update_mini_clock()

        self._btn_mini_add.pack(side="right", padx=4)
        self._btn_mini_add.config(padx=4, pady=1)

        self._mini_frame.pack(fill="both", expand=True)
        self._btn_mini.config(text="⊞")
        self.root.minsize(0, 0)
        self._refresh_mini()

    def _expand(self):
        self._mini_mode = False
        for aid in self._blink_after_ids:
            try: self.root.after_cancel(aid)
            except Exception: pass
        self._blink_after_ids.clear()
        if self._mini_after_id:
            self.root.after_cancel(self._mini_after_id)
            self._mini_after_id = None
        # 시계 정리
        if hasattr(self, "_mini_clock_after") and self._mini_clock_after:
            try: self.root.after_cancel(self._mini_clock_after)
            except Exception: pass
        if hasattr(self, "_mini_clock_lbl"):
            try: self._mini_clock_lbl.pack_forget()
            except Exception: pass

        self._mini_frame.pack_forget()
        self._btn_mini_add.pack_forget()
        self._hdr_frame.config(pady=10)
        self._btn_mini.config(font=("맑은 고딕", 13), padx=4, pady=0, text="⊟")
        self._btn_top.config(font=("맑은 고딕", 11), padx=4, pady=0)
        self._hdr_title.pack(side="left", padx=16)
        self._nb.pack(fill="both", expand=True)
        self.root.minsize(440, 520)
        self.root.geometry(self._FULL_GEO)
        self._alarm_tab.refresh()

    # ── 미니 뷰 렌더 ─────────────────────────────────────────────────────────

    def _refresh_mini(self):
        # 기존 blink 취소
        for aid in self._blink_after_ids:
            try: self.root.after_cancel(aid)
            except Exception: pass
        self._blink_after_ids.clear()

        if self._mini_after_id:
            self.root.after_cancel(self._mini_after_id)
            self._mini_after_id = None

        for w in self._mini_frame.winfo_children():
            w.destroy()

        data   = load_alarms()
        alarms = sorted(data.get("alarms", []), key=lambda a: a.get("time", ""))

        # ── 알람 행 (헤더 없음) ──
        if not alarms:
            tk.Label(self._mini_frame, text="등록된 알람이 없습니다.",
                     bg=BG, fg="#94A3B8", font=FONT_MINI).pack(pady=10)
        else:
            for alarm in alarms:
                self._make_mini_row(alarm)

        # 창 높이 자동 조정 (헤더 바 ~28px + 행당 26px + 버튼 행 24px)
        HDR_H = 28
        ROW_H = 26
        BTN_H = 24
        n = max(len(alarms), 1)
        h = HDR_H + n * ROW_H + BTN_H + 8
        self.root.geometry(f"{self._MINI_W}x{h}")

        # 30초마다 남은시간 갱신
        if self._mini_mode:
            self._mini_after_id = self.root.after(30_000, self._refresh_mini)

    def _make_mini_row(self, alarm):
        confirmed = alarm.get("confirmed", False)
        enabled   = alarm.get("enabled", True)

        # ── 남은 시간 & 색상 결정 ──
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        already_fired = (alarm.get("repeat") == "한 번" and
                         today_str in alarm.get("fired_dates", []))

        if already_fired:
            rem_str = "완료"
            rem_min = 9999
            base_bg = "#DCFCE7"
            rem_fg  = "#15803D"
        elif not enabled:
            rem_str = "꺼짐"
            rem_min = 9999
            base_bg = "#E2E8F0"
            rem_fg  = "#94A3B8"
        else:
            rem_min = remaining_minutes(alarm["time"])
            rem_str = remaining_str(alarm["time"])
            if rem_min < 10:
                base_bg = "#FCA5A5"   # 10분 미만 — 빨강 (깜빡임)
                rem_fg  = "#7F1D1D"
            elif rem_min < 30:
                base_bg = "#FED7AA"   # 30분 미만 — 주황
                rem_fg  = "#92400E"
            elif rem_min < 60:
                base_bg = "#FEF08A"   # 1시간 미만 — 노랑
                rem_fg  = "#713F12"
            else:
                base_bg = "white"
                rem_fg  = "#374151"

        if confirmed:
            base_bg = "#DCFCE7"
            rem_fg  = "#15803D"

        row = tk.Frame(self._mini_frame, bg=base_bg)
        row.pack(fill="x", padx=0, pady=0)

        # 라벨 + 반복주기
        lbl_txt = ("✔ " if confirmed else "") + alarm.get("label", "알람")
        repeat  = alarm.get("repeat", "한 번")
        lbl_fg  = "#15803D" if confirmed else ("#374151" if enabled else "#94A3B8")
        tk.Label(row, text=lbl_txt, bg=base_bg, fg=lbl_fg,
                 font=FONT_MINI, anchor="w").pack(side="left", padx=(6, 2), pady=3)
        tk.Label(row, text=f"[{repeat}]", bg=base_bg, fg="#94A3B8",
                 font=FONT_MINI, anchor="w").pack(side="left", pady=3)

        # 버튼
        btn_frm = tk.Frame(row, bg=base_bg)
        btn_frm.pack(side="right", padx=4)
        chk_bg = "#16A34A" if confirmed else "#E5E7EB"
        chk_fg = "white"   if confirmed else "#374151"
        tk.Button(btn_frm, text="✔", bg=chk_bg, fg=chk_fg,
                  font=FONT_MINI, relief="flat", cursor="hand2", padx=3, pady=1,
                  command=lambda a=alarm: self._mini_check(a)).pack(side="left", padx=1)
        tk.Button(btn_frm, text="✏", bg="#E5E7EB", fg="#374151",
                  font=FONT_MINI, relief="flat", cursor="hand2", padx=3, pady=1,
                  command=lambda a=alarm: self._mini_edit(a)).pack(side="left", padx=1)
        tk.Button(btn_frm, text="🗑", bg="#E5E7EB", fg="#EF4444",
                  font=FONT_MINI, relief="flat", cursor="hand2", padx=3, pady=1,
                  command=lambda a=alarm: self._mini_delete(a)).pack(side="left", padx=1)

        # 남은 시간 (버튼 왼쪽)
        rem_lbl = tk.Label(btn_frm, text=rem_str, bg=base_bg, fg=rem_fg,
                           font=FONT_MINI_M, width=9, anchor="center")
        rem_lbl.pack(side="left", padx=(4, 6))

        # 구분선
        tk.Frame(self._mini_frame, bg="#E2E8F0", height=1).pack(fill="x")

        # 10분 미만이면 깜빡임 시작 (confirmed 상태면 깜빡이지 않음)
        if enabled and not confirmed and rem_min < 10:
            self._start_blink(row, rem_lbl, base_bg)

    def _start_blink(self, row_widget, rem_label, base_color, interval=600):
        """row_widget 배경을 base_color ↔ 연한 색으로 교대 깜빡임."""
        blink_color = "#F87171"   # 더 진한 빨강
        state = [True]

        def _toggle():
            if not row_widget.winfo_exists():
                return
            cur = base_color if state[0] else blink_color
            row_widget.config(bg=cur)
            for child in row_widget.winfo_children():
                try: child.config(bg=cur)
                except Exception: pass
            rem_label.config(bg=cur)
            state[0] = not state[0]
            aid = self.root.after(interval, _toggle)
            self._blink_after_ids.append(aid)

        _toggle()

    def _mini_check(self, alarm):
        data = load_alarms()
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        for a in data["alarms"]:
            if a["id"] == alarm["id"]:
                new_confirmed = not a.get("confirmed", False)
                a["confirmed"] = new_confirmed
                if new_confirmed:
                    a["confirmed_date"] = today_str
                else:
                    a.pop("confirmed_date", None)
                break
        save_alarms(data)
        self._refresh_mini()

    def _mini_add(self):
        def on_save(alarm):
            data = load_alarms()
            alarm["id"] = data["next_id"]
            data["next_id"] += 1
            data["alarms"].append(alarm)
            save_alarms(data)
            self._refresh_mini()
        AlarmEditorDialog(self.root, on_save=on_save)

    def _mini_edit(self, alarm):
        def on_save(updated):
            data = load_alarms()
            for i, a in enumerate(data["alarms"]):
                if a["id"] == alarm["id"]:
                    updated["id"]          = alarm["id"]
                    updated["fired_dates"] = a.get("fired_dates", [])
                    updated["confirmed"]   = a.get("confirmed", False)
                    data["alarms"][i]      = updated
                    break
            save_alarms(data)
            self._refresh_mini()
        AlarmEditorDialog(self.root, alarm=alarm, on_save=on_save)

    def _mini_delete(self, alarm):
        if messagebox.askyesno("삭제 확인",
                               f"'{alarm['label']}' 알람을 삭제하시겠습니까?",
                               parent=self.root):
            data = load_alarms()
            data["alarms"] = [a for a in data["alarms"] if a["id"] != alarm["id"]]
            save_alarms(data)
            self._refresh_mini()

    def _update_mini_clock(self):
        if not self._mini_mode:
            return
        now_kst = datetime.datetime.now()
        now_utc = datetime.datetime.utcnow()
        if hasattr(self, "_mini_clock_var"):
            self._mini_clock_var.set(
                f"KST {now_kst.strftime('%H:%M:%S')}  UTC {now_utc.strftime('%H:%M:%S')}")
        self._mini_clock_after = self.root.after(1000, self._update_mini_clock)

    # ── 항상 위 토글 ─────────────────────────────────────────────────────────

    def _toggle_topmost(self):
        self._topmost = not self._topmost
        self.root.attributes("-topmost", self._topmost)
        if self._topmost:
            self._btn_top.config(bg="#2563EB", fg="white")
        else:
            self._btn_top.config(bg=HEADER_BG, fg="#93C5FD")

    # ── 공용 메서드 ───────────────────────────────────────────────────────────

    def confirm_alarm(self, alarm_id):
        """토스트 팝업의 '✔ 확인' 버튼에서 호출."""
        data = load_alarms()
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        for a in data["alarms"]:
            if a["id"] == alarm_id:
                a["confirmed"] = True
                a["confirmed_date"] = today_str
                break
        save_alarms(data)
        self._alarm_tab.refresh()
        if self._mini_mode:
            self._refresh_mini()

    def run(self):
        AlarmNotifier(self)
        self.root.mainloop()


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main():
    AlarmClockApp().run()


if __name__ == "__main__":
    _MUTEX_NAME = "AlarmClock_SingleInstance_Mutex"
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(
            0, "알람 설정기가 이미 실행 중입니다.", "알람 설정기",
            0x40 | 0x1000)
        sys.exit(0)
    main()
