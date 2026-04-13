import ctypes
import ctypes.wintypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import threading
import time
from datetime import datetime, date, timedelta
from tkcalendar import Calendar, DateEntry

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "task_manager_data.json")

TASK_TYPES    = ["구현", "설계", "디버깅", "테스트", "배포", "분석", "회의", "기타"]
PRIORITIES    = ["긴급", "높음", "보통", "낮음"]
STATUSES      = ["대기", "진행중", "완료", "취소"]
ALL_FILTER    = "전체"

PRIORITY_COLOR = {"긴급": "#FEE2E2", "높음": "#FEF9C3", "보통": "#DBEAFE", "낮음": "#F3F4F6"}
STATUS_COLOR   = {"대기": "#F3F4F6", "진행중": "#DBEAFE", "완료": "#D1FAE5", "취소": "#E5E7EB"}

FONT      = ("맑은 고딕", 10)
FONT_B    = ("맑은 고딕", 10, "bold")
FONT_S    = ("맑은 고딕", 9)
FONT_H    = ("맑은 고딕", 13, "bold")


# ---------------------------------------------------------------------------
# 데이터
# ---------------------------------------------------------------------------

def load_data():
    if not os.path.exists(DATA_PATH):
        d = {"next_id": 1, "next_memo_id": 1, "today_display_order": [], "tasks": []}
        save_data(d)
        return d
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("today_display_order", [])
    return d


def save_data(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_str():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def fmt_dt(s):
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s


def parse_effort_min(s):
    """'1d 4h 30m' → 총 분 (1d=8h 기준)"""
    if not s:
        return 0
    import re
    total = 0
    for val, unit in re.findall(r'(\d+(?:\.\d+)?)\s*([dDhHmM])', s):
        v = float(val)
        u = unit.lower()
        if u == 'd':
            total += v * 8 * 60
        elif u == 'h':
            total += v * 60
        elif u == 'm':
            total += v
    return int(total)


def format_effort_min(minutes):
    """총 분 → '1d 4h 30m' (1d=8h)"""
    if minutes <= 0:
        return "—"
    d, rem = divmod(int(minutes), 8 * 60)
    h, m   = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    return " ".join(parts) or "—"


def fmt_dt_short(s):
    """목록용 단축 표시: MM-DD HH:MM"""
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s).strftime("%m-%d %H:%M")
    except Exception:
        return s


def calc_dday(deadline_str):
    if not deadline_str:
        return ""
    try:
        dl = datetime.fromisoformat(deadline_str).date()
        delta = (dl - date.today()).days
        if delta < 0:
            return f"D+{-delta}"
        if delta == 0:
            return "D-Day"
        return f"D-{delta}"
    except Exception:
        return ""


def make_task(data, **kw):
    tid = data["next_id"]
    data["next_id"] += 1
    now = now_str()
    task = {
        "id": tid,
        "title": "",
        "project": "",
        "system": "",
        "type": "구현",
        "assignee": "",
        "priority": "보통",
        "status": "대기",
        "scheduled_at": "",
        "deadline": "",
        "notify_before_min": 30,
        "description": "",
        "tags": [],
        "seq_order": None,
        "parent_id": None,
        "sub_ids": [],
        "linked_ids": [],
        "effort": "",
        "actual_effort": "",
        "change_history": [],
        "memos": [],
        "todos": [],
        "result": {"summary": "", "score": None, "feedback": ""},
        "created_at": now,
        "updated_at": now,
    }
    task.update(kw)
    return task


def get_task(data, tid):
    return next((t for t in data["tasks"] if t["id"] == tid), None)


# ---------------------------------------------------------------------------
# 알림 팝업
# ---------------------------------------------------------------------------

class NotificationPopup(tk.Toplevel):
    def __init__(self, parent, title, message, on_click=None):
        super().__init__(parent)
        self.on_click = on_click
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#1E293B")

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 320, 72
        self.geometry(f"{w}x{h}+{sw - w - 12}+{sh - h - 60}")

        tk.Label(self, text=title, bg="#1E293B", fg="#F8FAFC",
                 font=FONT_B, anchor="w").pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(self, text=message, bg="#1E293B", fg="#94A3B8",
                 font=FONT_S, anchor="w", wraplength=290).pack(fill="x", padx=12)

        self.bind("<Button-1>", self._clicked)
        for w in self.winfo_children():
            w.bind("<Button-1>", self._clicked)

        self.after(6000, self._close)

    def _clicked(self, event=None):
        if self.on_click:
            self.on_click()
        self._close()

    def _close(self):
        try:
            self.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 알림 관리
# ---------------------------------------------------------------------------

class NotificationManager:
    def __init__(self, app):
        self.app = app
        self._notified = set()   # (task_id, event_type)
        self._stop = False

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def stop(self):
        self._stop = True

    def _loop(self):
        while not self._stop:
            try:
                self._check()
            except Exception:
                pass
            time.sleep(60)

    def _check(self):
        data = load_data()
        now = datetime.now()
        for task in data["tasks"]:
            if task["status"] in ("완료", "취소"):
                continue
            tid = task["id"]
            title = task["title"]

            # 시작 시간 알림
            sch = task.get("scheduled_at")
            if sch and ("start", tid) not in self._notified:
                try:
                    sch_dt = datetime.fromisoformat(sch)
                    if sch_dt <= now < sch_dt + timedelta(minutes=2):
                        self._notified.add(("start", tid))
                        self.app.root.after(0, lambda t=title, tid=tid: self._show(
                            "🔔 작업 시작", f"{t}", tid))
                except Exception:
                    pass

            # 마감 임박 알림
            dl = task.get("deadline")
            nbm = task.get("notify_before_min", 30)
            if dl and ("deadline_warn", tid) not in self._notified:
                try:
                    dl_dt = datetime.fromisoformat(dl)
                    warn_dt = dl_dt - timedelta(minutes=nbm)
                    if warn_dt <= now < dl_dt:
                        self._notified.add(("deadline_warn", tid))
                        self.app.root.after(0, lambda t=title, n=nbm, tid=tid: self._show(
                            f"⚠ 마감 {n}분 전", f"{t}", tid))
                except Exception:
                    pass

            # 마감 초과
            if dl and ("overdue", tid) not in self._notified:
                try:
                    dl_dt = datetime.fromisoformat(dl)
                    if now > dl_dt + timedelta(minutes=2):
                        self._notified.add(("overdue", tid))
                        self.app.root.after(0, lambda t=title, tid=tid: self._show(
                            "❌ 마감 초과", f"{t}", tid))
                except Exception:
                    pass

    def _show(self, title, message, task_id):
        def on_click():
            self.app.select_task(task_id)
            self.app.root.deiconify()
            self.app.root.lift()
        NotificationPopup(self.app.root, title, message, on_click)


# ---------------------------------------------------------------------------
# 메모 추가 다이얼로그
# ---------------------------------------------------------------------------

class MemoAddDialog(tk.Toplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.on_save = on_save
        self.title("메모 추가")
        self.geometry("440x180")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        self.configure(bg="white")
        tk.Label(self, text="메모 내용 (Ctrl+Enter 저장, Esc 취소)",
                 bg="white", fg="#475569", font=FONT_S).pack(anchor="w", padx=12, pady=(10, 4))
        self.txt = tk.Text(self, height=4, font=FONT, relief="solid", bd=1)
        self.txt.pack(fill="both", expand=True, padx=12)
        self.txt.bind("<Control-Return>", lambda e: self._save())
        self.txt.bind("<Escape>", lambda e: self.destroy())
        self.txt.focus_set()

        btn_frm = tk.Frame(self, bg="white")
        btn_frm.pack(fill="x", padx=12, pady=8)
        ttk.Button(btn_frm, text="저장", command=self._save).pack(side="right")
        ttk.Button(btn_frm, text="취소", command=self.destroy).pack(side="right", padx=4)

    def _save(self):
        content = self.txt.get("1.0", "end").strip()
        if content:
            self.on_save(content)
        self.destroy()


# ---------------------------------------------------------------------------
# 작업 연결 선택 팝업
# ---------------------------------------------------------------------------

class LinkSelectorDialog(tk.Toplevel):
    def __init__(self, parent, tasks, exclude_ids, on_select):
        super().__init__(parent)
        self.on_select = on_select
        self.title("작업 연결")
        self.geometry("400x300")
        self.grab_set()
        self._build(tasks, exclude_ids)

    def _build(self, tasks, exclude_ids):
        self.configure(bg="white")
        tk.Label(self, text="연결할 작업을 선택하세요", bg="white",
                 font=FONT_B).pack(anchor="w", padx=12, pady=(10, 4))

        frm = tk.Frame(self, bg="white")
        frm.pack(fill="both", expand=True, padx=12, pady=4)
        sb = ttk.Scrollbar(frm)
        self.lb = tk.Listbox(frm, font=FONT, yscrollcommand=sb.set,
                             selectbackground="#DBEAFE", selectforeground="#1E40AF",
                             relief="solid", bd=1)
        sb.config(command=self.lb.yview)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._task_ids = []
        for t in tasks:
            if t["id"] not in exclude_ids:
                self.lb.insert("end", f"[{t['id']}] {t['title']} ({t['status']})")
                self._task_ids.append(t["id"])

        self.lb.bind("<Double-1>", self._select)
        ttk.Button(self, text="선택", command=self._select).pack(pady=8)

    def _select(self, event=None):
        sel = self.lb.curselection()
        if not sel:
            return
        self.on_select(self._task_ids[sel[0]])
        self.destroy()


# ---------------------------------------------------------------------------
# 날짜+시간 선택 팝업
# ---------------------------------------------------------------------------

class DateTimePickerDialog(tk.Toplevel):
    """캘린더 + 시/분 선택 팝업. 확인 시 'YYYY-MM-DDTHH:MM' 문자열을 반환."""

    def __init__(self, parent, initial_value="", default_hour=9):
        super().__init__(parent)
        self.result = None
        self.title("날짜 · 시간 선택")
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg="white")

        # 초기값 파싱
        init_dt = None
        if initial_value:
            try:
                init_dt = datetime.fromisoformat(initial_value)
            except Exception:
                pass

        today = init_dt.date() if init_dt else date.today()
        init_h = init_dt.hour if init_dt else default_hour
        init_m = init_dt.minute if init_dt else 0

        # 캘린더
        self._cal = Calendar(
            self, selectmode="day", locale="ko_KR",
            year=today.year, month=today.month, day=today.day,
            background="#1E40AF", foreground="white",
            headersbackground="#1E3A8A", headersforeground="white",
            selectbackground="#2563EB", selectforeground="white",
            weekendforeground="#EF4444",
            font=FONT_S,
        )
        self._cal.pack(padx=12, pady=(12, 6))

        # 시간 선택
        time_frm = tk.Frame(self, bg="white")
        time_frm.pack(pady=(0, 8))
        tk.Label(time_frm, text="시간", bg="white", font=FONT_S,
                 fg="#374151").pack(side="left", padx=(0, 6))

        self._v_hour = tk.StringVar(value=f"{init_h:02d}")
        self._v_min  = tk.StringVar(value=f"{init_m:02d}")

        ttk.Spinbox(time_frm, from_=0, to=23, width=4,
                    textvariable=self._v_hour, format="%02.0f",
                    font=FONT).pack(side="left")
        tk.Label(time_frm, text=":", bg="white", font=FONT_B).pack(side="left", padx=2)
        ttk.Spinbox(time_frm, from_=0, to=59, width=4,
                    textvariable=self._v_min, format="%02.0f",
                    font=FONT).pack(side="left")

        # 버튼
        btn_frm = tk.Frame(self, bg="white")
        btn_frm.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btn_frm, text="확인", command=self._ok).pack(side="right")
        ttk.Button(btn_frm, text="취소", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btn_frm, text="지우기", command=self._clear).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _ok(self):
        try:
            sel = self._cal.selection_get()
        except Exception:
            sel = date.today()
        try:
            h = max(0, min(23, int(self._v_hour.get())))
            m = max(0, min(59, int(self._v_min.get())))
        except ValueError:
            h, m = 0, 0
        self.result = f"{sel.isoformat()}T{h:02d}:{m:02d}"
        self.destroy()

    def _clear(self):
        self.result = ""
        self.destroy()


def pick_datetime(parent, initial_value="", default_hour=9):
    """모달 날짜+시간 선택. 취소 시 None, 지우기 시 '' 반환."""
    dlg = DateTimePickerDialog(parent, initial_value, default_hour=default_hour)
    parent.wait_window(dlg)
    return dlg.result


# ---------------------------------------------------------------------------
# 변경 이력 코멘트 팝업
# ---------------------------------------------------------------------------

class ChangeCommentDialog(tk.Toplevel):
    """변경 항목 표시 + 코멘트 입력 후 on_confirm(comment) 호출."""

    def __init__(self, parent, changes, on_confirm):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.title("변경 이력 기록")
        self.geometry("460x300")
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg="white")
        self._build(changes)

    def _build(self, changes):
        tk.Label(self, text="다음 항목이 변경됩니다. 변경 사유를 입력하세요.",
                 bg="white", font=FONT_S, fg="#374151").pack(anchor="w", padx=14, pady=(12, 6))

        # 변경 목록
        chg_frm = tk.Frame(self, bg="#F8FAFC", relief="solid", bd=1)
        chg_frm.pack(fill="x", padx=14, pady=(0, 8))
        for c in changes:
            old = fmt_dt(c["old"]) if "T" in str(c["old"]) else c["old"]
            new = fmt_dt(c["new"]) if "T" in str(c["new"]) else c["new"]
            text = f"  {c['field']}:  {old or '(없음)'}  →  {new or '(없음)'}"
            tk.Label(chg_frm, text=text, bg="#F8FAFC", font=FONT_S,
                     fg="#1E40AF", anchor="w").pack(fill="x", padx=6, pady=2)

        tk.Label(self, text="변경 사유 (선택사항, Ctrl+Enter 저장)",
                 bg="white", font=FONT_S, fg="#64748B").pack(anchor="w", padx=14)
        self.txt = tk.Text(self, height=4, font=FONT, relief="solid", bd=1)
        self.txt.pack(fill="both", expand=True, padx=14, pady=4)
        self.txt.bind("<Control-Return>", lambda e: self._ok())
        self.txt.bind("<Escape>", lambda e: self.destroy())
        self.txt.focus_set()

        btn_frm = tk.Frame(self, bg="white")
        btn_frm.pack(fill="x", padx=14, pady=(4, 12))
        ttk.Button(btn_frm, text="이력 저장", command=self._ok).pack(side="right")
        ttk.Button(btn_frm, text="취소", command=self.destroy).pack(side="right", padx=4)

    def _ok(self):
        comment = self.txt.get("1.0", "end").strip()
        self.destroy()
        self.on_confirm(comment)


# ---------------------------------------------------------------------------
# 작업 편집기
# ---------------------------------------------------------------------------

