# 공통 코드 패턴

프로젝트 전체에서 반복되는 코드 패턴 레퍼런스.
새 도구를 작성하거나 기존 도구를 수정할 때 이 패턴에서 벗어나지 않도록 한다.

---

## GUI 상수

모든 `.pyw` / `.py` 도구 파일 최상단에 동일하게 선언.

```python
FONT   = ("맑은 고딕", 10)
FONT_S = ("맑은 고딕", 9)
FONT_B = ("맑은 고딕", 11, "bold")

BG        = "#F8FAFC"   # 전체 배경
HEADER_BG = "#1E40AF"   # 헤더 파란색
CARD_BG   = "white"     # 카드/패널 배경
BTN_BG    = "#2563EB"   # 주 버튼 파란색
ACCENT    = "#1E40AF"
```

---

## 단일 인스턴스 (Named Mutex)

```python
import ctypes, sys

_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "MyApp_Mutex")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)
```

앱 이름마다 고유한 뮤텍스 이름 사용. 도구 허브가 이미 실행 중이면 새 프로세스를 즉시 종료.

---

## 헤더 바

```python
hdr = tk.Frame(root, bg=HEADER_BG, height=42)
hdr.pack(fill="x")
hdr.pack_propagate(False)

tk.Label(hdr, text="🗂 앱 제목", bg=HEADER_BG, fg="white",
         font=FONT_B).pack(side="left", padx=14)
ttk.Button(hdr, text="+ 추가", command=_add).pack(side="right", padx=8, pady=6)
```

---

## 스크롤 가능 카드 영역

```python
canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=sb.set)
sb.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

inner = tk.Frame(canvas, bg=BG)
wid = canvas.create_window((0, 0), window=inner, anchor="nw")

inner.bind("<Configure>",
           lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(wid, width=e.width))

# 마우스 휠 바인딩
def _on_wheel(e):
    canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
canvas.bind_all("<MouseWheel>", _on_wheel)
```

---

## 모달 다이얼로그 (grab_set)

```python
class MyDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("다이얼로그")
        self.resizable(False, False)
        self.grab_set()          # 모달
        self.configure(bg="white")
        self._build()

    def _confirm(self):
        # 반드시 destroy() 먼저, refresh는 나중에
        self.destroy()
        self.app.refresh_list()
```

> **주의**: `grab_set` 이후에는 `destroy()` 전까지 부모 창 조작이 막힌다.
> `refresh_list()` 를 `destroy()` 이전에 호출하면 grab이 풀리지 않아 UI가 멈춘다.

---

## 날짜+시간 선택 팝업

```python
# task_manager.py 에 정의된 공용 함수
result = pick_datetime(parent, initial_value="", default_hour=9)
# 반환값
#   None  → 취소 (아무 것도 변경하지 않을 것)
#   ""    → 지우기 (값 삭제)
#   "YYYY-MM-DDTHH:MM" → 선택된 날짜·시각
```

`default_hour`: 값이 비어 있을 때 기본으로 채워지는 시(hour).
- 예정 일시 → `9`
- 마감 일시 → `18`

---

## 클릭 가능한 레이블 (날짜 표시 셀)

```python
lbl = tk.Label(cell, textvariable=var, bg="#F8FAFC", relief="solid",
               bd=1, font=FONT, anchor="w", padx=6, cursor="hand2")
lbl.grid(row=0, column=0, sticky="ew")
lbl.bind("<Button-1>", lambda e, v=var, dh=default_hour: self._pick_dt(v, dh))

btn = ttk.Button(cell, text="📅", width=3,
                 command=lambda v=var, dh=default_hour: self._pick_dt(v, dh))
btn.grid(row=0, column=1, padx=(4, 0))
```

레이블 클릭과 📅 버튼 양쪽 모두 동일한 `_pick_dt` 를 호출한다.

---

## 백그라운드 스레드 + UI 알림

```python
import threading

class MyNotifier:
    def __init__(self, root):
        self._root = root
        self._stop = threading.Event()
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while not self._stop.wait(timeout=10):  # 10초 주기
            # ... 체크 로직 ...
            if should_notify:
                self._root.after(0, self._show_popup)  # UI 스레드로 전달

    def _show_popup(self):
        # Tk 위젯 조작은 여기서 (메인 스레드)
        pass

    def stop(self):
        self._stop.set()
```

> **주의**: 백그라운드 스레드에서 직접 Tk 위젯을 건드리면 안 된다.
> 반드시 `root.after(0, fn)` 으로 메인 스레드에 위임한다.

---

## `after` ID 관리 (깜빡임 등)

```python
self._blink_ids: list[str] = []

def _start_blink(self, widget):
    def _toggle(state):
        widget.configure(fg="red" if state else "white")
        aid = self._root.after(500, _toggle, not state)
        self._blink_ids.append(aid)
    _toggle(True)

def _stop_blink(self):
    for aid in self._blink_ids:
        self._root.after_cancel(aid)
    self._blink_ids.clear()
```

`_refresh_*` 진입 시 반드시 `_stop_blink()` 먼저 호출해 기존 after를 전부 취소한다.

---

## Treeview 태그 우선순위

```python
# 나중에 configure된 태그가 앞의 태그를 덮는다.
# 아래 순서가 곧 시각적 우선순위 순서 (위=낮음, 아래=높음).
tree.tag_configure("done",    foreground="#9CA3AF")
tree.tag_configure("overdue", foreground="#EF4444")
tree.tag_configure("dday",    foreground="#EF4444")
tree.tag_configure("d1",      foreground="#F97316")
tree.tag_configure("d3",      foreground="#EAB308")
tree.tag_configure("active",  foreground="#2563EB")
tree.tag_configure("related", foreground="#7C3AED", font=FONT_B)  # 항상 마지막
```

---

## JSON 저장/로드 패턴

```python
import json, os

DATA_FILE = "my_data.json"
DEFAULT   = {"next_id": 1, "items": []}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT.copy()

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```
