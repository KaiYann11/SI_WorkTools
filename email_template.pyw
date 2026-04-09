import tkinter as tk
from tkinter import ttk, messagebox
import calendar
import datetime
import json
import os
import re
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "email_templates.json")

DEFAULT_CATEGORIES = ["업무요청", "보고", "인사", "회의", "공지", "기타"]


_WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _fmt_date(d):
    """날짜를 '3/27(금)' 형식으로 반환."""
    return f"{d.month}/{d.day}({_WEEKDAYS_KR[d.weekday()]})"


def _calc_weekday(target_weekday, advance_weeks=0):
    """이번 주 월요일 기준으로 target_weekday(0=월~6=일) 요일 날짜 반환."""
    today = datetime.date.today()
    this_monday = today - datetime.timedelta(days=today.weekday())
    return _fmt_date(this_monday + datetime.timedelta(days=target_weekday + 7 * advance_weeks))


DATE_ALIASES = {
    "오늘":          lambda: _fmt_date(datetime.date.today()),
    "내일":          lambda: _fmt_date(datetime.date.today() + datetime.timedelta(days=1)),
    "모레":          lambda: _fmt_date(datetime.date.today() + datetime.timedelta(days=2)),
    "이번주금요일":  lambda: _calc_weekday(4),
    "다음주월요일":  lambda: _calc_weekday(0, advance_weeks=1),
}


class PlaceholderText(tk.Text):
    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self._placeholder_on = False
        self._show_placeholder()
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _show_placeholder(self):
        if not self.get("1.0", tk.END).strip():
            self._placeholder_on = True
            self.insert("1.0", self.placeholder)
            self.config(foreground="gray")

    def _on_focus_in(self, event=None):
        if self._placeholder_on:
            self.delete("1.0", tk.END)
            self.config(foreground="black")
            self._placeholder_on = False

    def _on_focus_out(self, event=None):
        if not self.get("1.0", tk.END).strip():
            self._show_placeholder()

    def get_real_text(self):
        return "" if self._placeholder_on else self.get("1.0", tk.END).strip()


class DatePickerDialog:
    """달력 팝업. wait() 호출 시 선택된 "YYYY-MM-DD" 반환, 취소 시 None."""

    WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]
    WEEKDAY_COLORS = ["black"] * 5 + ["#1565C0", "#C62828"]

    def __init__(self, parent_win, initial_date=None):
        if initial_date:
            try:
                self._sel = datetime.date.fromisoformat(initial_date)
            except ValueError:
                self._sel = datetime.date.today()
        else:
            self._sel = datetime.date.today()
        self._year = self._sel.year
        self._month = self._sel.month
        self._result = None

        self.win = tk.Toplevel(parent_win)
        self.win.title("날짜 선택")
        self.win.resizable(False, False)
        self.win.transient(parent_win)

        self._header_var = tk.StringVar()
        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self.win, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        # 헤더: ◀ 년월 ▶
        hdr = ttk.Frame(outer)
        hdr.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(hdr, text="◀", width=3, command=self._prev_month).pack(side=tk.LEFT)
        ttk.Label(hdr, textvariable=self._header_var,
                  font=("맑은 고딕", 11, "bold"), anchor=tk.CENTER).pack(
            side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(hdr, text="▶", width=3, command=self._next_month).pack(side=tk.RIGHT)

        # 요일 헤더
        wday_frame = ttk.Frame(outer)
        wday_frame.pack()
        for col, (label, color) in enumerate(zip(self.WEEKDAY_LABELS, self.WEEKDAY_COLORS)):
            tk.Label(wday_frame, text=label, width=4, anchor=tk.CENTER,
                     font=("맑은 고딕", 9, "bold"), fg=color).grid(row=0, column=col)

        # 날짜 그리드 컨테이너
        self._day_container = ttk.Frame(outer)
        self._day_container.pack()

        # 하단 버튼
        btn = ttk.Frame(outer)
        btn.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btn, text="오늘",
                   command=lambda: self._select(datetime.date.today())).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(btn, text="취소", command=self._cancel).pack(
            side=tk.LEFT, expand=True, fill=tk.X)

        self._rebuild_days()

    def _rebuild_days(self):
        self._header_var.set(f"{self._year}년 {self._month:02d}월")
        for w in self._day_container.winfo_children():
            w.destroy()

        today = datetime.date.today()
        first_weekday, num_days = calendar.monthrange(self._year, self._month)
        # first_weekday: 0=월 ~ 6=일

        row, col = 0, first_weekday
        for day in range(1, num_days + 1):
            d = datetime.date(self._year, self._month, day)
            is_today = (d == today)
            is_sel = (d == self._sel)

            if is_sel:
                bg, fg = "#4A90D9", "white"
            elif is_today:
                bg, fg = "#FFF9C4", "black"
            else:
                bg, fg = "#F5F5F5", self.WEEKDAY_COLORS[col]

            tk.Button(
                self._day_container, text=str(day), width=3,
                font=("맑은 고딕", 9), fg=fg, bg=bg,
                relief=tk.FLAT, bd=1, activebackground="#90CAF9",
                command=lambda d=d: self._select(d)
            ).grid(row=row, column=col, padx=1, pady=1)

            col += 1
            if col == 7:
                col = 0
                row += 1

    def _prev_month(self):
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self._rebuild_days()

    def _next_month(self):
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self._rebuild_days()

    def _select(self, date):
        self._result = _fmt_date(date)
        self.win.destroy()

    def _cancel(self):
        self._result = None
        self.win.destroy()

    def wait(self):
        self.win.grab_set()
        self.win.wait_window(self.win)
        return self._result