class TaskEditor(tk.Toplevel):
    def __init__(self, parent, app, task=None, on_save=None):
        super().__init__(parent)
        self.app = app
        self.task = task
        self.on_save = on_save
        self.title("작업 추가" if task is None else "작업 수정")
        self.geometry("580x620")
        self.resizable(True, True)
        self.grab_set()
        self._build()
        if task:
            self._fill(task)

    def _build(self):
        self.configure(bg="white")

        # 버튼을 먼저 pack해야 창 크기와 무관하게 항상 표시됨
        btn_frm = tk.Frame(self, bg="white")
        btn_frm.pack(side="bottom", fill="x", padx=12, pady=(0, 10))
        ttk.Button(btn_frm, text="저장", command=self._save).pack(side="right")
        ttk.Button(btn_frm, text="취소", command=self.destroy).pack(side="right", padx=4)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── 기본 탭
        basic = tk.Frame(nb, bg="white")
        nb.add(basic, text="  기본 정보  ")
        self._build_basic(basic)

        # ── 일정 탭
        sched = tk.Frame(nb, bg="white")
        nb.add(sched, text="  일정 · 알림  ")
        self._build_sched(sched)

    def _row(self, parent, label, row, widget_fn, col_span=1):
        tk.Label(parent, text=label, bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=10).grid(
            row=row, column=0, padx=(12, 6), pady=5, sticky="e")
        w = widget_fn(parent)
        w.grid(row=row, column=1, columnspan=col_span, padx=(0, 12), pady=5, sticky="ew")
        return w

    def _build_basic(self, frm):
        # PanedWindow으로 상단 필드 영역 / 하단 설명 영역 분리 → 드래그로 높이 조절
        paned = ttk.PanedWindow(frm, orient="vertical")
        paned.pack(fill="both", expand=True)

        # ── 상단: 입력 필드
        fields_frm = tk.Frame(paned, bg="white")
        paned.add(fields_frm, weight=0)
        fields_frm.columnconfigure(1, weight=1)

        self.v_title    = tk.StringVar()
        self.v_project  = tk.StringVar()
        self.v_system   = tk.StringVar()
        self.v_assignee = tk.StringVar()
        self.v_type     = tk.StringVar(value="구현")
        self.v_priority = tk.StringVar(value="보통")
        self.v_status   = tk.StringVar(value="대기")
        self.v_tags     = tk.StringVar()

        self._row(fields_frm, "작업명 *", 0, lambda p: ttk.Entry(p, textvariable=self.v_title, font=FONT))
        self._row(fields_frm, "과제명",   1, lambda p: ttk.Entry(p, textvariable=self.v_project, font=FONT))
        self._row(fields_frm, "시스템명", 2, lambda p: ttk.Entry(p, textvariable=self.v_system, font=FONT))
        self._row(fields_frm, "담당자",   3, lambda p: ttk.Entry(p, textvariable=self.v_assignee, font=FONT))
        self._row(fields_frm, "작업 종류", 4, lambda p: ttk.Combobox(p, textvariable=self.v_type,
                                                              values=TASK_TYPES, state="readonly", font=FONT))
        self._row(fields_frm, "우선순위", 5, lambda p: ttk.Combobox(p, textvariable=self.v_priority,
                                                             values=PRIORITIES, state="readonly", font=FONT))
        self._row(fields_frm, "상태",     6, lambda p: ttk.Combobox(p, textvariable=self.v_status,
                                                             values=STATUSES, state="readonly", font=FONT))
        self._row(fields_frm, "태그",     7, lambda p: ttk.Entry(p, textvariable=self.v_tags, font=FONT))
        tk.Label(fields_frm, text="(쉼표로 구분)", bg="white", fg="#94A3B8", font=("맑은 고딕", 8)).grid(
            row=7, column=2, sticky="w")

        # ── To-Do 섹션
        tk.Label(fields_frm, text="To-Do", bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=10).grid(
            row=8, column=0, padx=(12, 6), pady=(8, 2), sticky="ne")

        todo_outer = tk.Frame(fields_frm, bg="white")
        todo_outer.grid(row=8, column=1, columnspan=2, padx=(0, 12), pady=(8, 4), sticky="ew")
        todo_outer.columnconfigure(0, weight=1)

        # 입력 행
        add_frm = tk.Frame(todo_outer, bg="white")
        add_frm.pack(fill="x")
        self._todo_entry = ttk.Entry(add_frm, font=FONT)
        self._todo_entry.pack(side="left", fill="x", expand=True)
        self._todo_entry.bind("<Return>", lambda e: self._todo_add())
        ttk.Button(add_frm, text="+ 추가", command=self._todo_add, width=6).pack(side="left", padx=(4, 0))

        # 목록 영역 — 고정 높이 스크롤 캔버스
        # (PanedWindow sash가 고정되어 단순 Frame pack 시 새 행이 숨는 문제 방지)
        list_container = tk.Frame(todo_outer, bg="#F8FAFC", relief="solid", bd=1)
        list_container.pack(fill="x", pady=(4, 0))

        self._todo_canvas = tk.Canvas(list_container, bg="#F8FAFC",
                                      highlightthickness=0, height=0)
        self._todo_sb = ttk.Scrollbar(list_container, orient="vertical",
                                      command=self._todo_canvas.yview)
        self._todo_canvas.configure(yscrollcommand=self._todo_sb.set)

        self._todo_list = tk.Frame(self._todo_canvas, bg="#F8FAFC")
        _todo_wid = self._todo_canvas.create_window(
            (0, 0), window=self._todo_list, anchor="nw")

        def _on_todo_inner_conf(e):
            self._todo_canvas.configure(scrollregion=self._todo_canvas.bbox("all"))
            row_h = 28
            h = min(row_h * 4, max(row_h, len(self._todo_items) * row_h))
            self._todo_canvas.configure(height=h)
            if len(self._todo_items) > 4:
                self._todo_sb.pack(side="right", fill="y")
            else:
                self._todo_sb.pack_forget()

        self._todo_list.bind("<Configure>", _on_todo_inner_conf)
        self._todo_canvas.bind("<Configure>",
                               lambda e: self._todo_canvas.itemconfig(_todo_wid, width=e.width))
        self._todo_canvas.pack(side="left", fill="x", expand=True)

        self._todo_items = []  # [{"text": str, "done_var": BoolVar, "frame": Frame}]

        # ── 하단: 설명 (드래그로 높이·너비 조절 가능)
        desc_frm = tk.Frame(paned, bg="white")
        paned.add(desc_frm, weight=1)
        desc_frm.rowconfigure(1, weight=1)
        desc_frm.columnconfigure(0, weight=1)

        tk.Label(desc_frm, text="설명", bg="white", font=FONT_S, fg="#374151",
                 anchor="w").grid(row=0, column=0, columnspan=2, padx=12, pady=(6, 2), sticky="w")

        self.txt_desc = tk.Text(desc_frm, font=FONT, relief="solid", bd=1, wrap="word")
        sb_desc = ttk.Scrollbar(desc_frm, orient="vertical", command=self.txt_desc.yview)
        self.txt_desc.configure(yscrollcommand=sb_desc.set)
        self.txt_desc.grid(row=1, column=0, padx=(12, 0), pady=(0, 6), sticky="nsew")
        sb_desc.grid(row=1, column=1, padx=(0, 12), pady=(0, 6), sticky="ns")

    def _build_sched(self, frm):
        frm.columnconfigure(1, weight=1)

        self.v_scheduled = tk.StringVar()
        self.v_deadline  = tk.StringVar()
        self.v_effort    = tk.StringVar()
        self.v_notify    = tk.StringVar(value="30")

        def _dt_row(parent, label, row, var, default_hour=9):
            tk.Label(parent, text=label, bg="white", font=FONT_S,
                     fg="#374151", anchor="e", width=10).grid(
                row=row, column=0, padx=(12, 6), pady=8, sticky="e")
            cell = tk.Frame(parent, bg="white")
            cell.grid(row=row, column=1, padx=(0, 12), pady=8, sticky="ew")
            cell.columnconfigure(0, weight=1)
            lbl = tk.Label(cell, textvariable=var, bg="#F8FAFC", relief="solid",
                           bd=1, font=FONT, anchor="w", padx=6, cursor="hand2")
            lbl.grid(row=0, column=0, sticky="ew")
            lbl.bind("<Button-1>", lambda e, v=var, dh=default_hour: self._pick_dt(v, dh))
            btn = ttk.Button(cell, text="📅", width=3,
                             command=lambda v=var, dh=default_hour: self._pick_dt(v, dh))
            btn.grid(row=0, column=1, padx=(4, 0))

        _dt_row(frm, "예정 일시", 0, self.v_scheduled, default_hour=9)
        _dt_row(frm, "마감 일시", 1, self.v_deadline, default_hour=18)

        tk.Label(frm, text="공수", bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=10).grid(
            row=2, column=0, padx=(12, 6), pady=8, sticky="e")
        effort_cell = tk.Frame(frm, bg="white")
        effort_cell.grid(row=2, column=1, padx=(0, 12), pady=8, sticky="w")
        ttk.Entry(effort_cell, textvariable=self.v_effort, width=12, font=FONT).pack(side="left")
        tk.Label(effort_cell, text="예) 1d 4h  /  3h 30m  /  2d",
                 bg="white", fg="#94A3B8", font=("맑은 고딕", 8)).pack(side="left", padx=(8, 0))

        tk.Label(frm, text="알림 (분)", bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=10).grid(
            row=3, column=0, padx=(12, 6), pady=8, sticky="e")
        ttk.Entry(frm, textvariable=self.v_notify, width=8, font=FONT).grid(
            row=3, column=1, padx=(0, 12), pady=8, sticky="w")

        tk.Label(frm, text="마감 N분 전에 알림 팝업을 표시합니다.",
                 bg="white", fg="#94A3B8", font=("맑은 고딕", 8)).grid(
            row=4, column=1, padx=(0, 12), sticky="w")

    def _pick_dt(self, var, default_hour=9):
        result = pick_datetime(self, var.get(), default_hour=default_hour)
        if result is not None:   # None = 취소, '' = 지우기
            var.set(result)

    def _todo_add(self):
        text = self._todo_entry.get().strip()
        if not text:
            return
        self._todo_entry.delete(0, "end")
        self._add_todo_row(text, done=False)

    def _add_todo_row(self, text, done=False):
        done_var = tk.BooleanVar(value=done)
        item = {"text": text, "done_var": done_var, "frame": None}

        row_frm = tk.Frame(self._todo_list, bg="white")
        row_frm.pack(fill="x", pady=1)
        item["frame"] = row_frm

        cb = tk.Checkbutton(row_frm, variable=done_var, bg="white",
                            activebackground="white",
                            command=lambda i=item: self._todo_toggle(i))
        cb.pack(side="left", padx=(2, 0))

        lbl = tk.Label(row_frm, text=text, bg="white", font=FONT,
                       fg="#374151", anchor="w", cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True, padx=(2, 4))
        lbl.bind("<Button-1>", lambda e, v=done_var, i=item: (v.set(not v.get()), self._todo_toggle(i)))

        def _remove(i=item):
            i["frame"].destroy()
            self._todo_items.remove(i)

        tk.Button(row_frm, text="✕", font=("맑은 고딕", 8), relief="flat",
                  bg="white", fg="#94A3B8", activeforeground="#EF4444",
                  cursor="hand2", bd=0, command=_remove).pack(side="right", padx=(0, 4))

        self._todo_items.append(item)

    def _todo_toggle(self, item):
        """완료 항목 텍스트 색상 갱신"""
        for w in item["frame"].winfo_children():
            if isinstance(w, tk.Label) and w.cget("cursor") == "hand2":
                done = item["done_var"].get()
                w.configure(fg="#9CA3AF" if done else "#374151",
                            font=(FONT[0], FONT[1], "overstrike") if done else FONT)

    def _fill(self, t):
        self.v_title.set(t["title"])
        self.v_project.set(t.get("project", ""))
        self.v_system.set(t.get("system", ""))
        self.v_assignee.set(t.get("assignee", ""))
        self.v_type.set(t.get("type", "구현"))
        self.v_priority.set(t.get("priority", "보통"))
        self.v_status.set(t.get("status", "대기"))
        self.v_tags.set(", ".join(t.get("tags", [])))
        self.txt_desc.insert("1.0", t.get("description", ""))
        self.v_scheduled.set(t.get("scheduled_at", ""))
        self.v_deadline.set(t.get("deadline", ""))
        self.v_effort.set(t.get("effort", ""))
        self.v_notify.set(str(t.get("notify_before_min", 30)))
        for td in t.get("todos", []):
            self._add_todo_row(td["text"], done=td.get("done", False))

    def _save(self):
        title = self.v_title.get().strip()
        if not title:
            messagebox.showwarning("입력 오류", "작업명을 입력하세요.", parent=self)
            return

        tags = [t.strip() for t in self.v_tags.get().split(",") if t.strip()]
        try:
            nbm = int(self.v_notify.get())
        except ValueError:
            nbm = 30

        new_vals = dict(
            title=title,
            project=self.v_project.get().strip(),
            system=self.v_system.get().strip(),
            assignee=self.v_assignee.get().strip(),
            type=self.v_type.get(),
            priority=self.v_priority.get(),
            status=self.v_status.get(),
            tags=tags,
            description=self.txt_desc.get("1.0", "end").strip(),
            scheduled_at=self.v_scheduled.get().strip(),
            deadline=self.v_deadline.get().strip(),
            effort=self.v_effort.get().strip(),
            notify_before_min=nbm,
            todos=[{"text": it["text"], "done": bool(it["done_var"].get())}
                   for it in self._todo_items],
        )

        # 이력 추적 대상 필드 (변경 시 코멘트 요청)
        TRACKED = [
            ("예정일시", "scheduled_at"),
            ("마감일시", "deadline"),
            ("공수",     "effort"),
        ]
        if self.task is not None:
            changes = [
                {"field": label, "old": self.task.get(key, ""), "new": new_vals[key]}
                for label, key in TRACKED
                if self.task.get(key, "") != new_vals[key]
            ]
        else:
            changes = []

        if changes:
            # 코멘트 팝업 → 확인 후 _do_save 호출
            ChangeCommentDialog(self, changes, lambda comment: self._do_save(new_vals, changes, comment))
        else:
            self._do_save(new_vals, [], "")

    def _do_save(self, new_vals, changes, comment):
        data = load_data()
        now  = now_str()

        if self.task is None:
            t = make_task(data, **new_vals)
            data["tasks"].append(t)
        else:
            for task in data["tasks"]:
                if task["id"] == self.task["id"]:
                    task.update(**new_vals, updated_at=now)
                    if changes:
                        task.setdefault("change_history", []).append({
                            "ts": now,
                            "changes": changes,
                            "comment": comment,
                        })
                    break

        save_data(data)
        if self.on_save:
            self.on_save()
        self.destroy()


# ---------------------------------------------------------------------------
# 상세 패널 (오른쪽)
# ---------------------------------------------------------------------------

class TaskDetailPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#F8FAFC")
        self.app = app
        self._task_id = None
        self._build()

    def _build(self):
        # 빈 상태 안내
        self._empty_label = tk.Label(self, text="작업을 선택하세요",
                                      bg="#F8FAFC", fg="#94A3B8", font=FONT_H)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")

        # 실제 상세 영역 (task 선택 시 표시)
        self._detail_frame = tk.Frame(self, bg="#F8FAFC")

        # 기본 정보 영역
        self._info_frame = tk.Frame(self._detail_frame, bg="white",
                                     relief="flat", bd=0)
        self._info_frame.pack(fill="x", padx=10, pady=(10, 4))

        # 탭
        self._nb = ttk.Notebook(self._detail_frame)
        self._nb.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._memo_tab    = tk.Frame(self._nb, bg="white")
        self._link_tab    = tk.Frame(self._nb, bg="white")
        self._result_tab  = tk.Frame(self._nb, bg="white")
        self._history_tab = tk.Frame(self._nb, bg="white")
        self._nb.add(self._memo_tab,    text="  메모  ")
        self._nb.add(self._link_tab,    text="  연결 작업  ")
        self._nb.add(self._result_tab,  text="  최종 결과  ")
        self._nb.add(self._history_tab, text="  변경 이력  ")

        self._build_memo_tab()
        self._build_link_tab()
        self._build_result_tab()
        self._build_history_tab()

    # ── 정보 요약
    def _refresh_info(self, task):
        for w in self._info_frame.winfo_children():
            w.destroy()

        bg = PRIORITY_COLOR.get(task["priority"], "white")
        self._info_frame.configure(bg=bg)

        title_row = tk.Frame(self._info_frame, bg=bg)
        title_row.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(title_row, text=task["title"], bg=bg,
                 font=("맑은 고딕", 12, "bold"), fg="#1E293B",
                 anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(title_row, text=f"[{task['priority']}]  {task['status']}",
                 bg=bg, font=FONT_S, fg="#475569").pack(side="right")

        row2 = tk.Frame(self._info_frame, bg=bg)
        row2.pack(fill="x", padx=10, pady=(0, 4))
        project = task.get("project", "")
        info_text = (f"{('과제: ' + project + '  |  ') if project else ''}"
                     f"{task.get('system','—')}  |  {task.get('type','—')}  "
                     f"|  담당: {task.get('assignee','—')}")
        tk.Label(row2, text=info_text, bg=bg, font=FONT_S, fg="#475569",
                 anchor="w").pack(side="left")

        sched  = fmt_dt(task.get("scheduled_at"))
        dl     = fmt_dt(task.get("deadline"))
        dday   = calc_dday(task.get("deadline"))
        effort = task.get("effort", "")
        time_text = (f"예정: {sched or '—'}  |  마감: {dl or '—'}  {dday}"
                     + (f"  |  공수: {effort}" if effort else ""))
        tk.Label(row2, text=time_text, bg=bg, font=FONT_S, fg="#64748B").pack(side="right")

        if task.get("description"):
            tk.Label(self._info_frame, text=task["description"],
                     bg=bg, font=FONT_S, fg="#374151", anchor="w",
                     wraplength=350, justify="left").pack(
                fill="x", padx=10, pady=(0, 6))

        if task.get("tags"):
            tags_text = "  ".join(f"#{t}" for t in task["tags"])
            tk.Label(self._info_frame, text=tags_text, bg=bg,
                     font=("맑은 고딕", 8), fg="#3B82F6").pack(anchor="w", padx=10, pady=(0, 6))

        # 편집 버튼
        tk.Button(self._info_frame, text="✏ 수정",
                  bg=bg, relief="flat", font=FONT_S, cursor="hand2",
                  command=lambda: self.app.edit_task(self._task_id)).pack(
            anchor="e", padx=10, pady=(0, 6))

    # ── 메모 탭
    def _build_memo_tab(self):
        toolbar = tk.Frame(self._memo_tab, bg="white")
        toolbar.pack(fill="x", padx=8, pady=6)
        tk.Button(toolbar, text="+ 메모 추가", font=FONT_S,
                  bg="#2563EB", fg="white", relief="flat", cursor="hand2",
                  command=self._add_memo).pack(side="left")

        # 스크롤 가능한 메모 카드 목록
        outer = tk.Frame(self._memo_tab, bg="#F8FAFC")
        outer.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self._memo_canvas = tk.Canvas(outer, bg="#F8FAFC", highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=self._memo_canvas.yview)
        self._memo_canvas.configure(yscrollcommand=sb.set)
        self._memo_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._memo_inner = tk.Frame(self._memo_canvas, bg="#F8FAFC")
        self._memo_win   = self._memo_canvas.create_window(
            (0, 0), window=self._memo_inner, anchor="nw")

        self._memo_inner.bind("<Configure>",
            lambda e: self._memo_canvas.configure(
                scrollregion=self._memo_canvas.bbox("all")))
        self._memo_canvas.bind("<Configure>",
            lambda e: self._memo_canvas.itemconfig(self._memo_win, width=e.width))

    def _refresh_memos(self, task):
        for w in self._memo_inner.winfo_children():
            w.destroy()

        memos = list(reversed(task.get("memos", [])))
        if not memos:
            tk.Label(self._memo_inner, text="메모가 없습니다.",
                     bg="#F8FAFC", fg="#94A3B8", font=FONT_S).pack(pady=20)
            return

        for memo in memos:
            self._make_memo_card(memo)

    def _make_memo_card(self, memo):
        mid = memo["id"]
        card = tk.Frame(self._memo_inner, bg="white", relief="solid", bd=1)
        card.pack(fill="x", pady=3, padx=2)

        # 헤더: 타임스탬프 + 버튼
        hdr = tk.Frame(card, bg="#F1F5F9")
        hdr.pack(fill="x")
        tk.Label(hdr, text=fmt_dt(memo.get("ts", "")),
                 bg="#F1F5F9", fg="#64748B", font=("맑은 고딕", 8)).pack(
            side="left", padx=8, pady=2)
        tk.Button(hdr, text="✏", bg="#F1F5F9", relief="flat", font=("맑은 고딕", 8),
                  cursor="hand2", fg="#2563EB",
                  command=lambda m=memo: self._edit_memo(m)).pack(side="right", padx=2)
        tk.Button(hdr, text="🗑", bg="#F1F5F9", relief="flat", font=("맑은 고딕", 8),
                  cursor="hand2", fg="#EF4444",
                  command=lambda m_id=mid: self._delete_memo(m_id)).pack(side="right")

        # 내용
        tk.Label(card, text=memo["content"], bg="white", font=FONT_S,
                 fg="#1E293B", anchor="w", justify="left",
                 wraplength=320).pack(fill="x", padx=8, pady=6)

    def _add_memo(self):
        if self._task_id is None:
            return
        def save_memo(content):
            data = load_data()
            task = get_task(data, self._task_id)
            if task is None:
                return
            mid = data.get("next_memo_id", 1)
            data["next_memo_id"] = mid + 1
            task["memos"].append({"id": mid, "ts": now_str(), "content": content})
            task["updated_at"] = now_str()
            save_data(data)
            self.app.refresh_list()
            self.load_task(self._task_id)
        MemoAddDialog(self, save_memo)

    def _edit_memo(self, memo):
        if self._task_id is None:
            return
        def save_edit(content):
            data = load_data()
            task = get_task(data, self._task_id)
            if task is None:
                return
            for m in task["memos"]:
                if m["id"] == memo["id"]:
                    m["content"] = content
                    m["ts"]      = now_str()
                    break
            task["updated_at"] = now_str()
            save_data(data)
            self.load_task(self._task_id)
        dlg = MemoAddDialog(self, save_edit)
        dlg.txt.insert("1.0", memo["content"])

    def _delete_memo(self, memo_id):
        if not messagebox.askyesno("삭제 확인", "메모를 삭제하시겠습니까?", parent=self):
            return
        data = load_data()
        task = get_task(data, self._task_id)
        if task:
            task["memos"]     = [m for m in task["memos"] if m["id"] != memo_id]
            task["updated_at"] = now_str()
            save_data(data)
            self.load_task(self._task_id)

    # ── 연결 탭
    def _build_link_tab(self):
        toolbar = tk.Frame(self._link_tab, bg="white")
        toolbar.pack(fill="x", padx=8, pady=6)
        tk.Button(toolbar, text="+ 서브작업 연결", font=FONT_S,
                  bg="#059669", fg="white", relief="flat", cursor="hand2",
                  command=lambda: self._link_dialog("sub")).pack(side="left", padx=(0, 4))
        tk.Button(toolbar, text="+ 연계작업 연결", font=FONT_S,
                  bg="#7C3AED", fg="white", relief="flat", cursor="hand2",
                  command=lambda: self._link_dialog("linked")).pack(side="left")

        frm = tk.Frame(self._link_tab, bg="white")
        frm.pack(fill="both", expand=True, padx=8)
        sb = ttk.Scrollbar(frm)
        self._link_text = tk.Text(frm, font=FONT_S, state="disabled",
                                   relief="flat", bd=0, bg="#F8FAFC",
                                   yscrollcommand=sb.set, wrap="word")
        sb.config(command=self._link_text.yview)
        self._link_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _refresh_links(self, task, all_tasks):
        self._link_text.config(state="normal")
        self._link_text.delete("1.0", "end")
        task_map = {t["id"]: t for t in all_tasks}

        parent_id = task.get("parent_id")
        if parent_id and parent_id in task_map:
            pt = task_map[parent_id]
            self._link_text.insert("end", f"▲ 부모 작업\n  [{pt['id']}] {pt['title']} ({pt['status']})\n\n")

        if task.get("sub_ids"):
            self._link_text.insert("end", "▼ 서브 작업\n")
            for sid in task["sub_ids"]:
                if sid in task_map:
                    st = task_map[sid]
                    self._link_text.insert("end", f"  [{st['id']}] {st['title']} ({st['status']})\n")
            self._link_text.insert("end", "\n")

        if task.get("linked_ids"):
            self._link_text.insert("end", "↔ 연계 작업\n")
            for lid in task["linked_ids"]:
                if lid in task_map:
                    lt = task_map[lid]
                    self._link_text.insert("end", f"  [{lt['id']}] {lt['title']} ({lt['status']})\n")

        self._link_text.config(state="disabled")

    def _link_dialog(self, link_type):
        if self._task_id is None:
            return
        data = load_data()
        task = get_task(data, self._task_id)
        if task is None:
            return
        exclude = {self._task_id} | set(task.get("sub_ids", [])) | set(task.get("linked_ids", []))
        if task.get("parent_id"):
            exclude.add(task["parent_id"])

        def on_select(selected_id):
            data2 = load_data()
            t = get_task(data2, self._task_id)
            sel = get_task(data2, selected_id)
            if t is None or sel is None:
                return
            if link_type == "sub":
                if selected_id not in t["sub_ids"]:
                    t["sub_ids"].append(selected_id)
                sel["parent_id"] = self._task_id
            else:
                if selected_id not in t["linked_ids"]:
                    t["linked_ids"].append(selected_id)
                if self._task_id not in sel.get("linked_ids", []):
                    sel.setdefault("linked_ids", []).append(self._task_id)
            save_data(data2)
            self.app.refresh_list()
            self.load_task(self._task_id)

        LinkSelectorDialog(self, data["tasks"], exclude, on_select)

    # ── 결과 탭
    def _build_result_tab(self):
        frm = tk.Frame(self._result_tab, bg="white")
        frm.pack(fill="both", expand=True, padx=12, pady=8)
        frm.columnconfigure(1, weight=1)

        tk.Label(frm, text="실 투입공수", bg="white", font=FONT_S,
                 fg="#374151").grid(row=0, column=0, sticky="w", pady=(0, 4))
        effort_cell = tk.Frame(frm, bg="white")
        effort_cell.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 8))
        self._v_actual_effort = tk.StringVar()
        ttk.Entry(effort_cell, textvariable=self._v_actual_effort,
                  width=14, font=FONT).pack(side="left")
        tk.Label(effort_cell, text="예) 1d 4h  /  3h 30m",
                 bg="white", fg="#94A3B8", font=("맑은 고딕", 8)).pack(side="left", padx=8)

        tk.Label(frm, text="결과 요약", bg="white", font=FONT_S,
                 fg="#374151").grid(row=1, column=0, sticky="nw", pady=(0, 4))
        self._result_summary = tk.Text(frm, height=3, font=FONT, relief="solid", bd=1)
        self._result_summary.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))

        tk.Label(frm, text="점수 (1~5)", bg="white", font=FONT_S,
                 fg="#374151").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self._score_var = tk.IntVar(value=0)
        score_row = tk.Frame(frm, bg="white")
        score_row.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(0, 8))
        STARS = ["—", "★", "★★", "★★★", "★★★★", "★★★★★"]
        self._score_btns = []
        for v in range(1, 6):
            btn = tk.Button(score_row, text=f"{v}점\n{STARS[v]}",
                            font=("맑은 고딕", 9), relief="flat", bd=1,
                            bg="#F1F5F9", fg="#374151", width=6, height=2,
                            cursor="hand2",
                            command=lambda val=v: self._select_score(val))
            btn.pack(side="left", padx=2)
            self._score_btns.append(btn)

        tk.Label(frm, text="피드백", bg="white", font=FONT_S,
                 fg="#374151").grid(row=3, column=0, sticky="nw", pady=(0, 4))
        self._result_feedback = tk.Text(frm, height=4, font=FONT, relief="solid", bd=1)
        self._result_feedback.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))

        tk.Button(frm, text="결과 저장", bg="#2563EB", fg="white",
                  font=FONT_S, relief="flat", cursor="hand2",
                  command=self._save_result).grid(row=4, column=1, sticky="e", padx=(8, 0))

    def _select_score(self, val):
        self._score_var.set(val)
        for i, btn in enumerate(self._score_btns, 1):
            if i == val:
                btn.config(bg="#2563EB", fg="white")
            else:
                btn.config(bg="#F1F5F9", fg="#374151")

    def _refresh_result(self, task):
        self._v_actual_effort.set(task.get("actual_effort", ""))
        res = task.get("result", {})
        self._result_summary.delete("1.0", "end")
        self._result_summary.insert("1.0", res.get("summary", ""))
        score = res.get("score") or 0
        # 구버전 0~100 값 변환
        if score > 5:
            score = round(score / 20)
        self._score_var.set(int(score))
        self._select_score(int(score)) if score else self._reset_score_btns()
        self._result_feedback.delete("1.0", "end")
        self._result_feedback.insert("1.0", res.get("feedback", ""))

    def _reset_score_btns(self):
        for btn in self._score_btns:
            btn.config(bg="#F1F5F9", fg="#374151")

    def _save_result(self):
        if self._task_id is None:
            return
        data = load_data()
        task = get_task(data, self._task_id)
        if task is None:
            return
        task["actual_effort"] = self._v_actual_effort.get().strip()
        task["result"] = {
            "summary": self._result_summary.get("1.0", "end").strip(),
            "score": int(self._score_var.get()),   # 1~5
            "feedback": self._result_feedback.get("1.0", "end").strip(),
        }
        task["updated_at"] = now_str()
        save_data(data)
        self.app.refresh_list()
        messagebox.showinfo("저장 완료", "결과가 저장됐습니다.", parent=self)

    # ── 이력 탭
    def _build_history_tab(self):
        outer = tk.Frame(self._history_tab, bg="#F8FAFC")
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        self._hist_canvas = tk.Canvas(outer, bg="#F8FAFC", highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=self._hist_canvas.yview)
        self._hist_canvas.configure(yscrollcommand=sb.set)
        self._hist_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._hist_inner = tk.Frame(self._hist_canvas, bg="#F8FAFC")
        self._hist_win   = self._hist_canvas.create_window(
            (0, 0), window=self._hist_inner, anchor="nw")

        self._hist_inner.bind("<Configure>",
            lambda e: self._hist_canvas.configure(
                scrollregion=self._hist_canvas.bbox("all")))
        self._hist_canvas.bind("<Configure>",
            lambda e: self._hist_canvas.itemconfig(self._hist_win, width=e.width))
        self._hist_canvas.bind("<MouseWheel>",
            lambda e: self._hist_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    def _refresh_history(self, task):
        for w in self._hist_inner.winfo_children():
            w.destroy()

        history = task.get("change_history", [])
        if not history:
            tk.Label(self._hist_inner, text="변경 이력이 없습니다.",
                     bg="#F8FAFC", fg="#94A3B8", font=FONT_S).pack(pady=20)
            return

        for entry in reversed(history):
            self._make_history_card(entry)

    def _make_history_card(self, entry):
        ts_str = entry.get("ts", "")
        card = tk.Frame(self._hist_inner, bg="white", relief="solid", bd=1)
        card.pack(fill="x", pady=3, padx=2)

        # 헤더: 타임스탬프 + 삭제 버튼
        hdr = tk.Frame(card, bg="#F1F5F9")
        hdr.pack(fill="x")
        tk.Label(hdr, text=fmt_dt(ts_str),
                 bg="#F1F5F9", fg="#64748B", font=("맑은 고딕", 8)).pack(
            side="left", padx=8, pady=2)
        tk.Button(hdr, text="🗑", bg="#F1F5F9", relief="flat",
                  font=("맑은 고딕", 8), cursor="hand2", fg="#EF4444",
                  command=lambda ts=ts_str: self._delete_history_entry(ts)
                  ).pack(side="right", padx=2)

        # 변경 내용
        body = tk.Frame(card, bg="white")
        body.pack(fill="x", padx=8, pady=(4, 2))
        for c in entry.get("changes", []):
            old = fmt_dt(c["old"]) if "T" in str(c["old"]) else c["old"]
            new = fmt_dt(c["new"]) if "T" in str(c["new"]) else c["new"]
            row = tk.Frame(body, bg="white")
            row.pack(fill="x")
            tk.Label(row, text=f"{c['field']}: ",
                     bg="white", fg="#1E40AF", font=FONT_S).pack(side="left")
            tk.Label(row, text=f"{old or '(없음)'}  →  {new or '(없음)'}",
                     bg="white", fg="#374151", font=FONT_S,
                     wraplength=300, justify="left").pack(side="left")

        # 사유
        if entry.get("comment"):
            tk.Label(card, text=f"사유: {entry['comment']}",
                     bg="white", fg="#64748B", font=FONT_S,
                     anchor="w", wraplength=320, justify="left").pack(
                fill="x", padx=8, pady=(0, 6))
        else:
            tk.Frame(card, bg="white", height=4).pack()

    def _delete_history_entry(self, ts_str):
        if not messagebox.askyesno("삭제 확인", "이 변경 이력을 삭제하시겠습니까?",
                                   parent=self):
            return
        data = load_data()
        task = get_task(data, self._task_id)
        if task is None:
            return
        task["change_history"] = [
            e for e in task.get("change_history", [])
            if e.get("ts") != ts_str
        ]
        save_data(data)
        self.load_task(self._task_id)

    # ── 외부 진입점
    def load_task(self, task_id):
        self._task_id = task_id
        data = load_data()
        task = get_task(data, task_id)
        if task is None:
            self.clear()
            return

        self._empty_label.place_forget()
        self._detail_frame.pack(fill="both", expand=True)

        self._refresh_info(task)
        self._refresh_memos(task)
        self._refresh_links(task, data["tasks"])
        self._refresh_result(task)
        self._refresh_history(task)

    def clear(self):
        self._task_id = None
        self._detail_frame.pack_forget()
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")


# ---------------------------------------------------------------------------
# 목록 패널 (왼쪽) — 탭 구조: 미종료 / 종료 / 오늘
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 오늘 타임라인 뷰 (Canvas 기반)
# ---------------------------------------------------------------------------

class TodayTimelineView(tk.Frame):
    """00:00~24:00 타임라인. 작업 바 드래그로 시간/공수 직접 편집."""

    HDR_H       = 32    # 눈금자 높이
    ROW_H       = 46    # 작업 행 높이
    LMARGIN     = 120   # 왼쪽 라벨 영역 너비
    RMARGIN     = 14
    RESIZE_ZONE = 10    # 오른쪽 끝 리사이즈 핫스팟 너비
    MIN_DUR_MIN = 15    # 최소 지속 시간(분)

    PRIO_FILL   = {"긴급": "#FEE2E2", "높음": "#FEF9C3",
                   "보통": "#DBEAFE", "낮음": "#D1FAE5"}
    PRIO_BORDER = {"긴급": "#EF4444", "높음": "#F59E0B",
                   "보통": "#2563EB",  "낮음": "#059669"}

    def __init__(self, parent, app):
        super().__init__(parent, bg="#F8FAFC")
        self.app  = app
        self._all_tasks: list  = []   # load()에서 받은 원본
        self._tasks: list      = []   # 필터 적용 후 표시 목록
        self._task_rows: dict  = {}   # task_id → row index
        self._drag_state       = None
        self._selected_tid     = None  # 현재 선택된 task_id
        self._tooltip_win      = None  # 툴팁 Toplevel
        self._tooltip_after    = None  # 툴팁 지연 after ID
        self._last_hover_tid   = None  # 마지막 hover task_id
        self._v_assignee       = None  # 담당자 필터 StringVar
        self._build()

    # ── UI 구성 ─────────────────────────────────────────────────

    def _build(self):
        # ── 필터 바 ──────────────────────────────────────────────
        fbar = tk.Frame(self, bg="#F1F5F9", pady=4)
        fbar.pack(fill="x")
        tk.Label(fbar, text="담당자", bg="#F1F5F9", fg="#374151",
                 font=FONT_S).pack(side="left", padx=(8, 4))
        self._v_assignee = tk.StringVar(value="전체")
        self._cb_assignee = ttk.Combobox(fbar, textvariable=self._v_assignee,
                                          values=["전체"], state="readonly",
                                          width=10, font=FONT_S)
        self._cb_assignee.pack(side="left", padx=(0, 10))
        self._v_assignee.trace_add("write", lambda *_: self._apply_filter())

        self._now_lbl = tk.Label(fbar, text="", bg="#F1F5F9", fg="#EF4444", font=FONT_S)
        self._now_lbl.pack(side="right", padx=8)
        tk.Label(fbar,
                 text="드래그: 이동  |  양 끝: 공수 조정(30분)  |  더블클릭: 수정  |  우클릭: 메뉴",
                 bg="#F1F5F9", fg="#64748B", font=FONT_S).pack(side="right", padx=8)

        # ── 캔버스 ───────────────────────────────────────────────
        frm = tk.Frame(self, bg="white")
        frm.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(frm, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)

        self._canvas.bind("<Configure>",       lambda e: self.after(20, self._redraw))
        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",       self._on_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Double-Button-1>", self._on_double)
        self._canvas.bind("<Button-3>",        self._on_right_click)
        self._canvas.bind("<Motion>",          self._on_hover)
        self._canvas.bind("<Leave>",           self._on_leave)
        self._canvas.bind("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self._tick_now()

    def _tick_now(self):
        now = datetime.now()
        self._now_lbl.config(text=f"현재 {now.strftime('%H:%M')}")
        self._draw_now_line()
        self.after(60000, self._tick_now)

    # ── Public ──────────────────────────────────────────────────

    def load(self, tasks):
        self._all_tasks = [t for t in tasks if self._has_time(t)]
        # 담당자 목록 갱신
        assignees = sorted({t.get("assignee", "").strip()
                            for t in self._all_tasks
                            if t.get("assignee", "").strip()})
        vals = ["전체"] + assignees
        self._cb_assignee["values"] = vals
        if self._v_assignee.get() not in vals:
            self._v_assignee.set("전체")
        self._apply_filter()

    def _apply_filter(self):
        sel = self._v_assignee.get()
        if sel == "전체":
            self._tasks = list(self._all_tasks)
        else:
            self._tasks = [t for t in self._all_tasks
                           if t.get("assignee", "").strip() == sel]
        self._tasks.sort(key=lambda t: self._start_min(t))
        self._task_rows = {t["id"]: i for i, t in enumerate(self._tasks)}
        self._redraw()

    # ── 시간 계산 ────────────────────────────────────────────────

    def _has_time(self, t):
        return bool(t.get("scheduled_at") or t.get("deadline"))

    def _start_min(self, t) -> float:
        sch = t.get("scheduled_at", "")
        if sch:
            try:
                dt = datetime.fromisoformat(sch)
                if dt.date() < date.today():
                    return 0.0
                return float(dt.hour * 60 + dt.minute)
            except Exception:
                pass
        dl = t.get("deadline", "")
        if dl:
            try:
                dt  = datetime.fromisoformat(dl)
                eff = parse_effort_min(t.get("effort", "")) or 60
                return max(0.0, float(dt.hour * 60 + dt.minute) - eff)
            except Exception:
                pass
        return 0.0

    def _end_min(self, t) -> float:
        dl = t.get("deadline", "")
        if dl:
            try:
                dt = datetime.fromisoformat(dl)
                if dt.date() > date.today():
                    return 1440.0
                return float(dt.hour * 60 + dt.minute)
            except Exception:
                pass
        sch = t.get("scheduled_at", "")
        if sch:
            try:
                dt  = datetime.fromisoformat(sch)
                eff = parse_effort_min(t.get("effort", "")) or 60
                return min(1440.0, float(dt.hour * 60 + dt.minute) + eff)
            except Exception:
                pass
        return min(1440.0, self._start_min(t) + 60.0)

    # ── 좌표 변환 ────────────────────────────────────────────────

    def _cw(self) -> int:
        return max(200, self._canvas.winfo_width())

    def _tw(self) -> float:
        return float(self._cw() - self.LMARGIN - self.RMARGIN)

    def _min_to_x(self, m: float) -> float:
        return self.LMARGIN + m / 1440.0 * self._tw()

    def _x_to_min(self, x: float) -> float:
        return max(0.0, min(1440.0, (x - self.LMARGIN) / self._tw() * 1440.0))

    @staticmethod
    def _snap30(m: float) -> float:
        """30분 단위 스냅."""
        return round(m / 30.0) * 30.0

    # ── 그리기 ───────────────────────────────────────────────────

    def _total_h(self) -> int:
        return self.HDR_H + max(len(self._tasks), 3) * self.ROW_H + 20

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        c.configure(scrollregion=(0, 0, self._cw(), self._total_h()))
        self._draw_bg()
        self._draw_ruler()
        for i, t in enumerate(self._tasks):
            self._draw_bar(i, t)
        self._draw_now_line()

    def _draw_bg(self):
        c   = self._canvas
        cw  = self._cw()
        th  = self._total_h()
        n   = max(len(self._tasks), 3)
        for i in range(n):
            y    = self.HDR_H + i * self.ROW_H
            fill = "white" if i % 2 == 0 else "#F8FAFC"
            c.create_rectangle(0, y, cw, y + self.ROW_H, fill=fill, outline="", tags="bg")
        for h in range(25):
            x = self._min_to_x(h * 60)
            if h % 6 == 0:
                lc, ld, lw = "#94A3B8", (), 1
            elif h % 3 == 0:
                lc, ld, lw = "#CBD5E1", (4, 4), 1
            else:
                lc, ld, lw = "#E2E8F0", (2, 4), 1
            c.create_line(x, self.HDR_H, x, th, fill=lc, dash=ld, width=lw, tags="bg")
        c.create_line(self.LMARGIN, 0, self.LMARGIN, th, fill="#CBD5E1", tags="bg")

    def _draw_ruler(self):
        c  = self._canvas
        cw = self._cw()
        c.create_rectangle(0, 0, cw, self.HDR_H,
                            fill="#F1F5F9", outline="", tags="ruler")
        c.create_rectangle(0, 0, self.LMARGIN, self.HDR_H,
                            fill="#E2E8F0", outline="", tags="ruler")
        c.create_text(self.LMARGIN // 2, self.HDR_H // 2,
                      text="작업", font=("맑은 고딕", 9, "bold"),
                      fill="#475569", tags="ruler")
        for h in range(25):
            x = self._min_to_x(h * 60)
            if h % 6 == 0:
                c.create_text(x, self.HDR_H // 2, text=f"{h:02d}:00",
                              font=("맑은 고딕", 9), fill="#374151", tags="ruler")
            elif h % 3 == 0:
                c.create_text(x, self.HDR_H // 2, text=f"{h:02d}",
                              font=("맑은 고딕", 8), fill="#94A3B8", tags="ruler")
        c.create_line(0, self.HDR_H, cw, self.HDR_H, fill="#CBD5E1", tags="ruler")

    def _draw_bar(self, row, task):
        c   = self._canvas
        tid = task["id"]
        sm  = self._start_min(task)
        em  = self._end_min(task)
        dur = max(float(self.MIN_DUR_MIN), em - sm)

        y0     = self.HDR_H + row * self.ROW_H
        bar_y1 = y0 + 5
        bar_y2 = y0 + self.ROW_H - 5
        y_mid  = y0 + self.ROW_H // 2
        x1     = self._min_to_x(sm)
        x2     = self._min_to_x(sm + dur)

        # 바 색상
        status = task.get("status", "대기")
        sicon  = {"진행중": "▶", "대기": "⏸", "완료": "✅", "취소": "✗"}.get(status, "")
        prio = task.get("priority", "보통")
        is_sel = (tid == self._selected_tid)
        if status in ("완료", "취소"):
            fill, border = "#E5E7EB", "#9CA3AF"
        else:
            fill   = self.PRIO_FILL.get(prio, "#DBEAFE")
            border = self.PRIO_BORDER.get(prio, "#2563EB")
            if status == "진행중":
                border = "#1D4ED8"

        outline_color = "#F59E0B" if is_sel else border
        outline_width = 3        if is_sel else 2
        handle_color  = "#F59E0B" if is_sel else border

        c.create_rectangle(x1, bar_y1, x2, bar_y2,
                           fill=fill, outline=outline_color, width=outline_width,
                           tags=(f"bar_{tid}", "bar"))

        # 왼쪽 라벨 (선택 시 amber 강조)
        lbl_fg   = "#92400E" if is_sel else "#1E293B"
        lbl_font = ("맑은 고딕", 9, "bold") if is_sel else ("맑은 고딕", 9)
        c.create_text(8, y_mid, text=f"{sicon} {task['title']}",
                      anchor="w", font=lbl_font, fill=lbl_fg,
                      width=self.LMARGIN - 16, tags=f"lbl_{tid}")

        # 바 라벨
        bar_w   = x2 - x1
        s_hhmm  = f"{int(sm)//60:02d}:{int(sm)%60:02d}"
        e_hhmm  = f"{int(sm+dur)//60:02d}:{int(sm+dur)%60:02d}"
        dur_str = format_effort_min(int(round(dur)))
        if bar_w >= 120:
            bt = f"{s_hhmm}~{e_hhmm}  ({dur_str})"
        elif bar_w >= 70:
            bt = f"{s_hhmm}  ({dur_str})"
        elif bar_w >= 36:
            bt = dur_str
        else:
            bt = ""
        if bt:
            fg_t = "#92400E" if is_sel else ("#1E40AF" if status not in ("완료", "취소") else "#6B7280")
            c.create_text((x1 + x2) / 2, (bar_y1 + bar_y2) / 2,
                          text=bt, font=("맑은 고딕", 8, "bold") if is_sel else ("맑은 고딕", 8),
                          fill=fg_t, width=max(1, int(bar_w) - 8),
                          tags=f"barlbl_{tid}")

        # 리사이즈 핸들 — 왼쪽 끝
        c.create_rectangle(x1, bar_y1 + 3,
                           x1 + self.RESIZE_ZONE, bar_y2 - 3,
                           fill=handle_color, outline="",
                           tags=(f"lrsz_{tid}", "lrsz"))
        # 리사이즈 핸들 — 오른쪽 끝
        c.create_rectangle(x2 - self.RESIZE_ZONE, bar_y1 + 3,
                           x2, bar_y2 - 3,
                           fill=handle_color, outline="",
                           tags=(f"rsz_{tid}", "rsz"))

    def _draw_now_line(self):
        c = self._canvas
        c.delete("nowline")
        now = datetime.now()
        if now.date() != date.today():
            return
        x  = self._min_to_x(now.hour * 60 + now.minute)
        th = self._total_h()
        c.create_line(x, 0, x, th, fill="#EF4444", width=2, dash=(5, 3), tags="nowline")
        c.create_oval(x - 4, self.HDR_H - 4, x + 4, self.HDR_H + 4,
                      fill="#EF4444", outline="", tags="nowline")

    # ── 히트 테스트 ──────────────────────────────────────────────

    def _hit_test(self, mx, my):
        """(task_id, 'move'|'resize_right'|'resize_left') 또는 (None, None)"""
        cx = self._canvas.canvasx(mx)
        cy = self._canvas.canvasy(my)
        for task in self._tasks:
            tid = task["id"]
            # 오른쪽 끝 핸들
            for item in self._canvas.find_withtag(f"rsz_{tid}"):
                x1, y1, x2, y2 = self._canvas.coords(item)
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    return tid, "resize_right"
            # 왼쪽 끝 핸들
            for item in self._canvas.find_withtag(f"lrsz_{tid}"):
                x1, y1, x2, y2 = self._canvas.coords(item)
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    return tid, "resize_left"
            # 바 본체
            for item in self._canvas.find_withtag(f"bar_{tid}"):
                x1, y1, x2, y2 = self._canvas.coords(item)
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    return tid, "move"
        return None, None

    # ── 바 위치 실시간 업데이트 (드래그 중) ─────────────────────

    def _update_bar_pos(self, task_id, sm, em):
        c     = self._canvas
        row   = self._task_rows.get(task_id, 0)
        y0    = self.HDR_H + row * self.ROW_H
        bar_y1 = y0 + 5
        bar_y2 = y0 + self.ROW_H - 5
        x1     = self._min_to_x(sm)
        x2     = self._min_to_x(em)

        for item in c.find_withtag(f"bar_{task_id}"):
            c.coords(item, x1, bar_y1, x2, bar_y2)
        for item in c.find_withtag(f"lrsz_{task_id}"):
            c.coords(item, x1, bar_y1 + 3, x1 + self.RESIZE_ZONE, bar_y2 - 3)
        for item in c.find_withtag(f"rsz_{task_id}"):
            c.coords(item, x2 - self.RESIZE_ZONE, bar_y1 + 3, x2, bar_y2 - 3)

        bar_w   = x2 - x1
        dur     = em - sm
        s_hhmm  = f"{int(sm)//60:02d}:{int(sm)%60:02d}"
        e_hhmm  = f"{int(em)//60:02d}:{int(em)%60:02d}"
        dur_str = format_effort_min(int(round(dur)))
        if bar_w >= 120:
            bt = f"{s_hhmm}~{e_hhmm}  ({dur_str})"
        elif bar_w >= 70:
            bt = f"{s_hhmm}  ({dur_str})"
        elif bar_w >= 36:
            bt = dur_str
        else:
            bt = ""
        for item in c.find_withtag(f"barlbl_{task_id}"):
            c.coords(item, (x1 + x2) / 2, (bar_y1 + bar_y2) / 2)
            c.itemconfig(item, text=bt, width=max(1, int(bar_w) - 8))

    # ── 마우스 이벤트 ─────────────────────────────────────────────

    # ── 툴팁 ─────────────────────────────────────────────────────

    def _tooltip_hide(self):
        if self._tooltip_after:
            self.after_cancel(self._tooltip_after)
            self._tooltip_after = None
        if self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None

    def _tooltip_show(self, task, rx, ry):
        """task 세부 정보 툴팁을 (rx, ry) 화면 절대 좌표 근처에 표시."""
        self._tooltip_hide()

        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#1E293B")
        self._tooltip_win = win

        # ── 내용 빌드 ──
        def row(label, value, fg="#CBD5E1"):
            if not value:
                return
            frm = tk.Frame(win, bg="#1E293B")
            frm.pack(fill="x", padx=10, pady=1)
            tk.Label(frm, text=label, bg="#1E293B", fg="#94A3B8",
                     font=("맑은 고딕", 8), width=7, anchor="e").pack(side="left")
            tk.Label(frm, text=value, bg="#1E293B", fg=fg,
                     font=("맑은 고딕", 8), anchor="w").pack(side="left", padx=(4, 0))

        # 제목
        tk.Label(win, text=task["title"], bg="#1E293B", fg="white",
                 font=("맑은 고딕", 9, "bold"),
                 wraplength=260, justify="left").pack(anchor="w", padx=10, pady=(8, 4))

        prio = task.get("priority", "")
        status = task.get("status", "")
        prio_fg = {"긴급": "#FCA5A5", "높음": "#FDE68A",
                   "보통": "#93C5FD", "낮음": "#6EE7B7"}.get(prio, "#CBD5E1")
        st_fg   = {"진행중": "#60A5FA", "완료": "#34D399",
                   "취소": "#9CA3AF", "대기": "#CBD5E1"}.get(status, "#CBD5E1")

        tk.Frame(win, bg="#334155", height=1).pack(fill="x", padx=8, pady=(0, 4))

        row("우선순위", prio, prio_fg)
        row("상태",     status, st_fg)
        row("과제",     task.get("project", ""))
        row("시스템",   task.get("system", ""))
        row("담당자",   task.get("assignee", ""))
        row("종류",     task.get("type", ""))

        sch = fmt_dt(task.get("scheduled_at", ""))
        dl  = fmt_dt(task.get("deadline", ""))
        eff = task.get("effort", "")
        aeff = task.get("actual_effort", "")

        if sch or dl:
            tk.Frame(win, bg="#334155", height=1).pack(fill="x", padx=8, pady=(4, 2))
        row("시작",   sch)
        row("마감",   dl)
        row("예상",   eff)
        row("실투입", aeff)

        desc = task.get("description", "")
        if desc:
            tk.Frame(win, bg="#334155", height=1).pack(fill="x", padx=8, pady=(4, 2))
            tk.Label(win, text=desc[:120] + ("…" if len(desc) > 120 else ""),
                     bg="#1E293B", fg="#94A3B8", font=("맑은 고딕", 8),
                     wraplength=260, justify="left").pack(anchor="w", padx=10, pady=(2, 6))

        tk.Frame(win, bg="#334155", height=1).pack(fill="x", padx=0, pady=(2, 0))

        # ── 위치 계산 (화면 밖으로 나가지 않도록) ──
        win.update_idletasks()
        tw = win.winfo_reqwidth()
        th = win.winfo_reqheight()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x  = min(rx + 14, sw - tw - 4)
        y  = min(ry + 14, sh - th - 4)
        win.geometry(f"+{x}+{y}")

    def _on_hover(self, event):
        if self._drag_state:
            return
        tid, dt = self._hit_test(event.x, event.y)

        # 커서 변경
        if dt in ("resize_left", "resize_right"):
            self._canvas.config(cursor="sb_h_double_arrow")
        elif dt == "move":
            self._canvas.config(cursor="fleur")
        else:
            self._canvas.config(cursor="arrow")

        # 툴팁: 작업이 바뀔 때만 처리
        if tid == self._last_hover_tid:
            return
        self._last_hover_tid = tid
        self._tooltip_hide()

        if tid is None or dt is None:
            return

        task = next((t for t in self._tasks if t["id"] == tid), None)
        if task is None:
            return

        rx = event.x_root
        ry = event.y_root
        self._tooltip_after = self.after(
            500, lambda: self._tooltip_show(task, rx, ry))

    def _on_leave(self, event):
        self._last_hover_tid = None
        self._tooltip_hide()

    def _set_selected(self, tid):
        """선택 상태 변경 — 전체 redraw 없이 해당 바 스타일만 갱신."""
        prev = self._selected_tid
        self._selected_tid = tid
        for task_id, selected in ((prev, False), (tid, True)):
            if task_id is None:
                continue
            task = next((t for t in self._tasks if t["id"] == task_id), None)
            if task is None:
                continue
            status = task.get("status", "대기")
            prio   = task.get("priority", "보통")
            if status in ("완료", "취소"):
                base_border = "#9CA3AF"
            else:
                base_border = self.PRIO_BORDER.get(prio, "#2563EB")
                if status == "진행중":
                    base_border = "#1D4ED8"
            outline = "#F59E0B" if selected else base_border
            width   = 3        if selected else 2
            for item in self._canvas.find_withtag(f"bar_{task_id}"):
                self._canvas.itemconfig(item, outline=outline, width=width)
            for tag in (f"lrsz_{task_id}", f"rsz_{task_id}"):
                for item in self._canvas.find_withtag(tag):
                    self._canvas.itemconfig(item, fill=outline)
            # 라벨 폰트/색상
            lbl_fg   = "#92400E" if selected else "#1E293B"
            lbl_font = ("맑은 고딕", 9, "bold") if selected else ("맑은 고딕", 9)
            for item in self._canvas.find_withtag(f"lbl_{task_id}"):
                self._canvas.itemconfig(item, fill=lbl_fg, font=lbl_font)
            # 바 텍스트 폰트/색상
            lbl_bt_fg   = "#92400E" if selected else (
                "#1E40AF" if status not in ("완료", "취소") else "#6B7280")
            lbl_bt_font = ("맑은 고딕", 8, "bold") if selected else ("맑은 고딕", 8)
            for item in self._canvas.find_withtag(f"barlbl_{task_id}"):
                self._canvas.itemconfig(item, fill=lbl_bt_fg, font=lbl_bt_font)

    def _on_press(self, event):
        self._tooltip_hide()
        self._last_hover_tid = None
        tid, drag_type = self._hit_test(event.x, event.y)
        if tid is None:
            return
        task = next((t for t in self._tasks if t["id"] == tid), None)
        if task is None:
            return
        # 선택 하이라이트 + 우측 상세 패널 갱신
        self._set_selected(tid)
        self.app.on_task_selected(tid)
        self._drag_state = {
            "task_id":    tid,
            "type":       drag_type,
            "press_x":    self._canvas.canvasx(event.x),
            "orig_start": self._start_min(task),
            "orig_end":   self._end_min(task),
            "cur_start":  self._start_min(task),
            "cur_end":    self._end_min(task),
        }
        self._canvas.config(
            cursor="fleur" if drag_type == "move" else "sb_h_double_arrow")

    def _on_motion(self, event):
        ds = self._drag_state
        if ds is None:
            return
        cx     = self._canvas.canvasx(event.x)
        dx_min = (cx - ds["press_x"]) / self._tw() * 1440.0

        if ds["type"] == "move":
            dur = ds["orig_end"] - ds["orig_start"]
            ns  = self._snap30(max(0.0, min(1440.0 - dur, ds["orig_start"] + dx_min)))
            ne  = ns + dur
        elif ds["type"] == "resize_right":
            ns  = ds["orig_start"]
            ne  = self._snap30(max(ns + self.MIN_DUR_MIN,
                                   min(1440.0, ds["orig_end"] + dx_min)))
        else:  # resize_left
            ne  = ds["orig_end"]
            ns  = self._snap30(min(ne - self.MIN_DUR_MIN,
                                   max(0.0, ds["orig_start"] + dx_min)))

        ds["cur_start"] = ns
        ds["cur_end"]   = ne
        self._update_bar_pos(ds["task_id"], ns, ne)

    def _on_release(self, event):
        ds = self._drag_state
        if ds is None:
            return
        self._drag_state = None
        self._canvas.config(cursor="arrow")

        new_start  = ds["cur_start"]
        new_end    = ds["cur_end"]
        orig_start = ds["orig_start"]
        orig_end   = ds["orig_end"]

        # 시각적으로 원래 상태로 복원 (ChangeCommentDialog 취소 시 그대로 유지)
        self._redraw()

        if abs(new_start - orig_start) < 1 and abs(new_end - orig_end) < 1:
            return  # 변경 없음

        def min_to_hhmm(m: float) -> str:
            m = int(round(max(0, min(1439, m))))
            return f"{m // 60:02d}:{m % 60:02d}"

        delta_s = new_start - orig_start
        delta_e = new_end   - orig_end

        # ── 변경 항목 계산 ──────────────────────────────────────
        data = load_data()
        task = get_task(data, ds["task_id"])
        if task is None:
            return

        changes = []
        today_str = date.today().isoformat()

        # scheduled_at / deadline 의 실제 분(분, 날짜 무관) — 공수 계산용
        def _actual_min(field_val: str):
            try:
                dt = datetime.fromisoformat(field_val)
                return float(dt.hour * 60 + dt.minute)
            except Exception:
                return None

        def _is_field_today(field_val: str) -> bool:
            try:
                return datetime.fromisoformat(field_val).date() == date.today()
            except Exception:
                return False

        if ds["type"] == "move":
            # 이동: delta 방식으로 기존 날짜의 시간만 조정
            if task.get("scheduled_at"):
                try:
                    dt  = datetime.fromisoformat(task["scheduled_at"])
                    nm  = max(0, min(1439, dt.hour * 60 + dt.minute + int(round(delta_s))))
                    new_val = f"{dt.date().isoformat()}T{min_to_hhmm(nm)}"
                    if new_val != task["scheduled_at"]:
                        changes.append({"field": "예정일시",
                                        "old": task["scheduled_at"], "new": new_val})
                except Exception:
                    pass
            if task.get("deadline"):
                try:
                    dt  = datetime.fromisoformat(task["deadline"])
                    nm  = max(0, min(1439, dt.hour * 60 + dt.minute + int(round(delta_e))))
                    new_val = f"{dt.date().isoformat()}T{min_to_hhmm(nm)}"
                    if new_val != task["deadline"]:
                        changes.append({"field": "마감일시",
                                        "old": task["deadline"], "new": new_val})
                except Exception:
                    pass

        elif ds["type"] == "resize_right":
            # 오른쪽 리사이즈: 종료를 오늘 날짜의 절대 위치로 설정
            new_dl = f"{today_str}T{min_to_hhmm(new_end)}"
            old_dl = task.get("deadline", "")
            if new_dl != old_dl:
                changes.append({"field": "마감일시", "old": old_dl, "new": new_dl})

            # 공수: scheduled_at 이 오늘이면 실제 시각 기준, 아니면 표시상 orig_start 기준
            sch_val = task.get("scheduled_at", "")
            if sch_val and _is_field_today(sch_val):
                ref_start = _actual_min(sch_val) or orig_start
            else:
                ref_start = orig_start  # 클램핑된 값 그대로 (과거 시작)
            dur_min = int(round(new_end - ref_start))
            new_eff = format_effort_min(dur_min) if dur_min > 0 else ""
            if new_eff and new_eff != "—" and new_eff != task.get("effort", ""):
                changes.append({"field": "공수",
                                "old": task.get("effort", ""), "new": new_eff})

        else:  # resize_left
            # 왼쪽 리사이즈: 시작을 오늘 날짜의 절대 위치로 설정
            new_sch = f"{today_str}T{min_to_hhmm(new_start)}"
            old_sch = task.get("scheduled_at", "")
            if new_sch != old_sch:
                changes.append({"field": "예정일시", "old": old_sch, "new": new_sch})

            # 공수: deadline 이 오늘이면 실제 시각 기준, 아니면 표시상 orig_end 기준
            dl_val = task.get("deadline", "")
            if dl_val and _is_field_today(dl_val):
                ref_end = _actual_min(dl_val) or orig_end
            else:
                ref_end = orig_end  # 클램핑된 값 그대로 (미래 마감)
            # 미래 마감(1440)이면 공수 업데이트 생략 (계산 불가)
            if ref_end < 1440.0:
                dur_min = int(round(ref_end - new_start))
                new_eff = format_effort_min(dur_min) if dur_min > 0 else ""
                if new_eff and new_eff != "—" and new_eff != task.get("effort", ""):
                    changes.append({"field": "공수",
                                    "old": task.get("effort", ""), "new": new_eff})

        if not changes:
            return

        # ── 변경 이력 입력 창 → 저장 ────────────────────────────
        FIELD_KEY = {"예정일시": "scheduled_at", "마감일시": "deadline", "공수": "effort"}

        def do_save(comment):
            data2 = load_data()
            task2 = get_task(data2, ds["task_id"])
            if task2 is None:
                return
            now_s = now_str()
            for ch in changes:
                key = FIELD_KEY.get(ch["field"])
                if key:
                    task2[key] = ch["new"]
            task2.setdefault("change_history", []).append({
                "ts": now_s, "changes": changes, "comment": comment})
            task2["updated_at"] = now_s
            save_data(data2)
            self.app.refresh_list()

        ChangeCommentDialog(self.winfo_toplevel(), changes, do_save)

    def _on_double(self, event):
        self._drag_state = None
        tid, _ = self._hit_test(event.x, event.y)
        if tid is not None:
            self.app.edit_task(tid)

    def _on_right_click(self, event):
        tid, _ = self._hit_test(event.x, event.y)
        if tid is None:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="✏ 수정", command=lambda: self.app.edit_task(tid))
        menu.add_separator()
        for s in STATUSES:
            menu.add_command(label=f"→ {s}",
                             command=lambda st=s: self.app.set_status(tid, st))
        menu.add_separator()
        menu.add_command(label="🗑 삭제", command=lambda: self.app.delete_task(tid))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


