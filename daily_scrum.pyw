import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import json
import os

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_scrum_history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# 무드미터: (쾌적함 x, 활력 y) -> 감정
# x: -5(불쾌) ~ +5(쾌적), y: -5(저활력) ~ +5(고활력), 0 제외
MOOD_MAP = {
    # ── 빨강 (고활력 + 불쾌) ──────────────────────────────
    (-5, 5): "격분한 😡",     (-4, 5): "공황상태인 😱",  (-3, 5): "극심한 스트레스 😤",
    (-2, 5): "안절부절못하는 😰", (-1, 5): "충격받은 😳",
    (-5, 4): "격노한 🤬",     (-4, 4): "맹렬히 화난 😠", (-3, 4): "좌절한 😣",
    (-2, 4): "긴장된 😬",     (-1, 4): "망연자실한 😵",
    (-5, 3): "부글부글 끓는 😤",(-4, 3): "겁먹은 😨",   (-3, 3): "화난 😠",
    (-2, 3): "불안한 😟",     (-1, 3): "안달하는 😒",
    (-5, 2): "초조한 😰",     (-4, 2): "걱정스러운 😧", (-3, 2): "걱정하는 😟",
    (-2, 2): "짜증난 😤",     (-1, 2): "성가신 😒",
    (-5, 1): "역겨운 🤢",     (-4, 1): "괴로운 😣",    (-3, 1): "염려되는 😕",
    (-2, 1): "불편한 😐",     (-1, 1): "약이 오른 😤",

    # ── 노랑 (고활력 + 쾌적) ──────────────────────────────
    (1, 5): "놀란 😲",        (2, 5): "기운찬 🤩",      (3, 5): "축제같은 🎉",
    (4, 5): "들뜬 😆",        (5, 5): "황홀한 🌟",
    (1, 4): "과흥분된 ⚡",    (2, 4): "명랑한 😄",      (3, 4): "의욕적인 💪",
    (4, 4): "영감받은 ✨",    (5, 4): "의기양양한 😎",
    (1, 3): "에너지 넘치는 ⚡",(2, 3): "생기있는 😊",   (3, 3): "신나는 🎊",
    (4, 3): "낙관적인 🌈",    (5, 3): "열정적인 🔥",
    (1, 2): "기쁜 😊",        (2, 2): "집중된 🎯",      (3, 2): "행복한 😀",
    (4, 2): "자랑스러운 😊",  (5, 2): "설레는 🥳",
    (1, 1): "유쾌한 🙂",      (2, 1): "즐거운 😊",      (3, 1): "희망찬 🌈",
    (4, 1): "장난기 있는 😜", (5, 1): "더없이 행복한 😇",

    # ── 파랑 (저활력 + 불쾌) ──────────────────────────────
    (-5, -1): "혐오스러운 🤢",(-4, -1): "침울한 😞",   (-3, -1): "실망한 😔",
    (-2, -1): "의기소침한 😞",(-1, -1): "무감각한 😶",
    (-5, -2): "비관적인 😞",  (-4, -2): "시무룩한 😢",  (-3, -2): "낙담한 😔",
    (-2, -2): "슬픈 😢",      (-1, -2): "지루한 😑",
    (-5, -3): "소외된 😔",    (-4, -3): "비참한 😩",   (-3, -3): "외로운 😢",
    (-2, -3): "낙심한 😞",    (-1, -3): "피곤한 😴",
    (-5, -4): "절망적인 😞",  (-4, -4): "우울한 😢",   (-3, -4): "뚱한 😒",
    (-2, -4): "탈진한 😩",    (-1, -4): "지친 😫",
    (-5, -5): "자포자기하는 😞",(-4, -5): "희망없는 😢",(-3, -5): "황량한 😔",
    (-2, -5): "기력이 다한 😩",(-1, -5): "녹초가 된 😫",

    # ── 초록 (저활력 + 쾌적) ──────────────────────────────
    (1, -1): "편안한 😌",     (2, -1): "느긋한 🙂",    (3, -1): "만족한 😊",
    (4, -1): "사랑스러운 🥰", (5, -1): "충만한 😌",
    (1, -2): "차분한 😌",     (2, -2): "안정된 🙂",    (3, -2): "만족스러운 😊",
    (4, -2): "감사한 🙏",     (5, -2): "감동받은 🥺",
    (1, -3): "여유로운 😌",   (2, -3): "쿨한 😎",      (3, -3): "평온한 😇",
    (4, -3): "축복받은 🌟",   (5, -3): "균형잡힌 ⚖️",
    (1, -4): "잔잔한 🌊",     (2, -4): "사려깊은 🤔",  (3, -4): "평화로운 🕊️",
    (4, -4): "포근한 🤗",     (5, -4): "걱정없는 😊",
    (1, -5): "졸린 😴",       (2, -5): "자기만족하는 😌",(3, -5): "고요한 🧘",
    (4, -5): "아늑한 🛋️",    (5, -5): "평화롭고 고요한 😌",
}


