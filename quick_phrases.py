import ctypes
import ctypes.wintypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import re
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "quick_phrases.json")

DEFAULT_DATA = {
    "next_id": 2,
    "phrases": [
        {"id": 1, "category": "요청", "template": "[이름] 님 [내용] 요청 드립니다.",
         "favorite": True, "use_count": 0},
    ]
}


# ---------------------------------------------------------------------------
# 클립보드 / 붙여넣기
# ---------------------------------------------------------------------------

def win_copy(text):
    """64비트 Windows에서 ctypes 포인터 restype을 명시해야 함 (미설정 시 32비트로 잘림)."""
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    text_bytes = text.encode("utf-16-le") + b"\x00\x00"

    k32 = ctypes.windll.kernel32
    u32 = ctypes.windll.user32
    k32.GlobalAlloc.restype          = ctypes.c_void_p
    k32.GlobalAlloc.argtypes         = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalLock.restype           = ctypes.c_void_p
    k32.GlobalLock.argtypes          = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes        = [ctypes.c_void_p]
    u32.SetClipboardData.restype     = ctypes.c_void_p
    u32.SetClipboardData.argtypes    = [ctypes.c_uint, ctypes.c_void_p]

    for _ in range(10):          # 다른 앱이 클립보드 점유 중일 때 재시도
        if u32.OpenClipboard(None):
            break
        time.sleep(0.01)
    else:
        return

    u32.EmptyClipboard()
    h = k32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
    p = k32.GlobalLock(h)
    ctypes.memmove(p, text_bytes, len(text_bytes))
    k32.GlobalUnlock(h)
    u32.SetClipboardData(CF_UNICODETEXT, h)
    u32.CloseClipboard()


def send_paste():
    time.sleep(0.3)
    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)       # Ctrl down
    ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)       # V down
    ctypes.windll.user32.keybd_event(0x56, 0, 0x0002, 0)  # V up
    ctypes.windll.user32.keybd_event(0x11, 0, 0x0002, 0)  # Ctrl up


# ---------------------------------------------------------------------------
# 데이터
# ---------------------------------------------------------------------------

def load_data():
    if not os.path.exists(DATA_PATH):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_vars(template):
    seen = set()
    result = []
    for v in re.findall(r'\[([^\]]+)\]', template):
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


def fill_template(template, var_values):
    result = template
    for name, val in var_values.items():
        result = result.replace(f"[{name}]", val)
    return result


# ---------------------------------------------------------------------------
# 문구 관리 창
# ---------------------------------------------------------------------------

class ManageWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("문구 관리")
        self.geometry("560x460")
        self.resizable(True, True)
        self.grab_set()
        self._build()
        self._load_list()

    def _build(self):
        self.configure(bg="white")
        toolbar = tk.Frame(self, bg="#F1F5F9", pady=6)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="+ 추가", command=self._add).pack(side="left", padx=8)
        ttk.Button(toolbar, text="✏ 수정", command=self._edit).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🗑 삭제", command=self._delete).pack(side="left", padx=2)

        cols = ("fav", "category", "template")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("fav", text="★")
        self.tree.heading("category", text="분류")
        self.tree.heading("template", text="문구 템플릿")
        self.tree.column("fav", width=30, anchor="center", stretch=False)
        self.tree.column("category", width=70, anchor="center", stretch=False)
        self.tree.column("template", width=400)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._edit())

    def _load_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        data = load_data()
        phrases = sorted(data["phrases"],
                         key=lambda p: (not p["favorite"], -p["use_count"]))
        for p in phrases:
            fav = "★" if p["favorite"] else ""
            self.tree.insert("", "end", iid=str(p["id"]),
                             values=(fav, p["category"], p["template"]))

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        PhraseEditor(self, on_save=self._on_save)

    def _edit(self):
        pid = self._selected_id()
        if pid is None:
            return
        data = load_data()
        phrase = next((p for p in data["phrases"] if p["id"] == pid), None)
        if phrase:
            PhraseEditor(self, phrase=phrase, on_save=self._on_save)

    def _delete(self):
        pid = self._selected_id()
        if pid is None:
            return
        if not messagebox.askyesno("삭제 확인", "선택한 문구를 삭제하시겠습니까?", parent=self):
            return
        data = load_data()
        data["phrases"] = [p for p in data["phrases"] if p["id"] != pid]
        save_data(data)
        self._on_save()

    def _on_save(self):
        self._load_list()
        self.app.reload_data()