# ---------------------------------------------------------------------------

_CIRC = {i: chr(0x245F + i) for i in range(1, 21)}  # ①~⑳

TREE_COLS    = ("seq", "priority", "title", "project", "system", "assignee", "status",
                "scheduled", "deadline_dt", "effort", "actual_effort", "dday")
TREE_HEADERS = [("seq","순서",42), ("priority","우선",50), ("title","작업명",120),
                ("project","과제명",80), ("system","시스템",72), ("assignee","담당자",52),
                ("status","상태",52), ("scheduled","시작일시",100),
                ("deadline_dt","종료일시",100), ("effort","예상공수",62),
                ("actual_effort","실투입",58), ("dday","D-Day",50)]


def _is_date_task(task, target: date) -> bool:
    """target 날짜가 작업의 시작~종료 범위에 포함되면 True."""
    sch = task.get("scheduled_at", "")
    dl  = task.get("deadline", "")
    try:
        sch_d = datetime.fromisoformat(sch).date() if sch else None
    except Exception:
        sch_d = None
    try:
        dl_d = datetime.fromisoformat(dl).date() if dl else None
    except Exception:
        dl_d = None
    if sch_d and dl_d:
        return sch_d <= target <= dl_d
    if sch_d:
        return sch_d == target
    return False


def _is_today_task(task):
    """오늘 날짜가 작업의 시작~종료 범위에 포함되면 True."""
    today = date.today()
    sch = task.get("scheduled_at", "")
    dl  = task.get("deadline", "")
    try:
        sch_d = datetime.fromisoformat(sch).date() if sch else None
    except Exception:
        sch_d = None
    try:
        dl_d = datetime.fromisoformat(dl).date() if dl else None
    except Exception:
        dl_d = None

    if sch_d and dl_d:
        return sch_d <= today <= dl_d
    if sch_d:
        return sch_d == today
    if dl_d:
        return dl_d == today
    return False


