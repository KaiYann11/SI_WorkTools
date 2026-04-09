# SI WorkTools — Claude 작업 가이드

Claude Code가 이 프로젝트에서 효율적으로 작업하기 위한 컨텍스트 문서.
새 대화 시작 시 반드시 이 파일을 먼저 읽어 중복 파악 작업을 최소화한다.

---

## 프로젝트 개요

- **플랫폼**: Windows 11, Python 3.9+, Tkinter GUI
- **패키지**: `tkcalendar`, `pystray`, `Pillow`, `keyboard`
- **데이터**: JSON 파일 기반 영속성 (런타임 데이터는 `.gitignore` 제외)
- **진입점**: `tool_hub.pyw` → 각 도구 실행

---

## 공통 패턴

### GUI 규칙
```python
FONT   = ("맑은 고딕", 10)
FONT_S = ("맑은 고딕", 9)
FONT_B = ("맑은 고딕", 11, "bold")
BG         = "#F8FAFC"   # 전체 배경
HEADER_BG  = "#1E40AF"   # 헤더 파란색
CARD_BG    = "white"     # 카드 배경
```

### 단일 인스턴스
```python
_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "AppName_Mutex")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)
```

### 스크롤 가능 카드 영역 패턴
```python
canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=sb.set)
sb.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
inner = tk.Frame(canvas, bg=BG)
wid = canvas.create_window((0, 0), window=inner, anchor="nw")
inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
```

### grab_set 다이얼로그 + refresh 순서
```python
# 반드시 destroy() 먼저, refresh는 나중에 (grab 해제 후 repaint)
self.destroy()
self.app.refresh_list()
```

---

## 파일별 요점

### tool_hub.pyw
- `hub_config.json` → `tools[]` 배열 → 카드 UI 자동 생성
- 배지 타입: `daily_scrum_json` (오늘 히스토리 파일 유무), `task_urgent` (긴급/마감초과 작업)
- 트레이: `pystray`, 전역 단축키: `keyboard.add_hotkey()`
- 자동시작: `winreg` HKCU Run 키

### task_manager.py
데이터 파일: `task_manager_data.json`
```
핵심 클래스:
  TaskManagerApp
  ├── TaskListPanel      (미종료 / 종료 / 오늘 탭 Treeview)
  ├── TaskDetailPanel    (메모 / 연결 / 최종결과 / 변경이력 탭)
  └── NotificationManager (daemon 스레드, 60초 주기)

팝업 다이얼로그:
  TaskEditor, MemoAddDialog, CloseTaskDialog
  ChangeCommentDialog, SequenceManagerDialog
  EffortReportDialog, DailyScrumExtractDialog
  DateTimePickerDialog, LinkSelectorDialog
```

목록 컬럼 수정 시 **3곳 동시 수정 필수**:
```python
TREE_COLS    = ("seq", "priority", "title", "project", ...)   # 1. 컬럼 ID
TREE_HEADERS = [("seq","순서",42), ("priority","우선",50), ...]  # 2. 헤더+너비
# _insert() values 튜플                                         # 3. 행 데이터
```

공수 유틸리티:
```python
parse_effort_min("1d 4h 30m") → 780   # 1일=8시간
format_effort_min(780) → "1d 4h 30m"
```

날짜 범위 판별:
```python
_is_date_task(task, target_date)  # scheduled_at ~ deadline 범위 포함 여부
_is_today_task(task)              # 오늘 기준
```

태그 우선순위 (나중에 configure된 태그가 앞 태그를 덮음):
`완료/취소(회색)` < `overdue/dday(빨강)` < `d1(주황)` < `d3(노랑)` < `진행중(파랑)` < `related(보라, 마지막 설정)`

### alarm_clock.pyw
데이터 파일: `alarm_data.json`
```
핵심 클래스:
  AlarmClockApp
  ├── AlarmTab        (카드 목록, CRUD)
  ├── TimerTab        (카운트다운)
  ├── StopwatchTab    (스톱워치, 랩)
  └── AlarmNotifier   (daemon 스레드, 10초 주기)
```

미니 모드 상태:
```python
self._mini_mode = True/False
self._blink_after_ids = []   # 깜빡임 after ID 추적, _refresh_mini()에서 전부 취소
self._mini_clock_after = None  # KST/UTC 시계 after ID
```

"한 번" 알람 발화 후 처리:
- `fired_dates[]`에 날짜 추가
- `_make_mini_row()` 에서 `fired_dates`에 오늘이 있으면 "완료" 표시

남은시간 색상: `<10분→빨강+깜빡임 / <30분→주황 / <1시간→노랑 / 이상→흰색`

### daily_scrum.pyw
- 히스토리 저장: `daily_scrum_history/YYYY-MM-DD.json`
- 배지 조건: 오늘 파일이 없으면 `!`

---

## 데이터 스키마 요약

### task_manager_data.json
```json
{
  "next_id": 13,
  "next_memo_id": 4,
  "today_display_order": [11, 12, 3, 2],
  "tasks": [{
    "id": 1,
    "title": "작업명",
    "project": "과제명",
    "system": "시스템",
    "type": "구현|설계|디버깅|테스트|배포|분석|회의|기타",
    "assignee": "담당자",
    "priority": "긴급|높음|보통|낮음",
    "status": "대기|진행중|완료|취소",
    "scheduled_at": "2026-04-08T09:00",
    "deadline": "2026-04-09T14:00",
    "notify_before_min": 30,
    "effort": "4h",
    "actual_effort": "3h",
    "seq_order": null,
    "description": "",
    "tags": [],
    "parent_id": null,
    "sub_ids": [],
    "linked_ids": [],
    "memos": [{ "id": 1, "ts": "2026-04-08T14:02", "content": "메모" }],
    "result": { "summary": "", "score": null, "feedback": "" },
    "change_history": [{ "ts": "...", "changes": [{ "field": "마감일시", "old": "...", "new": "..." }], "comment": "" }],
    "created_at": "2026-04-08T10:43",
    "updated_at": "2026-04-08T14:16"
  }]
}
```

### alarm_data.json
```json
{
  "next_id": 2,
  "alarms": [{
    "id": 1,
    "time": "08:00",
    "label": "알람 라벨",
    "repeat": "한 번|매일|평일(월~금)|주말(토~일)",
    "enabled": true,
    "confirmed": false,
    "fired_dates": ["2026-04-09"]
  }]
}
```

### hub_config.json — tools[] 항목
```json
{
  "id": "tool_id",
  "name": "도구명",
  "description": "설명",
  "icon_emoji": "🔧",
  "launch": { "type": "py|pyw|exe", "path": "상대경로" },
  "hotkey": "ctrl+alt+N",
  "badge_check": null
}
```

---

## 주의사항 / 자주 하는 실수

1. **컬럼 추가**: `TREE_COLS`, `TREE_HEADERS`, `_insert()` values 튜플 세 곳 동시 수정
2. **grab_set 다이얼로그**: `destroy()` 후 `refresh_list()` 호출 순서 지킬 것
3. **blink after_id**: `_refresh_mini()` 재진입 시 `_blink_after_ids` 전부 취소 후 clear
4. **today_order**: `TaskListPanel._today_order`는 메모리 상태 — 파일 재로드 금지, `_save_today_order()`만 파일 갱신
5. **Treeview 태그 순서**: `related` 태그는 항상 가장 마지막에 `tag_configure`
6. **점수(score)**: DB에 0~100으로 저장된 구버전 데이터 → 표시 시 `if score > 5: score = round(score/20)` 변환 적용 중