def get_mood(x, y):
    """x=쾌적함, y=활력. 0이면 ±1로 올림."""
    if x == 0 and y == 0:
        return "보통 😐"
    nx = x if x != 0 else (1 if y > 0 else -1)
    ny = y if y != 0 else (1 if x > 0 else -1)
    # 범위 클램프
    nx = max(-5, min(5, nx))
    ny = max(-5, min(5, ny))
    return MOOD_MAP.get((nx, ny), "보통 😐")


def quadrant_color(x, y):
    if x > 0 and y > 0:
        return "#FFF9C4"   # 노랑
    elif x < 0 and y > 0:
        return "#FFCDD2"   # 빨강
    elif x < 0 and y < 0:
        return "#BBDEFB"   # 파랑
    elif x > 0 and y < 0:
        return "#C8E6C9"   # 초록
    return "#F5F5F5"       # 중립


def load_history_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history_file(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_sorted_history_files():
    return sorted(
        [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")],
        reverse=True
    )


def load_yesterday_today():
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    for candidate in [yesterday.isoformat(), None]:
        if candidate:
            filepath = os.path.join(HISTORY_DIR, f"{candidate}.json")
            if os.path.exists(filepath):
                try:
                    return load_history_file(filepath).get("today", "")
                except Exception:
                    pass
        else:
            files = get_sorted_history_files()
            if files:
                try:
                    return load_history_file(os.path.join(HISTORY_DIR, files[0])).get("today", "")
                except Exception:
                    pass
    return ""


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


class DailyScrumApp:
    def __init__(self, root):
        self.root = root
        self.root.title("데일리 스크럼 작성기")
        self.root.geometry("640x820")
        self.root.resizable(False, True)

        style = ttk.Style()
        style.configure("Header.TLabel", font=("맑은 고딕", 14, "bold"))
        style.configure("Section.TLabel", font=("맑은 고딕", 10, "bold"))
        style.configure("Mood.TLabel", font=("맑은 고딕", 13, "bold"))

        main_frame = ttk.Frame(root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        today = datetime.date.today()
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        date_str = f"{today.strftime('%Y-%m-%d')} ({weekdays[today.weekday()]})"
        date_row = ttk.Frame(main_frame)
        date_row.pack(fill=tk.X, pady=(0, 10))
        self.date_label = ttk.Label(date_row, text=f"📅 {date_str}", style="Header.TLabel")
        self.date_label.pack(side=tk.LEFT)
        ttk.Button(date_row, text="🔄 날짜 갱신", command=self._refresh_date).pack(side=tk.RIGHT)

        # === 1. 무드미터 ===
        self.mood_frame = tk.LabelFrame(
            main_frame, text="1. 무드미터",
            font=("맑은 고딕", 10, "bold"), padx=10, pady=8
        )
        self.mood_frame.pack(fill=tk.X, pady=5)

        # 쾌적함 (x축)
        pf = ttk.Frame(self.mood_frame)
        pf.pack(fill=tk.X, pady=2)
        ttk.Label(pf, text="😞 쾌적함", width=10).pack(side=tk.LEFT)
        self.pleasant_var = tk.IntVar(value=0)
        ttk.Scale(pf, from_=-5, to=5, variable=self.pleasant_var,
                  orient=tk.HORIZONTAL, command=lambda _: self._update_mood()
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(pf, text="😊", width=3).pack(side=tk.LEFT)
        self.pleasant_label = ttk.Label(pf, text="0", width=3, font=("맑은 고딕", 10, "bold"))
        self.pleasant_label.pack(side=tk.LEFT)

        # 활력 (y축)
        ef = ttk.Frame(self.mood_frame)
        ef.pack(fill=tk.X, pady=2)
        ttk.Label(ef, text="😴 활력", width=10).pack(side=tk.LEFT)
        self.energy_var = tk.IntVar(value=0)
        ttk.Scale(ef, from_=-5, to=5, variable=self.energy_var,
                  orient=tk.HORIZONTAL, command=lambda _: self._update_mood()
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(ef, text="⚡", width=3).pack(side=tk.LEFT)
        self.energy_label = ttk.Label(ef, text="0", width=3, font=("맑은 고딕", 10, "bold"))
        self.energy_label.pack(side=tk.LEFT)

        self.mood_display = tk.Label(
            self.mood_frame, text="기분: 보통 😐",
            font=("맑은 고딕", 13, "bold"), bg="#F5F5F5", pady=5
        )
        self.mood_display.pack(fill=tk.X, pady=(5, 0))

        # 사분면 범례
        legend_frame = ttk.Frame(self.mood_frame)
        legend_frame.pack(fill=tk.X, pady=(4, 0))
        for color, label in [("#FFCDD2","🔴 빨강: 고활력·불쾌"), ("#FFF9C4","🟡 노랑: 고활력·쾌적"),
                              ("#BBDEFB","🔵 파랑: 저활력·불쾌"), ("#C8E6C9","🟢 초록: 저활력·쾌적")]:
            tk.Label(legend_frame, text=label, bg=color, font=("맑은 고딕", 8),
                     padx=4, relief=tk.FLAT).pack(side=tk.LEFT, padx=2)

        # === 2. 어제한일 ===
        ttk.Label(main_frame, text="2. 어제한일", style="Section.TLabel").pack(
            anchor=tk.W, pady=(10, 2))
        self.yesterday_text = tk.Text(main_frame, height=4, font=("맑은 고딕", 10))
        self.yesterday_text.pack(fill=tk.X, pady=(0, 5))
        prev_today = load_yesterday_today()
        if prev_today:
            self.yesterday_text.insert("1.0", prev_today)

        # === 3. 오늘할일 ===
        ttk.Label(main_frame, text="3. 오늘할일", style="Section.TLabel").pack(
            anchor=tk.W, pady=(5, 2))
        self.today_text = tk.Text(main_frame, height=4, font=("맑은 고딕", 10))
        self.today_text.pack(fill=tk.X, pady=(0, 5))

        # === 4. 업무이슈공유 ===
        ttk.Label(main_frame, text="4. 업무이슈공유", style="Section.TLabel").pack(
            anchor=tk.W, pady=(5, 2))
        self.work_issue_text = PlaceholderText(
            main_frame, placeholder="없음", height=3, font=("맑은 고딕", 10))
        self.work_issue_text.pack(fill=tk.X, pady=(0, 5))

        # === 5. 개인이슈공유 ===
        ttk.Label(main_frame, text="5. 개인이슈공유", style="Section.TLabel").pack(
            anchor=tk.W, pady=(5, 2))
        self.personal_issue_text = PlaceholderText(
            main_frame, placeholder="없음", height=3, font=("맑은 고딕", 10))
        self.personal_issue_text.pack(fill=tk.X, pady=(0, 5))

        # 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="📋 클립보드에 복사", command=self._copy_to_clipboard
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(btn_frame, text="👁 미리보기", command=self._preview
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        ttk.Button(btn_frame, text="📂 이전 기록", command=self._show_history
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

        btn_frame2 = ttk.Frame(main_frame)
        btn_frame2.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_frame2, text="📊 무드 추이 보기", command=self._show_mood_trend
                   ).pack(fill=tk.X)

        self.status_var = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.status_var, foreground="green"
                  ).pack(anchor=tk.W)

    def _show_mood_trend(self):
        files = get_sorted_history_files()
        if not files:
            messagebox.showinfo("무드 추이", "기록된 데이터가 없습니다.")
            return

        entries = []
        for f in reversed(files):
            try:
                data = load_history_file(os.path.join(HISTORY_DIR, f))
                entries.append({
                    "date": data.get("date", f.replace(".json", "")),
                    "pleasant": data.get("pleasant", 0),
                    "energy": data.get("energy", 0),
                    "mood": data.get("mood", ""),
                })
            except Exception:
                pass

        if not entries:
            messagebox.showinfo("무드 추이", "읽을 수 있는 기록이 없습니다.")
            return

        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.font_manager as fm
            import matplotlib as mpl
        except ImportError:
            messagebox.showwarning(
                "라이브러리 없음",
                "matplotlib가 설치되어 있지 않습니다.\n\npip install matplotlib 으로 설치해주세요.",
                parent=self.root,
            )
            return

        # 한글 폰트 설정
        available = {f.name for f in fm.fontManager.ttflist}
        for fn in ["Malgun Gothic", "NanumGothic", "AppleGothic", "Gulim"]:
            if fn in available:
                mpl.rc("font", family=fn)
                break
        mpl.rc("axes", unicode_minus=False)

        dates    = [e["date"]     for e in entries]
        pleasant = [e["pleasant"] for e in entries]
        energy   = [e["energy"]   for e in entries]
        moods    = [e["mood"]     for e in entries]
        x        = list(range(len(dates)))

        win = tk.Toplevel(self.root)
        win.title("무드미터 추이")
        win.geometry("860x540")

        fig = Figure(figsize=(10, 5.5), dpi=96)
        ax = fig.add_subplot(111)

        # 배경 사분면 색
        ax.axhspan(0,    5.5,  xmin=0, xmax=1, alpha=0.07, color="#FFC107")  # 노랑
        ax.axhspan(-5.5, 0,   xmin=0, xmax=1, alpha=0.07, color="#90CAF9")  # 파랑
        ax.axhline(0, color="gray", linestyle="--", linewidth=1, alpha=0.5)

        # 꺾은선 (마커 없이)
        ax.plot(x, pleasant, "-", color="#FF9800", linewidth=2, label="쾌적함")
        ax.plot(x, energy,   "-", color="#2196F3", linewidth=2, label="활력")

        # 사분면별 색상 점
        quad_colors = {
            ( 1,  1): "#FFC107",   # 노랑: 쾌적+활력
            (-1,  1): "#EF5350",   # 빨강: 불쾌+활력
            (-1, -1): "#42A5F5",   # 파랑: 불쾌+저활력
            ( 1, -1): "#66BB6A",   # 초록: 쾌적+저활력
        }
        def _qkey(p, e):
            return (1 if p >= 0 else -1, 1 if e >= 0 else -1)

        for i in range(len(x)):
            qc = quad_colors[_qkey(pleasant[i], energy[i])]
            ax.scatter(x[i], pleasant[i], color=qc, zorder=5, s=65,
                       edgecolors="white", linewidths=0.8)
            ax.scatter(x[i], energy[i],   color=qc, zorder=5, s=65,
                       marker="s", edgecolors="white", linewidths=0.8)

        ax.set_xticks(x)
        ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(-5, 6))
        ax.set_ylim(-5.5, 5.5)
        ax.set_ylabel("값 (-5 ~ +5)")
        ax.set_title("무드미터 추이  (● 쾌적함 / ■ 활력)")
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, alpha=0.2, linestyle="--")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 날짜 위 마우스 hover → 툴팁
        annot = ax.annotate(
            "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#BDBDBD", alpha=0.95),
            fontsize=9,
        )
        annot.set_visible(False)

        def _on_motion(event):
            if event.inaxes != ax or event.xdata is None:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return
            for i, xi in enumerate(x):
                if abs(event.xdata - xi) < 0.35:
                    annot.xy = (xi, max(pleasant[i], energy[i]))
                    annot.set_text(
                        f"{dates[i]}\n"
                        f"쾌적함: {pleasant[i]:+d}  활력: {energy[i]:+d}\n"
                        f"{moods[i]}"
                    )
                    annot.set_visible(True)
                    canvas.draw_idle()
                    return
            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()

        fig.canvas.mpl_connect("motion_notify_event", _on_motion)
        win.protocol("WM_DELETE_WINDOW", lambda: (fig.clf(), win.destroy()))

    def _refresh_date(self):
        today = datetime.date.today()
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        date_str = f"{today.strftime('%Y-%m-%d')} ({weekdays[today.weekday()]})"
        self.date_label.config(text=f"📅 {date_str}")

        # 어제한일 갱신 (직전 저장된 오늘할일로)
        prev_today = load_yesterday_today()
        self.yesterday_text.delete("1.0", tk.END)
        if prev_today:
            self.yesterday_text.insert("1.0", prev_today)

        # 오늘 입력 필드 초기화
        self.today_text.delete("1.0", tk.END)
        self.work_issue_text.delete("1.0", tk.END)
        self.work_issue_text._placeholder_on = False
        self.work_issue_text._show_placeholder()
        self.personal_issue_text.delete("1.0", tk.END)
        self.personal_issue_text._placeholder_on = False
        self.personal_issue_text._show_placeholder()

        # 무드 초기화
        self.pleasant_var.set(0)
        self.energy_var.set(0)
        self._update_mood()

        self.status_var.set("🔄 날짜가 갱신되었습니다!")
        self.root.after(3000, lambda: self.status_var.set(""))

    def _update_mood(self):
        x = int(round(self.pleasant_var.get()))
        y = int(round(self.energy_var.get()))
        self.pleasant_var.set(x)
        self.energy_var.set(y)
        self.pleasant_label.config(text=str(x))
        self.energy_label.config(text=str(y))
        mood = get_mood(x, y)
        bg = quadrant_color(x, y)
        self.mood_display.config(text=f"기분: {mood}", bg=bg)
        self.mood_frame.config(bg=bg)

    def _generate_text(self):
        x = int(round(self.pleasant_var.get()))
        y = int(round(self.energy_var.get()))
        yesterday = self.yesterday_text.get("1.0", tk.END).strip()
        today_work = self.today_text.get("1.0", tk.END).strip()
        work_issue = self.work_issue_text.get_real_text() or "없음"
        personal_issue = self.personal_issue_text.get_real_text() or "없음"
        lines = [
            f"1. 무드미터: {get_mood(x, y)} (쾌적함: {x}, 활력: {y})",
            f"2. 어제한일:\n{yesterday}",
            f"3. 오늘할일:\n{today_work}",
            f"4. 업무이슈공유: {work_issue}",
            f"5. 개인이슈공유: {personal_issue}",
        ]
        return "\n".join(lines)

    def _save_history(self):
        x = int(round(self.pleasant_var.get()))
        y = int(round(self.energy_var.get()))
        data = {
            "date": datetime.date.today().isoformat(),
            "pleasant": x,
            "energy": y,
            "mood": get_mood(x, y),
            "yesterday": self.yesterday_text.get("1.0", tk.END).strip(),
            "today": self.today_text.get("1.0", tk.END).strip(),
            "work_issue": self.work_issue_text.get_real_text() or "없음",
            "personal_issue": self.personal_issue_text.get_real_text() or "없음",
            "full_text": self._generate_text(),
        }
        filepath = os.path.join(HISTORY_DIR, f"{datetime.date.today().isoformat()}.json")
        save_history_file(filepath, data)

    def _copy_to_clipboard(self):
        text = self._generate_text()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._save_history()
        self.status_var.set("✅ 클립보드에 복사 + 기록 저장 완료!")
        self.root.after(3000, lambda: self.status_var.set(""))

    def _preview(self):
        win = tk.Toplevel(self.root)
        win.title("미리보기")
        win.geometry("500x400")
        preview = tk.Text(win, font=("맑은 고딕", 10), wrap=tk.WORD)
        preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        preview.insert("1.0", self._generate_text())
        preview.config(state=tk.DISABLED)

    def _show_history(self):
        win = tk.Toplevel(self.root)
        win.title("이전 기록 조회")
        win.geometry("700x550")

        files = get_sorted_history_files()
        state = {"current_file": None, "files": list(files)}

        left_frame = ttk.Frame(win, padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(left_frame, text="날짜 목록", font=("맑은 고딕", 10, "bold")).pack(anchor=tk.W)

        lb_frame = ttk.Frame(left_frame)
        lb_frame.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lb_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        date_listbox = tk.Listbox(lb_frame, width=18, font=("맑은 고딕", 10), yscrollcommand=sb.set)
        date_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=date_listbox.yview)

        def refresh_listbox():
            date_listbox.delete(0, tk.END)
            if not state["files"]:
                date_listbox.insert(tk.END, "(기록 없음)")
            for f in state["files"]:
                date_listbox.insert(tk.END, f.replace(".json", ""))

        refresh_listbox()

        right_frame = ttk.Frame(win, padding=5)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(right_frame, text="작성 내용 (직접 수정 가능)", font=("맑은 고딕", 10, "bold")).pack(anchor=tk.W)

        content_text = tk.Text(right_frame, font=("맑은 고딕", 10), wrap=tk.WORD)
        content_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        action_frame = ttk.Frame(right_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))

        def on_select(event=None):
            selection = date_listbox.curselection()
            if not selection or not state["files"]:
                return
            filename = state["files"][selection[0]]
            state["current_file"] = os.path.join(HISTORY_DIR, filename)
            try:
                data = load_history_file(state["current_file"])
                content_text.delete("1.0", tk.END)
                content_text.insert("1.0", data.get("full_text", ""))
            except Exception as ex:
                content_text.delete("1.0", tk.END)
                content_text.insert("1.0", f"파일 읽기 오류: {ex}")

        def save_edit():
            if not state["current_file"]:
                return
            try:
                data = load_history_file(state["current_file"])
                data["full_text"] = content_text.get("1.0", tk.END).strip()
                save_history_file(state["current_file"], data)
                messagebox.showinfo("저장 완료", "수정 내용이 저장되었습니다.", parent=win)
            except Exception as ex:
                messagebox.showerror("오류", f"저장 실패: {ex}", parent=win)

        def delete_record():
            if not state["current_file"]:
                return
            fname = os.path.basename(state["current_file"]).replace(".json", "")
            if not messagebox.askyesno("삭제 확인", f"{fname} 기록을 삭제하시겠습니까?", parent=win):
                return
            try:
                os.remove(state["current_file"])
                state["files"] = get_sorted_history_files()
                state["current_file"] = None
                content_text.delete("1.0", tk.END)
                refresh_listbox()
            except Exception as ex:
                messagebox.showerror("오류", f"삭제 실패: {ex}", parent=win)

        def copy_content():
            content = content_text.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self.status_var.set("✅ 이전 기록이 클립보드에 복사되었습니다!")
                self.root.after(3000, lambda: self.status_var.set(""))

        ttk.Button(action_frame, text="💾 수정 저장", command=save_edit
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(action_frame, text="📋 복사", command=copy_content
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        ttk.Button(action_frame, text="🗑 삭제", command=delete_record
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

        date_listbox.bind("<<ListboxSelect>>", on_select)


if __name__ == "__main__":
    root = tk.Tk()
    app = DailyScrumApp(root)
    root.mainloop()