class TaskListPanel(tk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, bg="white")
        self.app = app
        self._sort_col = "priority"
        self._sort_rev = False
        self._drag_item = None
        self._all_tasks = []
        self._highlighted_iids: set = set()   # 현재 관계 하이라이트된 IID
        # 오늘 탭 순서: 파일에서 초기 로드 후 메모리에서만 관리
        self._today_order = load_data().get("today_display_order", [])
        self._build()

    # ── UI 구성 ────────────────────────────────────────────

    def _build(self):
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

        # 탭 프레임
        frm_active = tk.Frame(self._nb, bg="white")
        frm_done   = tk.Frame(self._nb, bg="white")
        frm_today  = tk.Frame(self._nb, bg="white")
        self._nb.add(frm_active, text="  미종료  ")
        self._nb.add(frm_done,   text="  종료  ")
        self._nb.add(frm_today,  text="  오늘  ")

        self._build_active_tab(frm_active)
        self._build_done_tab(frm_done)
        self._build_today_tab(frm_today)

    def _make_tree(self, parent, sortable=True):
        """frm(parent 자식) 안에 tree + scrollbar를 생성하고 tree를 반환."""
        frm = tk.Frame(parent, bg="white")
        frm.pack(fill="both", expand=True)
        tree = ttk.Treeview(frm, columns=TREE_COLS,
                            show="headings", selectmode="browse")
        sb = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        for col, hdr, w in TREE_HEADERS:
            if sortable:
                tree.heading(col, text=hdr, command=lambda c=col: self._sort_by(c))
            else:
                tree.heading(col, text=hdr)
            tree.column(col, width=w, anchor="center", stretch=(col == "title"))
        tree.tag_configure("진행중",  background="#DBEAFE")
        tree.tag_configure("related", background="#EDE9FE",
                           font=("맑은 고딕", 9, "bold"))  # 연관 작업 하이라이트
        tree.tag_configure("완료",   background="#E5E7EB", foreground="#9CA3AF",
                           font=("맑은 고딕", 9, "overstrike"))
        tree.tag_configure("취소",   background="#E5E7EB", foreground="#9CA3AF",
                           font=("맑은 고딕", 9, "overstrike"))
        # 마감 임박 (미완료 작업에만 적용)
        tree.tag_configure("overdue", background="#FCA5A5")  # 초과 — 빨강
        tree.tag_configure("dday",    background="#FCA5A5")  # D-Day — 빨강
        tree.tag_configure("d1",      background="#FED7AA")  # 1일 전 — 주황
        tree.tag_configure("d3",      background="#FEF08A")  # 3일 전 — 노랑
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return tree

    def _build_active_tab(self, parent):
        bar = tk.Frame(parent, bg="#F1F5F9", pady=6)
        bar.pack(fill="x")
        tk.Label(bar, text="우선순위", bg="#F1F5F9", font=FONT_S).pack(side="left", padx=(8, 2))
        self._v_active_prio = tk.StringVar(value=ALL_FILTER)
        ttk.Combobox(bar, textvariable=self._v_active_prio,
                     values=[ALL_FILTER] + PRIORITIES,
                     state="readonly", width=7, font=FONT_S).pack(side="left", padx=(0, 6))
        self._v_active_prio.trace_add("write", lambda *_: self._reload_active())
        tk.Label(bar, text="검색", bg="#F1F5F9", font=FONT_S).pack(side="left", padx=(0, 2))
        self._v_active_search = tk.StringVar()
        self._v_active_search.trace_add("write", lambda *_: self._reload_active())
        ttk.Entry(bar, textvariable=self._v_active_search,
                  font=FONT_S, width=12).pack(side="left", padx=(0, 4))

        self._tree_active = self._make_tree(parent, sortable=True)
        self._tree_active.bind("<<TreeviewSelect>>",
                               lambda e: self._on_select(self._tree_active))
        self._tree_active.bind("<Double-1>",
                               lambda e: self._on_double_click(self._tree_active))
        self._tree_active.bind("<Button-3>",
                               lambda e: self._context_menu(e, self._tree_active))
        self._tree_active.bind("<space>",
                               lambda e: self._toggle_status(self._tree_active))

    def _build_done_tab(self, parent):
        bar = tk.Frame(parent, bg="#F1F5F9", pady=6)
        bar.pack(fill="x")
        tk.Label(bar, text="검색", bg="#F1F5F9", font=FONT_S).pack(side="left", padx=(8, 2))
        self._v_done_search = tk.StringVar()
        self._v_done_search.trace_add("write", lambda *_: self._reload_done())
        ttk.Entry(bar, textvariable=self._v_done_search,
                  font=FONT_S, width=16).pack(side="left", padx=(0, 4))

        self._tree_done = self._make_tree(parent, sortable=True)
        self._tree_done.bind("<<TreeviewSelect>>",
                             lambda e: self._on_select(self._tree_done))
        self._tree_done.bind("<Double-1>",
                             lambda e: self._on_double_click(self._tree_done))
        self._tree_done.bind("<Button-3>",
                             lambda e: self._context_menu(e, self._tree_done))

    def _build_today_tab(self, parent):
        bar = tk.Frame(parent, bg="#F1F5F9", pady=5)
        bar.pack(fill="x")
        tk.Label(bar,
                 text="오늘 작업  |  목록: 드래그로 순서 조정",
                 bg="#F1F5F9", fg="#64748B", font=FONT_S).pack(side="left", padx=8)

        # 뷰 전환 버튼
        self._btn_today_timeline = tk.Button(
            bar, text="🕐 타임라인", font=FONT_S, relief="flat", cursor="hand2",
            bg="#F1F5F9", fg="#374151",
            command=lambda: self._switch_today_view("timeline"))
        self._btn_today_timeline.pack(side="right", padx=4)
        self._btn_today_list = tk.Button(
            bar, text="📋 목록", font=FONT_S, relief="flat", cursor="hand2",
            bg="#2563EB", fg="white",
            command=lambda: self._switch_today_view("list"))
        self._btn_today_list.pack(side="right", padx=4)

        # ── 목록 뷰 컨테이너 ──
        self._today_list_frame = tk.Frame(parent, bg="white")
        self._today_list_frame.pack(fill="both", expand=True)

        self._tree_today = self._make_tree(self._today_list_frame, sortable=False)
        self._tree_today.bind("<<TreeviewSelect>>",
                              lambda e: self._on_select(self._tree_today))
        self._tree_today.bind("<Double-1>",
                              lambda e: self._on_double_click(self._tree_today))
        self._tree_today.bind("<Button-3>",
                              lambda e: self._context_menu(e, self._tree_today))
        self._tree_today.bind("<space>",
                              lambda e: self._toggle_status(self._tree_today))
        self._tree_today.bind("<ButtonPress-1>",    self._today_drag_start)
        self._tree_today.bind("<B1-Motion>",        self._today_drag_motion)
        self._tree_today.bind("<ButtonRelease-1>",  self._today_drag_end)

        # ── 타임라인 뷰 컨테이너 (초기 숨김) ──
        self._today_timeline_frame = tk.Frame(parent, bg="white")
        self._timeline_view = TodayTimelineView(self._today_timeline_frame, self.app)
        self._timeline_view.pack(fill="both", expand=True)

        self._today_view_mode = "list"

    def _switch_today_view(self, mode: str):
        self._today_view_mode = mode
        if mode == "list":
            self._today_timeline_frame.pack_forget()
            self._today_list_frame.pack(fill="both", expand=True)
            self._btn_today_list.config(bg="#2563EB", fg="white")
            self._btn_today_timeline.config(bg="#F1F5F9", fg="#374151")
        else:
            self._today_list_frame.pack_forget()
            self._today_timeline_frame.pack(fill="both", expand=True)
            self._btn_today_list.config(bg="#F1F5F9", fg="#374151")
            self._btn_today_timeline.config(bg="#2563EB", fg="white")
            today_tasks = [t for t in self._all_tasks if _is_today_task(t)]
            self._timeline_view.load(today_tasks)

    # ── 데이터 로딩 ────────────────────────────────────────

    def load(self, tasks, auto_resize=False):
        self._all_tasks = tasks
        self._reload_active()
        self._reload_done()
        self._reload_today()
        if auto_resize:
            self.after(50, self._auto_resize_columns)

    def _auto_resize_columns(self):
        """모든 트리 컬럼 너비를 헤더+내용 기준으로 자동 조정."""
        import tkinter.font as tkfont
        f = tkfont.Font(family="맑은 고딕", size=9)
        pad = 14   # 좌우 여백 합산
        min_w = {col: w for col, _, w in TREE_HEADERS}

        for tree in (self._tree_active, self._tree_done, self._tree_today):
            col_max = {col: w for col, _, w in TREE_HEADERS}

            # 헤더 너비
            for col, hdr, _ in TREE_HEADERS:
                col_max[col] = max(col_max[col], f.measure(hdr) + pad)

            # 각 행 내용 너비
            for iid in tree.get_children():
                vals = tree.item(iid, "values")
                for (col, _, _), v in zip(TREE_HEADERS, vals):
                    col_max[col] = max(col_max[col], f.measure(str(v)) + pad)

            for col, w in col_max.items():
                tree.column(col, width=min(w, 220))

    def _seq_str(self, task, row_idx=None):
        s = task.get("seq_order")
        if s is not None:
            return _CIRC.get(s, str(s))   # ① ② ③ — 명시적 순서
        if row_idx is not None:
            return str(row_idx)            # 1 2 3 — 표시 위치
        return ""

    _PRIO_ICON   = {"긴급": "🔴 긴급", "높음": "🟠 높음", "보통": "🟡 보통", "낮음": "⚪ 낮음"}
    _STATUS_ICON = {"대기": "⏸ 대기", "진행중": "▶ 진행중", "완료": "✅ 완료", "취소": "🚫 취소"}

    def _insert(self, tree, task, row_idx=None):
        status = task["status"]
        if status in ("완료", "취소"):
            tag = status
        else:
            # 마감 기준 색상 (미완료 작업)
            dl = task.get("deadline", "")
            tag = ""
            if dl:
                try:
                    delta = (datetime.fromisoformat(dl).date() - date.today()).days
                    if delta < 0:
                        tag = "overdue"
                    elif delta == 0:
                        tag = "dday"
                    elif delta == 1:
                        tag = "d1"
                    elif delta <= 3:
                        tag = "d3"
                    elif status == "진행중":
                        tag = "진행중"
                except Exception:
                    pass
            elif status == "진행중":
                tag = "진행중"

        prio_disp   = self._PRIO_ICON.get(task["priority"], task["priority"])
        status_disp = self._STATUS_ICON.get(status, status)

        tree.insert("", "end", iid=str(task["id"]),
                    values=(self._seq_str(task, row_idx),
                            prio_disp,
                            task["title"],
                            task.get("project", ""),
                            task.get("system", ""),
                            task.get("assignee", ""),
                            status_disp,
                            fmt_dt_short(task.get("scheduled_at", "")),
                            fmt_dt_short(task.get("deadline", "")),
                            task.get("effort", ""),
                            task.get("actual_effort", ""),
                            calc_dday(task.get("deadline"))),
                    tags=(tag,))

    def _keyword_match(self, task, keyword):
        if not keyword:
            return True
        searchable = " ".join([
            task.get("title", ""),
            task.get("project", ""),
            task.get("system", ""),
            task.get("assignee", ""),
            task.get("type", ""),
            task.get("priority", ""),
            task.get("status", ""),
            task.get("description", ""),
            task.get("effort", ""),
            " ".join(task.get("tags", [])),
            task.get("deadline", ""),          # 종료일 (예: 2026-04-08T18:00)
            task.get("scheduled_at", ""),      # 시작일
        ])
        return keyword.lower() in searchable.lower()

    def _sort_tasks(self, tasks):
        prio_order = {p: i for i, p in enumerate(PRIORITIES)}
        def key(t):
            if self._sort_col == "seq":
                s = t.get("seq_order")
                return (0, s) if s is not None else (1, 9999)
            if self._sort_col == "priority":
                return prio_order.get(t["priority"], 99)
            if self._sort_col == "dday":
                dl = t.get("deadline", "")
                return dl if dl else "9999"
            return str(t.get(self._sort_col, ""))
        return sorted(tasks, key=key, reverse=self._sort_rev)

    def _reload_active(self):
        sel = self._sel_from(self._tree_active)
        self._tree_active.delete(*self._tree_active.get_children())
        kw   = self._v_active_search.get().strip().lower()
        prio = self._v_active_prio.get()
        tasks = [t for t in self._all_tasks if t["status"] not in ("완료", "취소")]
        if prio != ALL_FILTER:
            tasks = [t for t in tasks if t["priority"] == prio]
        tasks = [t for t in tasks if self._keyword_match(t, kw)]
        for i, t in enumerate(self._sort_tasks(tasks), 1):
            self._insert(self._tree_active, t, row_idx=i)
        if sel and self._tree_active.exists(str(sel)):
            self._tree_active.selection_set(str(sel))

    def _reload_done(self):
        sel = self._sel_from(self._tree_done)
        self._tree_done.delete(*self._tree_done.get_children())
        kw    = self._v_done_search.get().strip().lower()
        tasks = [t for t in self._all_tasks if t["status"] in ("완료", "취소")]
        tasks = [t for t in tasks if self._keyword_match(t, kw)]
        tasks.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
        for i, t in enumerate(tasks, 1):
            self._insert(self._tree_done, t, row_idx=i)
        if sel and self._tree_done.exists(str(sel)):
            self._tree_done.selection_set(str(sel))

    def _reload_today(self):
        sel = self._sel_from(self._tree_today)
        self._tree_today.delete(*self._tree_today.get_children())

        today_tasks = [t for t in self._all_tasks if _is_today_task(t)]

        # 메모리에 유지된 순서 사용 (drag로만 갱신)
        order_map = {tid: i for i, tid in enumerate(self._today_order)}

        def today_key(t):
            if t["id"] in order_map:
                return (0, order_map[t["id"]])
            s = t.get("seq_order")
            return (1, s if s is not None else 9999)

        today_tasks.sort(key=today_key)
        for i, t in enumerate(today_tasks, 1):
            self._insert(self._tree_today, t, row_idx=i)
        if sel and self._tree_today.exists(str(sel)):
            self._tree_today.selection_set(str(sel))

        # 타임라인 뷰도 갱신 (표시 중인 경우)
        if getattr(self, "_today_view_mode", "list") == "timeline":
            self._timeline_view.load(today_tasks)

    # ── 이벤트 ────────────────────────────────────────────

    def _sel_from(self, tree):
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def _on_select(self, tree):
        tid = self._sel_from(tree)
        if tid is not None:
            self.app.on_task_selected(tid)
            self._highlight_related(tid)
        else:
            self._clear_highlights()

    def _highlight_related(self, task_id):
        """부모·서브·연계 작업 행에 'related' 태그 추가."""
        self._clear_highlights()

        data = load_data()
        task = get_task(data, task_id)
        if task is None:
            return

        related = set()
        if task.get("parent_id"):
            related.add(str(task["parent_id"]))
        related.update(str(i) for i in task.get("sub_ids", []))
        related.update(str(i) for i in task.get("linked_ids", []))
        if not related:
            return

        for tree in (self._tree_active, self._tree_done, self._tree_today):
            for iid in related:
                if tree.exists(iid):
                    tags = list(tree.item(iid, "tags"))
                    if "related" not in tags:
                        tags.append("related")
                        tree.item(iid, tags=tuple(tags))
                    self._highlighted_iids.add(iid)

    def _clear_highlights(self):
        """이전 'related' 태그를 모두 제거."""
        for tree in (self._tree_active, self._tree_done, self._tree_today):
            for iid in self._highlighted_iids:
                if tree.exists(iid):
                    tags = [t for t in tree.item(iid, "tags") if t != "related"]
                    tree.item(iid, tags=tuple(tags))
        self._highlighted_iids.clear()

    def _on_double_click(self, tree):
        tid = self._sel_from(tree)
        if tid is not None:
            self.app.edit_task(tid)

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        self._reload_active()
        self._reload_done()

    def _toggle_status(self, tree):
        tid = self._sel_from(tree)
        if tid is None:
            return
        data = load_data()
        task = get_task(data, tid)
        if task is None:
            return
        cycle = {"대기": "진행중", "진행중": "완료", "완료": "대기", "취소": "대기"}
        next_status = cycle.get(task["status"], "진행중")
        # 완료 전환은 app.set_status 를 통해 팝업 처리
        self.app.set_status(tid, next_status)

    def _context_menu(self, event, tree):
        row = tree.identify_row(event.y)
        if not row:
            return
        tree.selection_set(row)
        tid = int(row)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="✏ 수정",     command=lambda: self.app.edit_task(tid))
        menu.add_command(label="📋 복제",    command=lambda: self.app.duplicate_task(tid))
        menu.add_command(label="📄 내보내기", command=lambda: self.app.export_task(tid))
        menu.add_separator()
        for s in STATUSES:
            menu.add_command(label=f"→ {s}",
                             command=lambda st=s: self.app.set_status(tid, st))
        menu.add_separator()
        menu.add_command(label="🗑 삭제", command=lambda: self.app.delete_task(tid))
        menu.tk_popup(event.x_root, event.y_root)

    # ── 오늘 탭 드래그 ────────────────────────────────────

    def _today_drag_start(self, event):
        row = self._tree_today.identify_row(event.y)
        if row:
            self._drag_item = row
            self._tree_today.selection_set(row)

    def _today_drag_motion(self, event):
        if not self._drag_item:
            return
        target = self._tree_today.identify_row(event.y)
        if target and target != self._drag_item:
            idx = self._tree_today.index(target)
            self._tree_today.move(self._drag_item, "", idx)

    def _today_drag_end(self, event):
        if self._drag_item:
            self._save_today_order()
        self._drag_item = None

    def _save_today_order(self):
        """오늘 탭의 현재 행 순서를 메모리 + 파일에 저장하고 순서 컬럼 갱신."""
        items = self._tree_today.get_children()
        ordered_ids = [int(iid) for iid in items]
        self._today_order = ordered_ids          # 메모리 즉시 반영
        data = load_data()
        data["today_display_order"] = ordered_ids
        save_data(data)
        # 순서 컬럼 값 즉시 갱신 (드래그 후 번호 반영)
        for i, iid in enumerate(items, 1):
            tid = int(iid)
            task = next((t for t in self._all_tasks if t["id"] == tid), None)
            seq_s = self._seq_str(task, i) if task else str(i)
            vals = list(self._tree_today.item(iid, "values"))
            vals[0] = seq_s
            self._tree_today.item(iid, values=vals)

    # ── 외부 인터페이스 ───────────────────────────────────

    def select(self, task_id):
        for tree in (self._tree_active, self._tree_done, self._tree_today):
            if tree.exists(str(task_id)):
                tree.selection_set(str(task_id))
                tree.see(str(task_id))
                break