class PhraseEditor(tk.Toplevel):
    CATEGORIES = ["요청", "완료", "안내", "기타"]

    def __init__(self, parent, phrase=None, on_save=None):
        super().__init__(parent)
        self.phrase = phrase
        self.on_save = on_save
        self.title("문구 추가" if phrase is None else "문구 수정")
        self.geometry("420x220")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        self.configure(bg="white")
        pad = {"padx": 16, "pady": 6}

        tk.Label(self, text="분류", bg="white",
                 font=("맑은 고딕", 9)).grid(row=0, column=0, **pad, sticky="w")
        self.cat_var = tk.StringVar(value=self.phrase["category"] if self.phrase else "요청")
        ttk.Combobox(self, textvariable=self.cat_var, values=self.CATEGORIES,
                     state="readonly", width=12).grid(row=0, column=1, **pad, sticky="w")

        tk.Label(self, text="즐겨찾기", bg="white",
                 font=("맑은 고딕", 9)).grid(row=0, column=2, padx=4, pady=6, sticky="w")
        self.fav_var = tk.BooleanVar(value=self.phrase["favorite"] if self.phrase else False)
        ttk.Checkbutton(self, variable=self.fav_var).grid(row=0, column=3, padx=4)

        tk.Label(self, text="템플릿", bg="white",
                 font=("맑은 고딕", 9)).grid(row=1, column=0, **pad, sticky="nw")
        self.tmpl_text = tk.Text(self, height=4, width=36, font=("맑은 고딕", 10),
                                  relief="solid", bd=1)
        self.tmpl_text.grid(row=1, column=1, columnspan=3, **pad, sticky="ew")
        if self.phrase:
            self.tmpl_text.insert("1.0", self.phrase["template"])

        tk.Label(self, text="힌트: [이름], [내용] 등 대괄호로 변수 지정",
                 bg="white", fg="#94A3B8", font=("맑은 고딕", 8)).grid(
            row=2, column=1, columnspan=3, padx=16, sticky="w")

        btn_frm = tk.Frame(self, bg="white")
        btn_frm.grid(row=3, column=0, columnspan=4, pady=12)
        ttk.Button(btn_frm, text="저장", command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_frm, text="취소", command=self.destroy).pack(side="left")
        self.columnconfigure(1, weight=1)

    def _save(self):
        tmpl = self.tmpl_text.get("1.0", "end").strip()
        if not tmpl:
            messagebox.showwarning("입력 오류", "템플릿을 입력하세요.", parent=self)
            return
        data = load_data()
        if self.phrase is None:
            new_phrase = {
                "id": data["next_id"],
                "category": self.cat_var.get(),
                "template": tmpl,
                "favorite": self.fav_var.get(),
                "use_count": 0,
            }
            data["next_id"] += 1
            data["phrases"].append(new_phrase)
        else:
            for p in data["phrases"]:
                if p["id"] == self.phrase["id"]:
                    p["category"] = self.cat_var.get()
                    p["template"] = tmpl
                    p["favorite"] = self.fav_var.get()
                    break
        save_data(data)
        if self.on_save:
            self.on_save()
        self.destroy()


# ---------------------------------------------------------------------------
# 변수 입력 화면
# ---------------------------------------------------------------------------

class FillVarsFrame(tk.Frame):
    def __init__(self, parent, phrase, on_copy, on_back):
        super().__init__(parent, bg="white")
        self.phrase = phrase
        self.on_copy = on_copy
        self.on_back = on_back
        self.var_entries = {}   # name -> tk.Entry widget
        self._build()

    def _build(self):
        tk.Button(self, text="← 뒤로", bg="white", fg="#475569",
                  font=("맑은 고딕", 8), relief="flat", bd=0,
                  cursor="hand2", command=self.on_back).pack(anchor="w", padx=12, pady=(10, 0))

        tmpl = self.phrase["template"]
        tk.Label(self, text=tmpl, bg="#F8FAFC", fg="#1E293B",
                 font=("맑은 고딕", 10), wraplength=340, justify="left",
                 padx=10, pady=8).pack(fill="x", padx=12, pady=6)

        var_names = extract_vars(tmpl)
        entry_frame = tk.Frame(self, bg="white")
        entry_frame.pack(fill="x", padx=12)

        first_entry = None
        for i, name in enumerate(var_names):
            tk.Label(entry_frame, text=name, bg="white",
                     font=("맑은 고딕", 9, "bold"), fg="#374151",
                     width=8, anchor="e").grid(row=i, column=0, pady=4, padx=(0, 6))
            entry = tk.Entry(entry_frame, font=("맑은 고딕", 10), width=24,
                             relief="solid", bd=1)
            entry.grid(row=i, column=1, pady=4, sticky="ew")
            entry.bind("<KeyRelease>", lambda e: self._update_preview())
            entry.bind("<Return>", lambda e: self._do_copy())
            entry.bind("<Escape>", lambda e: self.on_back())
            self.var_entries[name] = entry
            if first_entry is None:
                first_entry = entry
        entry_frame.columnconfigure(1, weight=1)

        # 미리보기
        self.preview_var = tk.StringVar(value=tmpl)
        preview_frm = tk.Frame(self, bg="#EFF6FF", pady=8, padx=10)
        preview_frm.pack(fill="x", padx=12, pady=8)
        tk.Label(preview_frm, text="미리보기", bg="#EFF6FF", fg="#3B82F6",
                 font=("맑은 고딕", 8, "bold")).pack(anchor="w")
        tk.Label(preview_frm, textvariable=self.preview_var,
                 bg="#EFF6FF", fg="#1E293B",
                 font=("맑은 고딕", 10), wraplength=320,
                 justify="left").pack(anchor="w", pady=(2, 0))

        tk.Button(self, text="📋  복사 후 닫기",
                  bg="#2563EB", fg="white",
                  font=("맑은 고딕", 10, "bold"),
                  relief="flat", bd=0, cursor="hand2",
                  pady=8, command=self._do_copy).pack(fill="x", padx=12, pady=(0, 12))

        if first_entry:
            self.after(50, first_entry.focus_set)

    def _update_preview(self):
        vals = {name: entry.get() for name, entry in self.var_entries.items()}
        self.preview_var.set(fill_template(self.phrase["template"], vals))

    def _do_copy(self):
        vals = {name: entry.get() for name, entry in self.var_entries.items()}
        result = fill_template(self.phrase["template"], vals)
        self.on_copy(result, self.phrase)