class VariableSubstDialog:
    def __init__(self, parent_app, to, cc, subject, body, variables):
        self.parent_app = parent_app
        self.root = parent_app.root
        self.to = to
        self.cc = cc
        self.subject = subject
        self.body = body

        self.win = tk.Toplevel(self.root)
        self.win.title("변수 입력 및 미리보기")
        self.win.geometry("620x680")
        self.win.resizable(True, True)
        self.win.grab_set()

        self.var_entries = {}

        if variables:
            input_frame = tk.LabelFrame(
                self.win, text="변수 입력",
                font=("맑은 고딕", 10, "bold"), padx=10, pady=8
            )
            input_frame.pack(fill=tk.X, padx=10, pady=10)

            for var_name in variables:
                row = ttk.Frame(input_frame)
                row.pack(fill=tk.X, pady=3)
                ttk.Label(row, text=f"{{{{{var_name}}}}}", width=20, anchor=tk.W,
                          font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT)
                sv = tk.StringVar()
                self.var_entries[var_name] = sv

                if var_name in DATE_ALIASES:
                    # 자동 날짜 별칭 — 미리 채워진 읽기 전용
                    sv.set(DATE_ALIASES[var_name]())
                    ttk.Entry(row, textvariable=sv, state="readonly",
                              font=("맑은 고딕", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)
                    ttk.Label(row, text="(자동)", foreground="#2E7D32",
                              font=("맑은 고딕", 9, "bold")).pack(side=tk.LEFT, padx=4)

                elif "날짜" in var_name or "date" in var_name.lower():
                    # 날짜 타입 — 직접 입력 + 캘린더 버튼
                    sv.trace_add("write", lambda *_: self._update_preview())
                    ttk.Entry(row, textvariable=sv, font=("맑은 고딕", 10)).pack(
                        side=tk.LEFT, fill=tk.X, expand=True)

                    def _open_picker(sv=sv):
                        dlg = DatePickerDialog(self.win, initial_date=sv.get() or None)
                        result = dlg.wait()
                        if result:
                            sv.set(result)

                    ttk.Button(row, text="📅", width=3,
                               command=_open_picker).pack(side=tk.LEFT, padx=(3, 0))

                else:
                    # 일반 변수
                    sv.trace_add("write", lambda *_: self._update_preview())
                    ttk.Entry(row, textvariable=sv, font=("맑은 고딕", 10)).pack(
                        side=tk.LEFT, fill=tk.X, expand=True)
        else:
            ttk.Label(self.win, text="이 템플릿에는 변수가 없습니다.",
                      font=("맑은 고딕", 10), foreground="gray").pack(padx=10, pady=10, anchor=tk.W)

        ttk.Label(self.win, text="미리보기",
                  font=("맑은 고딕", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(5, 2))

        preview_frame = ttk.Frame(self.win)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        sb = ttk.Scrollbar(preview_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text = tk.Text(
            preview_frame, font=("맑은 고딕", 10), wrap=tk.WORD,
            state=tk.DISABLED, yscrollcommand=sb.set
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.preview_text.yview)

        btn_frame = ttk.Frame(self.win)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="📋 복사", command=self._copy).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(btn_frame, text="닫기", command=self.win.destroy).pack(
            side=tk.LEFT, expand=True, fill=tk.X)

        self._update_preview()

    def _substitute(self, text):
        result = text
        for var_name, sv in self.var_entries.items():
            result = result.replace(f"{{{{{var_name}}}}}", sv.get())
        return result

    def _build_content(self):
        lines = []
        to = self._substitute(self.to)
        cc = self._substitute(self.cc)
        subj = self._substitute(self.subject)
        body = self._substitute(self.body)
        if to:
            lines.append(f"수신자: {to}")
        if cc:
            lines.append(f"참조: {cc}")
        if subj:
            lines.append(f"제목: {subj}")
        if lines:
            lines.append("")
        lines.append(body)
        return "\n".join(lines)

    def _update_preview(self):
        content = self._build_content()
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", content)
        self.preview_text.config(state=tk.DISABLED)

    def _copy(self):
        content = self._build_content()
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.parent_app._set_status("✅ 클립보드에 복사되었습니다!")
        self.win.destroy()


class CategoryManagerDialog:
    def __init__(self, parent_app):
        self.parent_app = parent_app

        self.win = tk.Toplevel(parent_app.root)
        self.win.title("카테고리 관리")
        self.win.geometry("300x420")
        self.win.resizable(False, True)
        self.win.grab_set()

        ttk.Label(self.win, text="카테고리 목록",
                  font=("맑은 고딕", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))

        list_frame = ttk.Frame(self.win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        sb = ttk.Scrollbar(list_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox = tk.Listbox(list_frame, font=("맑은 고딕", 10), yscrollcommand=sb.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.listbox.yview)

        add_frame = ttk.Frame(self.win)
        add_frame.pack(fill=tk.X, padx=10, pady=8)
        self.new_cat_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.new_cat_var,
                  font=("맑은 고딕", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(add_frame, text="추가", command=self._add_category).pack(side=tk.LEFT)

        ttk.Button(self.win, text="🗑 선택 삭제", command=self._delete_category).pack(
            fill=tk.X, padx=10, pady=(0, 10))

        self._refresh_listbox()

    def _refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for cat in self.parent_app.data["categories"]:
            self.listbox.insert(tk.END, cat)

    def _add_category(self):
        name = self.new_cat_var.get().strip()
        if not name:
            messagebox.showwarning("입력 오류", "카테고리 이름을 입력하세요.", parent=self.win)
            return
        if name in self.parent_app.data["categories"]:
            messagebox.showwarning("중복", f"'{name}' 카테고리가 이미 존재합니다.", parent=self.win)
            return
        self.parent_app.data["categories"].append(name)
        self.parent_app._save_data()
        self.parent_app._refresh_category_listbox()
        self.parent_app._refresh_category_combo()
        self.new_cat_var.set("")
        self._refresh_listbox()

    def _delete_category(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("선택 없음", "삭제할 카테고리를 선택하세요.", parent=self.win)
            return
        cat = self.listbox.get(sel[0])
        in_use = [t["name"] for t in self.parent_app.data["templates"]
                  if t["category"] == cat]
        if in_use:
            names = ", ".join(in_use[:3])
            extra = "..." if len(in_use) > 3 else ""
            messagebox.showwarning(
                "삭제 불가",
                f"이 카테고리를 사용 중인 템플릿이 있습니다:\n{names}{extra}",
                parent=self.win
            )
            return
        if not messagebox.askyesno("삭제 확인", f"'{cat}' 카테고리를 삭제하시겠습니까?", parent=self.win):
            return
        self.parent_app.data["categories"].remove(cat)
        self.parent_app._save_data()
        self.parent_app._refresh_category_listbox()
        self.parent_app._refresh_category_combo()
        self._refresh_listbox()


class EmailTemplateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("회사 이메일 템플릿 관리")
        self.root.geometry("870x750")
        self.root.resizable(True, True)

        self.current_id = None
        self._listbox_ids = []
        self._last_focused = "body"
        self.status_var = tk.StringVar(value="")

        style = ttk.Style()
        style.configure("Header.TLabel", font=("맑은 고딕", 14, "bold"))
        style.configure("Section.TLabel", font=("맑은 고딕", 10, "bold"))
        style.configure("TButton", font=("맑은 고딕", 10))
        style.configure("TLabel", font=("맑은 고딕", 10))
        style.configure("TEntry", font=("맑은 고딕", 10))
        style.configure("TCombobox", font=("맑은 고딕", 10))

        self.data = self._load_data()

        header = ttk.Label(root, text="📧 회사 이메일 템플릿 관리", style="Header.TLabel")
        header.pack(anchor=tk.W, padx=15, pady=(10, 5))

        paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left_frame = ttk.Frame(paned, width=210)
        left_frame.pack_propagate(False)
        paned.add(left_frame, weight=0)

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        self._build_left_panel(left_frame)
        self._build_right_panel(right_frame)

        self._refresh_category_listbox()
        self._refresh_template_listbox()
        self._refresh_category_combo()
        self._select_first_template()

    # ── Data layer ────────────────────────────────────────────────────────────

    def _load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "categories" not in data:
                    data["categories"] = list(DEFAULT_CATEGORIES)
                if "templates" not in data:
                    data["templates"] = []
                return data
            except Exception:
                pass
        return {"templates": [], "categories": list(DEFAULT_CATEGORIES)}

    def _save_data(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("저장 오류", f"파일 저장 실패:\n{e}")

    def _detect_variables(self, text):
        found = re.findall(r'\{\{(\w+)\}\}', text)
        seen = set()
        result = []
        for v in found:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result

    def _generate_id(self):
        return uuid.uuid4().hex[:8]

    def _get_template_by_id(self, tid):
        for t in self.data["templates"]:
            if t["id"] == tid:
                return t
        return None

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        cat_frame = tk.LabelFrame(parent, text="카테고리",
                                  font=("맑은 고딕", 10, "bold"), padx=5, pady=5)
        cat_frame.pack(fill=tk.X, padx=5, pady=(5, 3))

        cat_lb_frame = ttk.Frame(cat_frame)
        cat_lb_frame.pack(fill=tk.X)
        cat_sb = ttk.Scrollbar(cat_lb_frame, orient=tk.VERTICAL)
        cat_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.category_listbox = tk.Listbox(
            cat_lb_frame, font=("맑은 고딕", 10), height=7,
            yscrollcommand=cat_sb.set, activestyle="dotbox",
            selectbackground="#4A90D9", selectforeground="white"
        )
        self.category_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cat_sb.config(command=self.category_listbox.yview)
        self.category_listbox.bind("<<ListboxSelect>>", self._on_category_select)

        tpl_frame = tk.LabelFrame(parent, text="템플릿 목록",
                                  font=("맑은 고딕", 10, "bold"), padx=5, pady=5)
        tpl_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        tpl_lb_frame = ttk.Frame(tpl_frame)
        tpl_lb_frame.pack(fill=tk.BOTH, expand=True)
        tpl_sb = ttk.Scrollbar(tpl_lb_frame, orient=tk.VERTICAL)
        tpl_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.template_listbox = tk.Listbox(
            tpl_lb_frame, font=("맑은 고딕", 10),
            yscrollcommand=tpl_sb.set, activestyle="dotbox",
            selectbackground="#4A90D9", selectforeground="white"
        )
        self.template_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tpl_sb.config(command=self.template_listbox.yview)
        self.template_listbox.bind("<<ListboxSelect>>", self._on_template_select)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="+ 새 템플릿", command=self._new_template).pack(
            fill=tk.X, pady=(0, 3))
        ttk.Button(btn_frame, text="카테고리 관리", command=self._open_category_manager).pack(
            fill=tk.X)

    def _build_right_panel(self, parent):
        meta_frame = ttk.Frame(parent)
        meta_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        name_row = ttk.Frame(meta_frame)
        name_row.pack(fill=tk.X, pady=2)
        ttk.Label(name_row, text="이름:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_row, textvariable=self.name_var,
                                    font=("맑은 고딕", 10))
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        cat_row = ttk.Frame(meta_frame)
        cat_row.pack(fill=tk.X, pady=2)
        ttk.Label(cat_row, text="카테고리:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(
            cat_row, textvariable=self.category_var,
            font=("맑은 고딕", 10), state="readonly"
        )
        self.category_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        to_row = ttk.Frame(meta_frame)
        to_row.pack(fill=tk.X, pady=2)
        ttk.Label(to_row, text="수신자:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        self.to_var = tk.StringVar()
        ttk.Entry(to_row, textvariable=self.to_var,
                  font=("맑은 고딕", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.to_var.trace_add("write", lambda *_: self._refresh_vars_label())

        cc_row = ttk.Frame(meta_frame)
        cc_row.pack(fill=tk.X, pady=2)
        ttk.Label(cc_row, text="참조:", width=8, anchor=tk.W).pack(side=tk.LEFT)
        self.cc_var = tk.StringVar()
        ttk.Entry(cc_row, textvariable=self.cc_var,
                  font=("맑은 고딕", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cc_var.trace_add("write", lambda *_: self._refresh_vars_label())

        subj_frame = tk.LabelFrame(parent, text="제목",
                                   font=("맑은 고딕", 10, "bold"), padx=8, pady=5)
        subj_frame.pack(fill=tk.X, padx=10, pady=3)
        self.subject_var = tk.StringVar()
        self.subject_entry = ttk.Entry(subj_frame, textvariable=self.subject_var,
                                       font=("맑은 고딕", 10))
        self.subject_entry.pack(fill=tk.X)
        self.subject_var.trace_add("write", lambda *_: self._refresh_vars_label())
        self.subject_entry.bind("<FocusIn>",
                                lambda e: setattr(self, "_last_focused", "subject"))

        # 날짜 삽입 툴바
        self._build_date_toolbar(parent)

        body_frame = tk.LabelFrame(parent, text="본문",
                                   font=("맑은 고딕", 10, "bold"), padx=8, pady=5)
        # 하단 고정 요소를 먼저 BOTTOM으로 배치 → body가 남은 공간을 채움
        ttk.Label(parent, textvariable=self.status_var,
                  foreground="green", font=("맑은 고딕", 9)).pack(
            side=tk.BOTTOM, anchor=tk.E, padx=12, pady=(0, 4))

        action_frame = ttk.Frame(parent)
        action_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 4))
        ttk.Button(action_frame, text="💾 저장", command=self._save_template).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(action_frame, text="🗑 삭제", command=self._delete_template).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        ttk.Button(action_frame, text="👁 미리보기/복사", command=self._open_preview_dialog).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

        self.vars_label = ttk.Label(parent, text="감지된 변수: 없음",
                                    foreground="gray", font=("맑은 고딕", 9))
        self.vars_label.pack(side=tk.BOTTOM, anchor=tk.W, padx=12, pady=(0, 2))

        # body는 남은 공간 모두 차지
        body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=3)

        body_inner = ttk.Frame(body_frame)
        body_inner.pack(fill=tk.BOTH, expand=True)
        body_sb = ttk.Scrollbar(body_inner)
        body_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.body_text = tk.Text(
            body_inner, font=("맑은 고딕", 10), wrap=tk.WORD,
            yscrollcommand=body_sb.set
        )
        self.body_text.pack(fill=tk.BOTH, expand=True)
        body_sb.config(command=self.body_text.yview)
        self.body_text.bind("<<Modified>>", self._on_body_modified)
        self.body_text.bind("<FocusIn>",
                            lambda e: setattr(self, "_last_focused", "body"))

    # ── Refresh methods ───────────────────────────────────────────────────────

    def _refresh_category_listbox(self):
        self.category_listbox.delete(0, tk.END)
        self.category_listbox.insert(tk.END, "전체")
        for cat in self.data["categories"]:
            self.category_listbox.insert(tk.END, cat)
        self.category_listbox.selection_set(0)

    def _refresh_template_listbox(self):
        self.template_listbox.delete(0, tk.END)
        self._listbox_ids = []
        sel = self.category_listbox.curselection()
        selected_cat = self.category_listbox.get(sel[0]) if sel else "전체"
        for t in self.data["templates"]:
            if selected_cat == "전체" or t["category"] == selected_cat:
                self.template_listbox.insert(tk.END, t["name"])
                self._listbox_ids.append(t["id"])

    def _refresh_vars_label(self):
        combined = "\n".join([
            self.to_var.get(), self.cc_var.get(),
            self.subject_var.get(), self.body_text.get("1.0", tk.END)
        ])
        variables = self._detect_variables(combined)
        if variables:
            tags = "  ".join(f"{{{{{v}}}}}" for v in variables)
            self.vars_label.config(text=f"감지된 변수:  {tags}", foreground="#1565C0")
        else:
            self.vars_label.config(text="감지된 변수: 없음", foreground="gray")

    def _refresh_category_combo(self):
        self.category_combo["values"] = self.data["categories"]

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_category_select(self, event=None):
        self._refresh_template_listbox()

    def _on_template_select(self, event=None):
        sel = self.template_listbox.curselection()
        if not sel or sel[0] >= len(self._listbox_ids):
            return
        tid = self._listbox_ids[sel[0]]
        self._load_template_to_editor(tid)

    def _on_body_modified(self, event=None):
        self._refresh_vars_label()
        self.body_text.edit_modified(False)

    # ── Editor load/clear ─────────────────────────────────────────────────────

    def _load_template_to_editor(self, tid):
        t = self._get_template_by_id(tid)
        if not t:
            return
        self.current_id = tid
        self.name_var.set(t.get("name", ""))
        self.category_var.set(t.get("category", ""))
        self.to_var.set(t.get("to", ""))
        self.cc_var.set(t.get("cc", ""))
        self.subject_var.set(t.get("subject", ""))
        self.body_text.delete("1.0", tk.END)
        self.body_text.insert("1.0", t.get("body", ""))
        self.body_text.edit_modified(False)
        self._refresh_vars_label()

    def _clear_editor(self):
        self.current_id = None
        self.name_var.set("")
        self.category_var.set(self.data["categories"][0] if self.data["categories"] else "")
        self.to_var.set("")
        self.cc_var.set("")
        self.subject_var.set("")
        self.body_text.delete("1.0", tk.END)
        self.body_text.edit_modified(False)
        self._refresh_vars_label()

    def _select_first_template(self):
        if self._listbox_ids:
            self.template_listbox.selection_set(0)
            self._load_template_to_editor(self._listbox_ids[0])

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _new_template(self):
        self._clear_editor()
        self.name_entry.focus_set()

    def _save_template(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("입력 오류", "템플릿 이름을 입력하세요.")
            return
        category = self.category_var.get().strip() or "기타"
        to = self.to_var.get().strip()
        cc = self.cc_var.get().strip()
        subject = self.subject_var.get().strip()
        body = self.body_text.get("1.0", tk.END).strip()
        now = datetime.datetime.now().isoformat(timespec="seconds")

        if self.current_id:
            for t in self.data["templates"]:
                if t["id"] == self.current_id:
                    t.update({
                        "name": name, "category": category,
                        "to": to, "cc": cc,
                        "subject": subject, "body": body, "updated_at": now
                    })
                    break
        else:
            new_t = {
                "id": self._generate_id(), "name": name,
                "category": category, "to": to, "cc": cc,
                "subject": subject, "body": body, "created_at": now, "updated_at": now
            }
            self.data["templates"].append(new_t)
            self.current_id = new_t["id"]

        self._save_data()
        self._refresh_template_listbox()

        # Re-select the saved template in the listbox
        if self.current_id in self._listbox_ids:
            idx = self._listbox_ids.index(self.current_id)
            self.template_listbox.selection_clear(0, tk.END)
            self.template_listbox.selection_set(idx)
            self.template_listbox.see(idx)

        self._set_status("✅ 템플릿이 저장되었습니다.")

    def _delete_template(self):
        if not self.current_id:
            messagebox.showwarning("선택 없음", "삭제할 템플릿을 선택하세요.")
            return
        t = self._get_template_by_id(self.current_id)
        name = t["name"] if t else self.current_id
        if not messagebox.askyesno("삭제 확인", f"'{name}' 템플릿을 삭제하시겠습니까?"):
            return
        self.data["templates"] = [
            t for t in self.data["templates"] if t["id"] != self.current_id
        ]
        self._save_data()
        self._clear_editor()
        self._refresh_template_listbox()
        self._set_status("🗑 템플릿이 삭제되었습니다.")

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _open_preview_dialog(self):
        to = self.to_var.get()
        cc = self.cc_var.get()
        subject = self.subject_var.get()
        body = self.body_text.get("1.0", tk.END).strip()
        if not to and not subject and not body:
            messagebox.showwarning("내용 없음", "수신자 또는 제목/본문을 입력하세요.")
            return
        combined = "\n".join([to, cc, subject, body])
        variables = self._detect_variables(combined)
        VariableSubstDialog(self, to, cc, subject, body, variables)

    def _open_category_manager(self):
        CategoryManagerDialog(self)

    # ── Date toolbar ──────────────────────────────────────────────────────────

    def _build_date_toolbar(self, parent):
        tb = ttk.Frame(parent)
        tb.pack(fill=tk.X, padx=10, pady=(2, 0))

        ttk.Label(tb, text="📅", font=("맑은 고딕", 10)).pack(side=tk.LEFT)

        for alias in DATE_ALIASES:
            token = f"{{{{{alias}}}}}"
            ttk.Button(tb, text=token,
                       command=lambda t=token: self._insert_date_token(t)).pack(
                side=tk.LEFT, padx=(2, 0))

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Button(tb, text="📅 직접선택",
                   command=self._pick_and_insert_date).pack(side=tk.LEFT)

    def _insert_date_token(self, token):
        if self._last_focused == "subject":
            self.subject_entry.insert(tk.INSERT, token)
            self.subject_entry.focus_set()
        else:
            self.body_text.insert(tk.INSERT, token)
            self.body_text.focus_set()

    def _pick_and_insert_date(self):
        dlg = DatePickerDialog(self.root)
        result = dlg.wait()
        if result:
            self._insert_date_token(result)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _set_status(self, msg):
        self.status_var.set(msg)
        self.root.after(3000, lambda: self.status_var.set(""))


if __name__ == "__main__":
    root = tk.Tk()
    app = EmailTemplateApp(root)
    root.mainloop()