# ---------------------------------------------------------------------------
# 공수 리포트
# ---------------------------------------------------------------------------

class EffortReportDialog(tk.Toplevel):
    """기간 + 담당자 기준 일별 작업 내역 및 과제별 투입공수 리포트."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("공수 리포트")
        self.geometry("1000x620")
        self.minsize(800, 500)
        self.configure(bg="#F8FAFC")
        self._build()
        self._query()   # 초기 조회

    # ── UI ────────────────────────────────────────────────

    def _build(self):
        # 헤더 필터 바
        bar = tk.Frame(self, bg="#1E40AF", pady=8)
        bar.pack(fill="x")
        tk.Label(bar, text="📊 공수 리포트", bg="#1E40AF", fg="white",
                 font=("맑은 고딕", 12, "bold")).pack(side="left", padx=14)

        # 담당자
        tk.Label(bar, text="담당자", bg="#1E40AF", fg="#BFDBFE",
                 font=FONT_S).pack(side="left", padx=(20, 4))
        self._v_assignee = tk.StringVar(value="전체")
        self._cb_assignee = ttk.Combobox(bar, textvariable=self._v_assignee,
                                          state="readonly", width=10, font=FONT_S)
        self._cb_assignee.pack(side="left", padx=(0, 16))
        self._load_assignees()

        # 기간
        tk.Label(bar, text="시작", bg="#1E40AF", fg="#BFDBFE",
                 font=FONT_S).pack(side="left", padx=(0, 4))
        self._de_start = DateEntry(bar, locale="ko_KR", date_pattern="yyyy-mm-dd",
                                    width=11, font=FONT_S,
                                    background="#1E3A8A", foreground="white",
                                    selectbackground="#2563EB")
        self._de_start.pack(side="left", padx=(0, 6))
        # 기본: 이번 달 1일
        self._de_start.set_date(date.today().replace(day=1))

        tk.Label(bar, text="~", bg="#1E40AF", fg="white",
                 font=FONT_S).pack(side="left", padx=4)
        self._de_end = DateEntry(bar, locale="ko_KR", date_pattern="yyyy-mm-dd",
                                  width=11, font=FONT_S,
                                  background="#1E3A8A", foreground="white",
                                  selectbackground="#2563EB")
        self._de_end.pack(side="left", padx=(0, 16))
        # 기본: 오늘
        self._de_end.set_date(date.today())

        ttk.Button(bar, text="조회", command=self._query).pack(side="left")

        # 본문: 좌(일별) + 우(과제별)
        pane = tk.PanedWindow(self, orient="horizontal",
                               sashwidth=5, bg="#E2E8F0")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        # 좌 패널
        left = tk.Frame(pane, bg="white")
        pane.add(left, minsize=380, width=560)
        tk.Label(left, text="일별 작업 내역",
                 bg="#F1F5F9", font=FONT_B, fg="#1E293B",
                 pady=4).pack(fill="x", padx=0)
        self._build_daily_panel(left)

        # 우 패널
        right = tk.Frame(pane, bg="white")
        pane.add(right, minsize=260)
        tk.Label(right, text="과제별 투입공수",
                 bg="#F1F5F9", font=FONT_B, fg="#1E293B",
                 pady=4).pack(fill="x")
        self._build_project_panel(right)

        # 하단 상태
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var,
                 bg="#E2E8F0", fg="#475569", font=FONT_S,
                 anchor="w", pady=3, padx=8).pack(fill="x", side="bottom")

    def _build_daily_panel(self, parent):
        frm = tk.Frame(parent, bg="white")
        frm.pack(fill="both", expand=True)
        self._daily_canvas = tk.Canvas(frm, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self._daily_canvas.yview)
        self._daily_canvas.configure(yscrollcommand=sb.set)
        self._daily_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._daily_inner = tk.Frame(self._daily_canvas, bg="white")
        self._daily_win   = self._daily_canvas.create_window(
            (0, 0), window=self._daily_inner, anchor="nw")
        self._daily_inner.bind("<Configure>",
            lambda e: self._daily_canvas.configure(
                scrollregion=self._daily_canvas.bbox("all")))
        self._daily_canvas.bind("<Configure>",
            lambda e: self._daily_canvas.itemconfig(self._daily_win, width=e.width))

    def _build_project_panel(self, parent):
        cols = ("project", "effort", "pct", "bar")
        self._proj_tree = ttk.Treeview(parent, columns=cols,
                                        show="headings", selectmode="none")
        self._proj_tree.heading("project", text="과제명")
        self._proj_tree.heading("effort",  text="투입공수")
        self._proj_tree.heading("pct",     text="비율")
        self._proj_tree.heading("bar",     text="")
        self._proj_tree.column("project", width=130, anchor="w")
        self._proj_tree.column("effort",  width=80,  anchor="center")
        self._proj_tree.column("pct",     width=55,  anchor="center")
        self._proj_tree.column("bar",     width=110, anchor="w", stretch=True)
        sb = ttk.Scrollbar(parent, orient="vertical", command=self._proj_tree.yview)
        self._proj_tree.configure(yscrollcommand=sb.set)
        self._proj_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── 데이터 조회 ────────────────────────────────────────

    def _load_assignees(self):
        data = load_data()
        assignees = sorted({t.get("assignee", "").strip()
                            for t in data["tasks"]
                            if t.get("assignee", "").strip()})
        self._cb_assignee["values"] = ["전체"] + assignees

    def _query(self):
        try:
            start = self._de_start.get_date()
            end   = self._de_end.get_date()
        except Exception:
            return
        if start > end:
            start, end = end, start

        assignee = self._v_assignee.get()
        data     = load_data()
        tasks    = self._filter_tasks(data["tasks"], start, end, assignee)

        self._render_daily(tasks, start, end)
        self._render_projects(tasks)

    def _filter_tasks(self, tasks, start, end, assignee):
        result = []
        for t in tasks:
            if assignee != "전체" and t.get("assignee", "").strip() != assignee:
                continue
            # 작업의 날짜 범위가 조회 기간과 겹치면 포함
            sch = t.get("scheduled_at", "")
            dl  = t.get("deadline", "")
            try:
                sch_d = datetime.fromisoformat(sch).date() if sch else None
            except Exception:
                sch_d = None
            try:
                dl_d = datetime.fromisoformat(dl).date() if dl else None
            except Exception:
                dl_d = None

            t_start = sch_d or dl_d
            t_end   = dl_d  or sch_d
            if t_start is None:
                continue
            # 겹치면 포함
            if t_start <= end and t_end >= start:
                result.append(t)
        return result

    def _work_date(self, task):
        """작업의 대표 날짜 (scheduled_at 우선)."""
        for key in ("scheduled_at", "deadline"):
            v = task.get(key, "")
            if v:
                try:
                    return datetime.fromisoformat(v).date()
                except Exception:
                    pass
        return None

    # ── 렌더링 ─────────────────────────────────────────────

    def _render_daily(self, tasks, start, end):
        for w in self._daily_inner.winfo_children():
            w.destroy()

        # 날짜별 그룹화 (대표 날짜 기준)
        from collections import defaultdict
        day_map = defaultdict(list)
        for t in tasks:
            d = self._work_date(t)
            if d:
                day_map[d].append(t)

        total_min = 0
        cur = start
        while cur <= end:
            day_tasks = day_map.get(cur, [])
            # 날짜 헤더
            hdr_bg = "#DBEAFE" if day_tasks else "#F1F5F9"
            hdr = tk.Frame(self._daily_inner, bg=hdr_bg)
            hdr.pack(fill="x", pady=(6, 0))
            dow = ["월", "화", "수", "목", "금", "토", "일"][cur.weekday()]
            day_effort = sum(
                parse_effort_min(t.get("actual_effort") or t.get("effort", ""))
                for t in day_tasks)
            total_min += day_effort
            hdr_text = f"  {cur.strftime('%Y-%m-%d')} ({dow})"
            if day_effort:
                hdr_text += f"   총 {format_effort_min(day_effort)}"
            tk.Label(hdr, text=hdr_text, bg=hdr_bg,
                     font=FONT_B if day_tasks else FONT_S,
                     fg="#1E40AF" if day_tasks else "#94A3B8",
                     anchor="w").pack(fill="x", padx=8, pady=3)

            for t in sorted(day_tasks, key=lambda x: x.get("seq_order") or 9999):
                effort_raw = t.get("actual_effort") or t.get("effort") or ""
                effort_min = parse_effort_min(effort_raw)
                proj  = t.get("project") or t.get("system") or "—"
                row = tk.Frame(self._daily_inner, bg="white")
                row.pack(fill="x", padx=4, pady=1)
                tk.Label(row, text=f"  {t['title']}", bg="white",
                         font=FONT_S, fg="#1E293B", anchor="w",
                         width=28).pack(side="left")
                tk.Label(row, text=proj, bg="white", font=FONT_S,
                         fg="#6B7280", anchor="w", width=14).pack(side="left")
                effort_lbl = format_effort_min(effort_min) if effort_min else (effort_raw or "—")
                fg_e = "#2563EB" if effort_min else "#94A3B8"
                tk.Label(row, text=effort_lbl, bg="white", font=FONT_S,
                         fg=fg_e, width=9, anchor="e").pack(side="right", padx=6)
                status_icon = {"완료": "✅", "진행중": "▶", "대기": "⏸", "취소": "🚫"}.get(
                    t["status"], "")
                tk.Label(row, text=status_icon, bg="white",
                         font=FONT_S).pack(side="right")

            cur += timedelta(days=1)

        if not any(day_map.values()):
            tk.Label(self._daily_inner, text="해당 기간에 작업이 없습니다.",
                     bg="white", fg="#94A3B8", font=FONT_S).pack(pady=30)

        self._status_var.set(
            f"조회된 작업 {len(tasks)}건  |  총 투입공수 {format_effort_min(total_min)}")

    def _render_projects(self, tasks):
        for row in self._proj_tree.get_children():
            self._proj_tree.delete(row)

        from collections import defaultdict
        proj_map = defaultdict(int)
        for t in tasks:
            proj  = t.get("project") or t.get("system") or "(미지정)"
            mins  = parse_effort_min(t.get("actual_effort") or t.get("effort", ""))
            proj_map[proj] += mins

        total_min = sum(proj_map.values()) or 1
        BAR_LEN = 12  # 최대 막대 길이 (■ 문자 수)

        for proj, mins in sorted(proj_map.items(), key=lambda x: -x[1]):
            pct = mins / total_min * 100
            bar = "■" * max(1, round(pct / 100 * BAR_LEN))
            self._proj_tree.insert("", "end", values=(
                proj,
                format_effort_min(mins),
                f"{pct:.1f}%",
                bar,
            ))


# ---------------------------------------------------------------------------
# 순서 관리 팝업
# ---------------------------------------------------------------------------
# 종료 처리 팝업 (실제 투입공수 + 최종결과)
# ---------------------------------------------------------------------------

class CloseTaskDialog(tk.Toplevel):
    """상태를 '완료'로 변경할 때 투입공수·결과 요약·점수·피드백을 입력받는 팝업."""

    STARS = ["—", "★", "★★", "★★★", "★★★★", "★★★★★"]

    def __init__(self, parent, task, on_confirm):
        super().__init__(parent)
        self.task       = task
        self.on_confirm = on_confirm
        self.title("작업 종료 처리")
        unchecked_count = sum(1 for td in task.get("todos", []) if not td.get("done"))
        height = 420 + max(0, unchecked_count) * 20
        self.geometry(f"500x{height}")
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg="white")
        self._score_var = tk.IntVar(value=0)
        self._build()

    def _build(self):
        tk.Label(self, text=f"✅  {self.task['title']}  —  종료 처리",
                 bg="white", font=FONT_B, fg="#1E293B").pack(anchor="w", padx=14, pady=(12, 8))

        # 미완료 To-Do 경고
        unchecked = [td for td in self.task.get("todos", []) if not td.get("done")]
        if unchecked:
            warn_frm = tk.Frame(self, bg="#FEF3C7", relief="solid", bd=1)
            warn_frm.pack(fill="x", padx=14, pady=(0, 10))
            tk.Label(warn_frm,
                     text=f"⚠  미완료 To-Do 항목이 {len(unchecked)}개 있습니다.",
                     bg="#FEF3C7", fg="#92400E", font=FONT_S,
                     anchor="w").pack(fill="x", padx=8, pady=(6, 2))
            for td in unchecked:
                tk.Label(warn_frm, text=f"  • {td['text']}",
                         bg="#FEF3C7", fg="#78350F", font=FONT_S,
                         anchor="w").pack(fill="x", padx=8)
            tk.Label(warn_frm, bg="#FEF3C7").pack(pady=3)

        # 버튼 먼저 pack (항상 보이도록)
        btn_frm = tk.Frame(self, bg="white")
        btn_frm.pack(side="bottom", fill="x", padx=14, pady=(4, 12))
        ttk.Button(btn_frm, text="종료 확정", command=self._ok).pack(side="right")
        ttk.Button(btn_frm, text="취소", command=self.destroy).pack(side="right", padx=4)

        frm = tk.Frame(self, bg="white")
        frm.pack(fill="both", expand=True, padx=14)
        frm.columnconfigure(1, weight=1)

        # 실제 투입공수
        tk.Label(frm, text="실제 투입공수", bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=12).grid(row=0, column=0, sticky="e", pady=6)
        self.v_actual_effort = tk.StringVar(value=self.task.get("effort", ""))
        effort_cell = tk.Frame(frm, bg="white")
        effort_cell.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=6)
        ttk.Entry(effort_cell, textvariable=self.v_actual_effort,
                  width=14, font=FONT).pack(side="left")
        tk.Label(effort_cell, text="예) 1d 4h", bg="white",
                 fg="#94A3B8", font=("맑은 고딕", 8)).pack(side="left", padx=6)

        # 결과 요약
        tk.Label(frm, text="결과 요약", bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=12).grid(row=1, column=0, sticky="ne", pady=6)
        self.txt_summary = tk.Text(frm, height=3, font=FONT, relief="solid", bd=1)
        self.txt_summary.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=6)
        res = self.task.get("result", {})
        self.txt_summary.insert("1.0", res.get("summary", ""))

        # 점수
        tk.Label(frm, text="점수 (1~5)", bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=12).grid(row=2, column=0, sticky="w", pady=6)
        score_row = tk.Frame(frm, bg="white")
        score_row.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=6)
        self._score_btns = []
        for v in range(1, 6):
            btn = tk.Button(score_row, text=f"{v}점\n{self.STARS[v]}",
                            font=("맑은 고딕", 9), relief="flat", bd=1,
                            bg="#F1F5F9", fg="#374151", width=6, height=2,
                            cursor="hand2",
                            command=lambda val=v: self._select_score(val))
            btn.pack(side="left", padx=2)
            self._score_btns.append(btn)
        saved_score = res.get("score") or 0
        if saved_score > 5:
            saved_score = round(saved_score / 20)
        if saved_score:
            self._select_score(saved_score)

        # 피드백
        tk.Label(frm, text="피드백", bg="white", font=FONT_S,
                 fg="#374151", anchor="e", width=12).grid(row=3, column=0, sticky="ne", pady=6)
        self.txt_feedback = tk.Text(frm, height=3, font=FONT, relief="solid", bd=1)
        self.txt_feedback.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=6)
        self.txt_feedback.insert("1.0", res.get("feedback", ""))

    def _select_score(self, val):
        self._score_var.set(val)
        for i, btn in enumerate(self._score_btns, 1):
            btn.config(bg="#2563EB" if i == val else "#F1F5F9",
                       fg="white"   if i == val else "#374151")

    def _ok(self):
        result = {
            "actual_effort": self.v_actual_effort.get().strip(),
            "summary":       self.txt_summary.get("1.0", "end").strip(),
            "score":         int(self._score_var.get()),
            "feedback":      self.txt_feedback.get("1.0", "end").strip(),
        }
        self.destroy()
        self.on_confirm(result)


# ---------------------------------------------------------------------------

class DailyScrumExtractDialog(tk.Toplevel):
    """특정 날짜의 수행 작업을 데일리 스크럼 형식으로 추출."""

    _DOW = ["월", "화", "수", "목", "금", "토", "일"]

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("데일리 스크럼 추출")
        self.geometry("620x520")
        self.minsize(500, 400)
        self.grab_set()
        self.configure(bg="white")
        self._build()
        self._query()

    # ── UI ──────────────────────────────────────────────────

    def _build(self):
        hdr = tk.Frame(self, bg="#1E40AF", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📋 데일리 스크럼 추출", bg="#1E40AF", fg="white",
                 font=("맑은 고딕", 11, "bold")).pack(side="left", padx=14)

        # ── 필터 바 ──
        bar = tk.Frame(self, bg="#F8FAFC", pady=6)
        bar.pack(fill="x", padx=12)

        tk.Label(bar, text="날짜", bg="#F8FAFC", font=FONT_S, fg="#374151").pack(side="left")
        self._date_entry = DateEntry(bar, width=12, font=FONT,
                                     date_pattern="yyyy-mm-dd",
                                     background="#1E40AF", foreground="white",
                                     borderwidth=1)
        self._date_entry.pack(side="left", padx=(4, 12))

        tk.Label(bar, text="담당자", bg="#F8FAFC", font=FONT_S, fg="#374151").pack(side="left")
        data = load_data()
        assignees = sorted({t.get("assignee", "") for t in data["tasks"] if t.get("assignee")})
        self._v_assignee = tk.StringVar(value="전체")
        ttk.Combobox(bar, textvariable=self._v_assignee,
                     values=["전체"] + assignees,
                     state="readonly", width=10, font=FONT).pack(side="left", padx=(4, 12))

        tk.Button(bar, text="조회", bg="#2563EB", fg="white",
                  font=FONT_S, relief="flat", cursor="hand2", padx=10, pady=3,
                  command=self._query).pack(side="left")

        tk.Button(bar, text="📋 복사", bg="#F1F5F9", fg="#374151",
                  font=FONT_S, relief="flat", cursor="hand2", padx=10, pady=3,
                  command=self._copy).pack(side="right")

        # ── 출력 영역 ──
        out_frm = tk.Frame(self, bg="white")
        out_frm.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        sb = ttk.Scrollbar(out_frm)
        self._txt = tk.Text(out_frm, font=("맑은 고딕", 9), wrap="word",
                            relief="solid", bd=1, yscrollcommand=sb.set,
                            bg="#FAFAFA", state="disabled")
        sb.config(command=self._txt.yview)
        sb.pack(side="right", fill="y")
        self._txt.pack(side="left", fill="both", expand=True)

        # 태그 색상
        self._txt.tag_configure("title",   font=("맑은 고딕", 11, "bold"), foreground="#1E40AF")
        self._txt.tag_configure("sep",     foreground="#94A3B8")
        self._txt.tag_configure("project", font=("맑은 고딕", 9, "bold"),  foreground="#7C3AED")
        self._txt.tag_configure("task",    font=("맑은 고딕", 9, "bold"),  foreground="#1E293B")
        self._txt.tag_configure("meta",    foreground="#475569")
        self._txt.tag_configure("memo",    foreground="#64748B")
        self._txt.tag_configure("done",    foreground="#16A34A")
        self._txt.tag_configure("inprog",  foreground="#2563EB")

    # ── 조회 & 렌더 ─────────────────────────────────────────

    def _query(self):
        try:
            target = date.fromisoformat(self._date_entry.get_date().isoformat())
        except Exception:
            target = date.today()

        assignee_filter = self._v_assignee.get()
        data  = load_data()
        tasks = [t for t in data["tasks"] if _is_date_task(t, target)]
        if assignee_filter != "전체":
            tasks = [t for t in tasks if t.get("assignee") == assignee_filter]

        tasks.sort(key=lambda t: (t.get("seq_order") or 9999,
                                  t.get("scheduled_at") or ""))

        self._render(target, tasks)

    def _render(self, target: date, tasks):
        dow  = self._DOW[target.weekday()]
        sep  = "━" * 44

        self._txt.config(state="normal")
        self._txt.delete("1.0", "end")

        # 제목
        self._txt.insert("end", f"📅 {target.isoformat()} ({dow}) 데일리 스크럼\n", "title")
        self._txt.insert("end", sep + "\n\n", "sep")

        if not tasks:
            self._txt.insert("end", "  해당 날짜에 작업이 없습니다.\n", "meta")
        else:
            # 과제별 그룹핑
            groups: dict = {}
            for t in tasks:
                proj = t.get("project") or t.get("system") or "(미지정)"
                groups.setdefault(proj, []).append(t)

            for proj, grp in groups.items():
                self._txt.insert("end", f"[{proj}]\n", "project")
                for t in grp:
                    status    = t["status"]
                    status_tag = "done" if status == "완료" else ("inprog" if status == "진행중" else "meta")
                    self._txt.insert("end", f"  ■ {t['title']}", "task")
                    self._txt.insert("end", f"  ({status})\n", status_tag)

                    # 메타 정보
                    effort     = t.get("effort", "") or ""
                    act_effort = t.get("actual_effort", "") or ""
                    sch        = fmt_dt_short(t.get("scheduled_at", ""))
                    dl         = fmt_dt_short(t.get("deadline", ""))
                    meta_parts = []
                    if effort:     meta_parts.append(f"예상 {effort}")
                    if act_effort: meta_parts.append(f"실투입 {act_effort}")
                    if sch or dl:  meta_parts.append(f"{sch} → {dl}")
                    if meta_parts:
                        self._txt.insert("end", f"    {' | '.join(meta_parts)}\n", "meta")

                    # 메모
                    memos = t.get("memos", [])
                    if memos:
                        self._txt.insert("end", "    메모:\n", "meta")
                        for m in memos:
                            content = m.get("content", "").strip().replace("\n", "\n       ")
                            self._txt.insert("end", f"      • {content}\n", "memo")

                    self._txt.insert("end", "\n")
                self._txt.insert("end", sep + "\n\n", "sep")

        self._txt.config(state="disabled")

    def _copy(self):
        content = self._txt.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("복사 완료", "클립보드에 복사됐습니다.", parent=self)


class SequenceManagerDialog(tk.Toplevel):
    """
    왼쪽: 순서 미지정 작업 목록
    오른쪽: 순서 지정된 작업 (드래그 또는 ↑↓ 버튼으로 재정렬)
    저장 시 seq_order 갱신
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("작업 순서 관리")
        self.geometry("720x500")
        self.minsize(600, 400)
        self.grab_set()
        self.configure(bg="white")

        data = load_data()
        tasks = [t for t in data["tasks"]
                 if t["status"] not in ("완료", "취소")]

        # 순서 있는 것 / 없는 것 분리
        ordered   = sorted([t for t in tasks if t.get("seq_order") is not None],
                           key=lambda t: t["seq_order"])
        unordered = [t for t in tasks if t.get("seq_order") is None]

        self._unordered_tasks = unordered   # 원본 리스트 (순서 변경 없음)
        self._ordered_tasks   = ordered     # 순서 편집 리스트

        self._drag_start = None

        self._build()
        self._reload_lists()

    # ── UI 구성 ────────────────────────────────────────────

    def _build(self):
        # 헤더
        hdr = tk.Frame(self, bg="#1E40AF", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⟺  작업 순서 관리", bg="#1E40AF", fg="white",
                 font=("맑은 고딕", 11, "bold")).pack(side="left", padx=14)
        tk.Label(hdr, text="더블클릭으로 추가/제거  |  ↑↓ 버튼 또는 드래그로 재정렬",
                 bg="#1E40AF", fg="#BFDBFE", font=FONT_S).pack(side="left", padx=6)

        # 본문 (좌 / 중간 버튼 / 우)
        body = tk.Frame(self, bg="white")
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(2, weight=1)

        # ── 왼쪽: 미지정 ──
        tk.Label(body, text="순서 미지정", bg="white", font=FONT_B,
                 fg="#64748B").grid(row=0, column=0, sticky="w", pady=(0, 4))

        left_frm = tk.Frame(body, bg="white")
        left_frm.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(1, weight=1)

        sb_l = ttk.Scrollbar(left_frm)
        self._lb_unordered = tk.Listbox(
            left_frm, font=FONT_S, selectbackground="#DBEAFE",
            selectforeground="#1E40AF", activestyle="none",
            relief="solid", bd=1, yscrollcommand=sb_l.set)
        sb_l.config(command=self._lb_unordered.yview)
        self._lb_unordered.pack(side="left", fill="both", expand=True)
        sb_l.pack(side="right", fill="y")
        self._lb_unordered.bind("<Double-1>", lambda e: self._add_selected())

        # ── 가운데 버튼 ──
        mid = tk.Frame(body, bg="white")
        mid.grid(row=1, column=1, padx=10, sticky="ns")
        mid.rowconfigure(0, weight=1)
        btn_area = tk.Frame(mid, bg="white")
        btn_area.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Button(btn_area, text="→ 추가", width=8,
                   command=self._add_selected).pack(pady=4)
        ttk.Button(btn_area, text="← 제거", width=8,
                   command=self._remove_selected).pack(pady=4)

        # ── 오른쪽: 순서 목록 ──
        tk.Label(body, text="순서 지정됨", bg="white", font=FONT_B,
                 fg="#1E40AF").grid(row=0, column=2, sticky="w", pady=(0, 4))

        right_frm = tk.Frame(body, bg="white")
        right_frm.grid(row=1, column=2, sticky="nsew")

        # 오른쪽 내부: 리스트 + ↑↓ 버튼
        right_frm.columnconfigure(0, weight=1)
        sb_r = ttk.Scrollbar(right_frm)
        self._lb_ordered = tk.Listbox(
            right_frm, font=FONT_S, selectbackground="#DBEAFE",
            selectforeground="#1E40AF", activestyle="none",
            relief="solid", bd=1, yscrollcommand=sb_r.set)
        sb_r.config(command=self._lb_ordered.yview)
        self._lb_ordered.grid(row=0, column=0, sticky="nsew")
        sb_r.grid(row=0, column=1, sticky="ns")
        right_frm.rowconfigure(0, weight=1)

        ud_frm = tk.Frame(right_frm, bg="white")
        ud_frm.grid(row=1, column=0, columnspan=2, pady=4, sticky="e")
        ttk.Button(ud_frm, text="↑ 위로", width=7,
                   command=self._move_up).pack(side="left", padx=2)
        ttk.Button(ud_frm, text="↓ 아래로", width=8,
                   command=self._move_down).pack(side="left", padx=2)
        ttk.Button(ud_frm, text="← 제거", width=7,
                   command=self._remove_selected).pack(side="left", padx=2)

        self._lb_ordered.bind("<Double-1>", lambda e: self._remove_selected())

        # 드래그 지원
        self._lb_ordered.bind("<Button-1>",       self._drag_start_evt)
        self._lb_ordered.bind("<B1-Motion>",       self._drag_motion_evt)
        self._lb_ordered.bind("<ButtonRelease-1>", self._drag_end_evt)

        # 하단 버튼
        btn_frm = tk.Frame(self, bg="white")
        btn_frm.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(btn_frm, text="저장", command=self._save).pack(side="right")
        ttk.Button(btn_frm, text="취소", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btn_frm, text="순서 전체 해제",
                   command=self._clear_all).pack(side="left")

    # ── 리스트 갱신 ────────────────────────────────────────

    def _task_label(self, task, idx=None):
        prefix = f"{'①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'[idx-1] if idx and 1 <= idx <= 20 else str(idx) + '.' if idx else ''}"
        dl = f"  마감: {fmt_dt(task.get('deadline'))}" if task.get("deadline") else ""
        return f"{prefix}  {task['title']}  [{task.get('system','') or task.get('project','')}]{dl}"

    def _reload_lists(self):
        self._lb_unordered.delete(0, "end")
        for t in self._unordered_tasks:
            self._lb_unordered.insert("end", f"  {t['title']}  [{t.get('system','') or t.get('project','')}]  {t['priority']}")

        self._lb_ordered.delete(0, "end")
        for i, t in enumerate(self._ordered_tasks, 1):
            self._lb_ordered.insert("end", self._task_label(t, i))

    # ── 동작 ───────────────────────────────────────────────

    def _add_selected(self):
        sel = self._lb_unordered.curselection()
        if not sel:
            return
        idx = sel[0]
        task = self._unordered_tasks.pop(idx)
        self._ordered_tasks.append(task)
        self._reload_lists()
        # 방금 추가된 항목 선택
        new_idx = len(self._ordered_tasks) - 1
        self._lb_ordered.selection_clear(0, "end")
        self._lb_ordered.selection_set(new_idx)
        self._lb_ordered.see(new_idx)

    def _remove_selected(self):
        sel = self._lb_ordered.curselection()
        if not sel:
            return
        idx = sel[0]
        task = self._ordered_tasks.pop(idx)
        self._unordered_tasks.append(task)
        self._reload_lists()

    def _move_up(self):
        sel = self._lb_ordered.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self._ordered_tasks[i-1], self._ordered_tasks[i] = \
            self._ordered_tasks[i], self._ordered_tasks[i-1]
        self._reload_lists()
        self._lb_ordered.selection_set(i - 1)

    def _move_down(self):
        sel = self._lb_ordered.curselection()
        if not sel or sel[0] >= len(self._ordered_tasks) - 1:
            return
        i = sel[0]
        self._ordered_tasks[i], self._ordered_tasks[i+1] = \
            self._ordered_tasks[i+1], self._ordered_tasks[i]
        self._reload_lists()
        self._lb_ordered.selection_set(i + 1)

    def _clear_all(self):
        self._unordered_tasks.extend(self._ordered_tasks)
        self._ordered_tasks.clear()
        self._reload_lists()

    # ── 드래그 ─────────────────────────────────────────────

    def _drag_start_evt(self, event):
        self._drag_start = self._lb_ordered.nearest(event.y)

    def _drag_motion_evt(self, event):
        if self._drag_start is None:
            return
        cur = self._lb_ordered.nearest(event.y)
        if cur == self._drag_start or cur < 0:
            return
        self._ordered_tasks[self._drag_start], self._ordered_tasks[cur] = \
            self._ordered_tasks[cur], self._ordered_tasks[self._drag_start]
        self._drag_start = cur
        self._reload_lists()
        self._lb_ordered.selection_clear(0, "end")
        self._lb_ordered.selection_set(cur)

    def _drag_end_evt(self, event):
        self._drag_start = None

    # ── 저장 ───────────────────────────────────────────────

    def _save(self):
        ordered_ids   = {t["id"]: i+1 for i, t in enumerate(self._ordered_tasks)}
        unordered_ids = {t["id"] for t in self._unordered_tasks}

        data = load_data()
        for task in data["tasks"]:
            if task["id"] in ordered_ids:
                task["seq_order"] = ordered_ids[task["id"]]
            elif task["id"] in unordered_ids:
                task["seq_order"] = None
        save_data(data)
        self.destroy()          # grab 해제 먼저
        self.app.refresh_list() # 그 다음 목록 갱신