# ---------------------------------------------------------------------------
# 메인 검색 화면
# ---------------------------------------------------------------------------

class SearchFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="white")
        self.app = app
        self._all_phrases = []
        self._filtered = []
        self._sel_idx = 0
        self._build()

    def _build(self):
        # 검색창 — 포커스를 절대 떠나지 않음
        search_frm = tk.Frame(self, bg="#F1F5F9", pady=8, padx=10)
        search_frm.pack(fill="x")

        self.search_entry = tk.Entry(search_frm, font=("맑은 고딕", 11),
                                      relief="flat", bd=0, bg="#F1F5F9")
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=2)

        # 모든 키 이벤트를 검색창에서 처리
        self.search_entry.bind("<KeyPress>", self._on_keypress)

        tk.Button(search_frm, text="관리", bg="#F1F5F9", fg="#475569",
                  font=("맑은 고딕", 8), relief="flat", bd=0,
                  cursor="hand2", command=self.app.open_manage).pack(side="right")

        tk.Frame(self, bg="#E2E8F0", height=1).pack(fill="x")

        list_frm = tk.Frame(self, bg="white")
        list_frm.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(list_frm, font=("맑은 고딕", 10),
                                   selectmode="single", relief="flat",
                                   activestyle="none",
                                   selectbackground="#DBEAFE",
                                   selectforeground="#1E40AF",
                                   bd=0, highlightthickness=0,
                                   takefocus=0)          # 탭/클릭으로 포커스 안 받음
        sb = ttk.Scrollbar(list_frm, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # 마우스: 단일 클릭은 선택만, 더블클릭은 복사
        self.listbox.bind("<Button-1>", self._on_mouse_click)
        self.listbox.bind("<Double-1>", self._on_mouse_double)

        self.hint_label = tk.Label(self, text="", bg="white", fg="#94A3B8",
                                    font=("맑은 고딕", 8), pady=4)
        self.hint_label.pack(fill="x")

    def load_phrases(self, phrases):
        self._all_phrases = phrases
        self._filter("")

    def _on_keypress(self, event):
        keysym = event.keysym
        if keysym == "Return":
            self._select_current()
            return "break"
        if keysym == "Escape":
            self.app.root.destroy()
            return "break"
        if keysym == "Down":
            self._move_sel(1)
            return "break"
        if keysym == "Up":
            self._move_sel(-1)
            return "break"
        if event.char == "e" and not self.search_entry.get():
            self._edit_current()
            return "break"
        # 일반 문자 입력 — 한 프레임 뒤에 필터링 (Entry가 값을 업데이트한 후)
        self.after(1, lambda: self._filter(self.search_entry.get()))

    def _move_sel(self, delta):
        if not self._filtered:
            return
        self._sel_idx = max(0, min(len(self._filtered) - 1, self._sel_idx + delta))
        self._highlight(self._sel_idx)

    def _highlight(self, idx):
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        self.listbox.see(idx)

    def _filter(self, keyword=""):
        keyword = keyword.strip().lower()
        self.listbox.delete(0, "end")
        self._filtered = []

        sorted_phrases = sorted(
            self._all_phrases,
            key=lambda p: (not p["favorite"], -p["use_count"])
        )
        for p in sorted_phrases:
            if keyword in p["template"].lower() or keyword in p["category"].lower():
                prefix = "★ " if p["favorite"] else "   "
                self.listbox.insert("end", f"{prefix}[{p['category']}] {p['template']}")
                self._filtered.append(p)

        self._sel_idx = 0
        if self._filtered:
            self._highlight(0)

        count = len(self._filtered)
        self.hint_label.config(text=f"{count}개  |  ↑↓ 선택  |  Enter 복사  |  e 수정  |  Esc 닫기")

    def _select_current(self):
        if self._filtered:
            self.app.copy_phrase(self._filtered[self._sel_idx])

    def _on_mouse_click(self, event):
        idx = self.listbox.nearest(event.y)
        if 0 <= idx < len(self._filtered):
            self._sel_idx = idx
            self._highlight(idx)
        self.search_entry.focus_set()
        return "break"

    def _on_mouse_double(self, event):
        idx = self.listbox.nearest(event.y)
        if 0 <= idx < len(self._filtered):
            self._sel_idx = idx
            self.app.copy_phrase(self._filtered[idx])
        return "break"

    def _edit_current(self):
        if not self._filtered:
            return
        phrase = self._filtered[self._sel_idx]
        PhraseEditor(self.app.root, phrase=phrase, on_save=lambda: self.app.reload_data())


# ---------------------------------------------------------------------------
# 메인 앱
# ---------------------------------------------------------------------------

class QuickPhrasesApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("빠른 문구")
        self.root.geometry("400x320")
        self.root.resizable(False, False)
        self.root.configure(bg="white")
        self._center_window()

        self.data = load_data()
        self._current_frame = None
        self._show_search()

        # root 레벨 키 바인딩 — 어떤 위젯에 포커스가 있어도 동작
        self.root.bind("<Return>", self._on_root_return)
        self.root.bind("<Escape>", self._on_root_escape)
        self.root.bind("<Down>",   self._on_root_down)
        self.root.bind("<Up>",     self._on_root_up)
        # 일반 문자 입력 시 검색창으로 자동 리다이렉트
        self.root.bind("<Key>",    self._on_root_key)

        # 창 표시 후 포커스 강제 획득
        self.root.after(100, self._force_focus)

    def _center_window(self):
        self.root.update_idletasks()
        w, h = 400, 320
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2 - 60
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _force_focus(self):
        self.root.update()
        # Win32 API로 OS 레벨 포커스 강제 획득
        hwnd = ctypes.windll.user32.FindWindowW(None, "빠른 문구")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)       # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.after(300, lambda: self.root.attributes("-topmost", False))

    def reload_data(self):
        self.data = load_data()
        if isinstance(self._current_frame, SearchFrame):
            self._current_frame.load_phrases(self.data["phrases"])

    def _switch_frame(self, frame):
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = frame
        frame.pack(fill="both", expand=True)

    def _show_search(self):
        frame = SearchFrame(self.root, self)
        self._switch_frame(frame)
        frame.load_phrases(self.data["phrases"])

    def copy_phrase(self, phrase):
        self._copy_and_close(phrase["template"], phrase)

    def _on_root_return(self, event):
        if isinstance(self._current_frame, SearchFrame):
            self._current_frame._select_current()
        return "break"

    def _on_root_escape(self, event):
        self.root.destroy()
        return "break"

    def _on_root_down(self, event):
        if isinstance(self._current_frame, SearchFrame):
            self._current_frame._move_sel(1)
        return "break"

    def _on_root_up(self, event):
        if isinstance(self._current_frame, SearchFrame):
            self._current_frame._move_sel(-1)
        return "break"

    def _on_root_key(self, event):
        """Enter/Esc/방향키 제외 — 검색창으로 리다이렉트."""
        if not isinstance(self._current_frame, SearchFrame):
            return
        if not event.char or not event.char.isprintable():
            return
        entry = self._current_frame.search_entry
        if self.root.focus_get() is entry:
            return  # 이미 검색창에 포커스 있음 → 기본 동작 유지
        entry.focus_set()
        entry.insert(tk.END, event.char)
        self._current_frame._filter(entry.get())
        return "break"

    def _copy_and_close(self, text, phrase):
        win_copy(text)

        data = load_data()
        for p in data["phrases"]:
            if p["id"] == phrase["id"]:
                p["use_count"] = p.get("use_count", 0) + 1
                break
        save_data(data)

        threading.Thread(target=send_paste, daemon=True).start()
        self.root.destroy()

    def open_manage(self):
        ManageWindow(self.root, self)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    QuickPhrasesApp().run()
