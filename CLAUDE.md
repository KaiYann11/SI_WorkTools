# SI WorkTools — Claude 작업 가이드

새 대화 시작 시 이 파일을 먼저 읽는다.
상세 작업 전 해당 도구의 `docs/` 파일을 추가로 읽으면 중복 탐색이 줄어든다.

---

## 프로젝트 개요

- **플랫폼**: Windows 11, Python 3.9+, Tkinter GUI
- **패키지**: `tkcalendar`, `pystray`, `Pillow`, `keyboard`
- **데이터**: JSON 파일 기반 영속성 (런타임 데이터는 `.gitignore` 제외)
- **진입점**: `tool_hub.pyw` → 각 도구 실행

---

## 도구별 문서 빠른 참조

| 파일 | 상세 문서 | 한 줄 설명 |
|------|-----------|-----------|
| `tool_hub.pyw` | [docs/tool_hub.md](docs/tool_hub.md) | 메인 런처, 트레이, 전역 단축키, 배지 |
| `task_manager.py` | [docs/task_manager.md](docs/task_manager.md) | 작업 CRUD, 메모, 공수, 알림 |
| `alarm_clock.pyw` | [docs/alarm_clock.md](docs/alarm_clock.md) | 알람·타이머·스톱워치, 미니 모드 |
| `daily_scrum.pyw` | [docs/daily_scrum.md](docs/daily_scrum.md) | 스탠드업 기록, 무드미터 |
| `email_template.pyw` | [docs/email_template.md](docs/email_template.md) | 변수 치환 이메일 템플릿 |
| `quick_phrases.py` | [docs/quick_phrases.md](docs/quick_phrases.md) | 자주 쓰는 문구 클립보드 복사 |
| `file_batch_mover.py` | [docs/file_batch_mover.md](docs/file_batch_mover.md) | 폴더구조 유지 배치 복사/이동 |
| `file_rename/rename_tool.py` | [docs/file_rename.md](docs/file_rename.md) | 파일명 일괄 변경 |

공통 코드 패턴 → [docs/_patterns.md](docs/_patterns.md)  
최근 변경 이력 → [docs/_changes.md](docs/_changes.md)

---

## 공통 패턴 요약

> 코드 스니펫 상세는 `docs/_patterns.md` 참고.

### GUI 상수
```python
FONT   = ("맑은 고딕", 10)
FONT_S = ("맑은 고딕", 9)
FONT_B = ("맑은 고딕", 11, "bold")
BG        = "#F8FAFC"   # 전체 배경
HEADER_BG = "#1E40AF"   # 헤더 파란색
CARD_BG   = "white"     # 카드 배경
```

### 단일 인스턴스
```python
_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "AppName_Mutex")
if ctypes.windll.kernel32.GetLastError() == 183:
    sys.exit(0)
```

### grab_set 다이얼로그 + refresh 순서
```python
self.destroy()          # grab 해제
self.app.refresh_list() # 반드시 destroy() 후
```

---

## 파일별 핵심 요점

### tool_hub.pyw
- `hub_config.json` → `tools[]` 배열 → 카드 UI 자동 생성
- 배지 타입: `daily_scrum_json` (오늘 히스토리 파일 유무), `task_urgent` (긴급/마감초과 작업)
- 트레이: `pystray` / 전역 단축키: `keyboard.add_hotkey()`
- 자동시작: `winreg` HKCU Run 키

### task_manager.py
데이터: `task_manager_data.json`

컬럼 추가 시 **3곳 동시 수정 필수**:
```python
TREE_COLS    = ("seq", "priority", ...)          # 1. 컬럼 ID
TREE_HEADERS = [("seq","순서",42), ...]           # 2. 헤더+너비
# _insert() values 튜플                           # 3. 행 데이터
```

공수 유틸리티:
```python
parse_effort_min("1d 4h 30m") → 780  # 1일=8시간
format_effort_min(780) → "1d 4h 30m"
```

날짜 선택 팝업:
```python
pick_datetime(parent, initial_value="", default_hour=9) → "YYYY-MM-DDTHH:MM" | "" | None
# default_hour: 값이 없을 때 적용되는 기본 시각 (예정=9, 마감=18)
```

태그 우선순위 (나중에 configure된 태그가 덮음):
`완료/취소(회색)` < `overdue/dday(빨강)` < `d1(주황)` < `d3(노랑)` < `진행중(파랑)` < `related(보라, 마지막)`

### alarm_clock.pyw
데이터: `alarm_data.json`

미니 모드 상태:
```python
self._mini_mode = True/False
self._blink_after_ids = []        # _refresh_mini() 진입 시 전부 취소 후 clear
self._mini_clock_after = None
```

반복 알람 확인 처리:
- 확인 체크 시 `confirmed=True` + `confirmed_date="YYYY-MM-DD"` 저장
- `AlarmNotifier`: 날짜가 바뀌거나 당일 알람 시각이 지나면 `confirmed` 자동 해제

### daily_scrum.pyw
- 히스토리: `daily_scrum_history/YYYY-MM-DD.json`
- 배지 조건: 오늘 파일 없으면 `!`

---

## 전역 주의사항 / 자주 하는 실수

1. **컬럼 추가**: `TREE_COLS`, `TREE_HEADERS`, `_insert()` values 튜플 세 곳 동시 수정
2. **grab_set 다이얼로그**: `destroy()` 후 `refresh_list()` 호출 순서 지킬 것
3. **blink after_id**: `_refresh_mini()` 재진입 시 `_blink_after_ids` 전부 취소 후 clear
4. **today_order**: `TaskListPanel._today_order`는 메모리 상태 — 파일 재로드 금지, `_save_today_order()`만 파일 갱신
5. **Treeview 태그 순서**: `related` 태그는 항상 가장 마지막에 `tag_configure`
6. **점수(score)**: DB에 0~100 저장된 구버전 → 표시 시 `if score > 5: score = round(score/20)` 변환 중
7. **after/스레드 혼용**: UI 조작은 반드시 `root.after(0, fn)` 로 메인 스레드에서 수행
8. **날짜 선택 기본값**: `pick_datetime` 에 `default_hour` 지정 — 예정 일시=9, 마감 일시=18