# ---------------------------------------------------------------------------
# 메인 앱
# ---------------------------------------------------------------------------

class TaskManagerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("작업 관리")
        self.root.geometry("920x600")
        self.root.minsize(700, 480)
        self.root.configure(bg="#F8FAFC")
        self._center()
        self._build_ui()
        self._notifier = NotificationManager(self)
        self._notifier.start()
        self._initial_load()

    def _center(self):
        self.root.update_idletasks()
        w, h = 920, 600
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build_ui(self):
        # 헤더
        header = tk.Frame(self.root, bg="#1E40AF", pady=10)
        header.pack(fill="x")
        tk.Label(header, text="🗂 작업 관리", bg="#1E40AF", fg="white",
                 font=("맑은 고딕", 13, "bold")).pack(side="left", padx=16)
        tk.Button(header, text="+ 작업 추가", bg="#3B82F6", fg="white",
                  font=FONT_B, relief="flat", cursor="hand2", padx=10,
                  command=self.add_task).pack(side="right", padx=12)
        tk.Button(header, text="⟺ 순서 관리", bg="#1E40AF", fg="#BFDBFE",
                  font=FONT_S, relief="flat", cursor="hand2", padx=8,
                  activebackground="#1D4ED8", activeforeground="white",
                  command=self.open_sequence_manager).pack(side="right", padx=4)
        tk.Button(header, text="📊 공수 리포트", bg="#1E40AF", fg="#BFDBFE",
                  font=FONT_S, relief="flat", cursor="hand2", padx=8,
                  activebackground="#1D4ED8", activeforeground="white",
                  command=self.open_effort_report).pack(side="right", padx=4)
        tk.Button(header, text="📋 스크럼 추출", bg="#1E40AF", fg="#BFDBFE",
                  font=FONT_S, relief="flat", cursor="hand2", padx=8,
                  activebackground="#1D4ED8", activeforeground="white",
                  command=self.open_scrum_extract).pack(side="right", padx=4)

        # 좌우 분할
        pane = tk.PanedWindow(self.root, orient="horizontal",
                               sashwidth=5, bg="#E2E8F0")
        pane.pack(fill="both", expand=True)

        self._list_panel = TaskListPanel(pane, self)
        self._detail_panel = TaskDetailPanel(pane, self)
        pane.add(self._list_panel, minsize=300, width=400)
        pane.add(self._detail_panel, minsize=320)

        # 상태바
        self._status_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self._status_var,
                 anchor="w", bg="#E2E8F0", fg="#475569",
                 font=("맑은 고딕", 8), pady=3, padx=8).pack(fill="x", side="bottom")

    # ── 데이터 조작
    def _initial_load(self):
        data = load_data()
        self._list_panel.load(data["tasks"], auto_resize=True)
        self._update_statusbar(data["tasks"])

    def refresh_list(self):
        data = load_data()
        self._list_panel.load(data["tasks"])
        self._update_statusbar(data["tasks"])

    def _update_statusbar(self, tasks):
        total    = len(tasks)
        active   = sum(1 for t in tasks if t["status"] == "진행중")
        urgent   = sum(1 for t in tasks if t["priority"] == "긴급" and t["status"] not in ("완료","취소"))
        now      = datetime.now()
        overdue  = sum(1 for t in tasks
                       if t.get("deadline") and t["status"] not in ("완료","취소")
                       and datetime.fromisoformat(t["deadline"]) < now
                       if True)
        self._status_var.set(
            f"전체 {total}  |  진행중 {active}  |  긴급 {urgent}  |  마감초과 {overdue}")

    def on_task_selected(self, task_id):
        self._detail_panel.load_task(task_id)

    def select_task(self, task_id):
        self._list_panel.select(task_id)
        self._detail_panel.load_task(task_id)

    def open_effort_report(self):
        EffortReportDialog(self.root, self)

    def open_sequence_manager(self):
        SequenceManagerDialog(self.root, self)

    def open_scrum_extract(self):
        DailyScrumExtractDialog(self.root, self)

    def add_task(self):
        TaskEditor(self.root, self, on_save=self.refresh_list)

    def edit_task(self, task_id):
        data = load_data()
        task = get_task(data, task_id)
        if task:
            TaskEditor(self.root, self, task=task,
                       on_save=lambda: [self.refresh_list(),
                                        self._detail_panel.load_task(task_id)])

    def delete_task(self, task_id):
        if not messagebox.askyesno("삭제 확인", "작업을 삭제하시겠습니까?", parent=self.root):
            return
        data = load_data()
        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
        save_data(data)
        self._detail_panel.clear()
        self.refresh_list()

    def set_status(self, task_id, status):
        if status == "완료":
            data = load_data()
            task = get_task(data, task_id)
            if task:
                def _confirm(result):
                    d = load_data()
                    t = get_task(d, task_id)
                    if t:
                        t["status"]        = "완료"
                        t["actual_effort"] = result["actual_effort"]
                        t["result"]        = {
                            "summary":  result["summary"],
                            "score":    result["score"],
                            "feedback": result["feedback"],
                        }
                        t["updated_at"] = now_str()
                        save_data(d)
                    self.refresh_list()
                    self._detail_panel.load_task(task_id)
                CloseTaskDialog(self.root, task, _confirm)
        else:
            data = load_data()
            task = get_task(data, task_id)
            if task:
                task["status"] = status
                task["updated_at"] = now_str()
                save_data(data)
                self.refresh_list()
                self._detail_panel.load_task(task_id)

    def duplicate_task(self, task_id):
        data = load_data()
        src = get_task(data, task_id)
        if src is None:
            return
        import copy
        new_task = copy.deepcopy(src)
        new_task["id"] = data["next_id"]
        data["next_id"] += 1
        new_task["title"] = src["title"] + " (복사)"
        new_task["status"] = "대기"
        new_task["memos"] = []
        new_task["result"] = {"summary": "", "score": None, "feedback": ""}
        new_task["created_at"] = now_str()
        new_task["updated_at"] = now_str()
        data["tasks"].append(new_task)
        save_data(data)
        self.refresh_list()

    def export_task(self, task_id):
        data = load_data()
        task = get_task(data, task_id)
        if task is None:
            return
        lines = [
            f"[작업] {task['title']}",
            f"시스템: {task.get('system','')}  |  종류: {task.get('type','')}  |  담당: {task.get('assignee','')}",
            f"우선순위: {task['priority']}  |  상태: {task['status']}",
            f"예정: {fmt_dt(task.get('scheduled_at'))}  |  마감: {fmt_dt(task.get('deadline'))}",
            "",
            task.get("description", ""),
            "",
        ]
        if task.get("memos"):
            lines.append("─ 메모 ─")
            for m in task["memos"]:
                lines.append(f"[{fmt_dt(m['ts'])}] {m['content']}")
        text = "\n".join(lines)

        # ctypes 클립보드
        import ctypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        k32 = ctypes.windll.kernel32
        u32 = ctypes.windll.user32
        k32.GlobalAlloc.restype       = ctypes.c_void_p
        k32.GlobalAlloc.argtypes      = [ctypes.c_uint, ctypes.c_size_t]
        k32.GlobalLock.restype        = ctypes.c_void_p
        k32.GlobalLock.argtypes       = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes     = [ctypes.c_void_p]
        u32.SetClipboardData.restype  = ctypes.c_void_p
        u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        tb = text.encode("utf-16-le") + b"\x00\x00"
        if u32.OpenClipboard(None):
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(GMEM_MOVEABLE, len(tb))
            p = k32.GlobalLock(h)
            ctypes.memmove(p, tb, len(tb))
            k32.GlobalUnlock(h)
            u32.SetClipboardData(CF_UNICODETEXT, h)
            u32.CloseClipboard()
        messagebox.showinfo("내보내기", "작업 정보가 클립보드에 복사됐습니다.", parent=self.root)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    TaskManagerApp().run()
