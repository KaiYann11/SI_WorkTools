# 작업 관리 (task_manager.py)

일정·메모·알림을 통합 관리하는 작업 추적 도구.

---

## 기능

- 작업 CRUD (추가/수정/삭제/복제)
- 탭 분리: **미종료** / **종료** / **오늘**
- 우선순위·마감일 기반 색상 코딩
- 순서 관리: 명시적 순서(①②③) + 위치 순서(1 2 3)
- 메모 (타임스탬프, 편집/삭제)
- 연결 작업 (부모/서브/연계)
- 공수 관리: 예상공수 + 실투입 (`1d 4h` 형식)
- 변경 이력 (스케줄/마감/공수 변경 시 코멘트 포함)
- 완료 처리: 실투입공수 + 결과요약 + 1~5점 평가
- 알림: 시작/마감 전 토스트 팝업
- 공수 리포트: 기간·담당자별 일별/과제별 통계
- 데일리 스크럼 추출: 날짜·담당자 필터 → 클립보드 복사

---

## 단축키 (앱 내)

| 동작 | 방법 |
|------|------|
| 작업 수정 | 목록 더블클릭 |
| 상태 빠른 전환 | 우클릭 컨텍스트 메뉴 |
| 오늘 탭 순서 변경 | 드래그 앤 드롭 |

---

## 화면 구성

```
┌─────────────────────────────────────────────────────────────────┐
│ 🗂 작업 관리  [+ 작업 추가] [⟺ 순서 관리] [📊 공수 리포트] [📋 스크럼 추출] │
├──────────────────────────────┬──────────────────────────────────┤
│  [미종료] [종료] [오늘]       │  작업 상세                       │
│  Treeview 목록               │  ┌ 기본정보 요약 ──────────────┐ │
│  필터: 상태/우선순위/검색어   │  └─────────────────────────────┘ │
│                              │  [메모] [연결] [최종결과] [이력]  │
├──────────────────────────────┴──────────────────────────────────┤
│  전체 N | 진행중 N | 긴급 N | 마감초과 N                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 목록 컬럼

| 컬럼 ID | 헤더 | 설명 |
|---------|------|------|
| `seq` | 순서 | 명시적 순서(①②) 또는 위치(1 2 3) |
| `priority` | 우선 | 🔴긴급 / 🟠높음 / 🟡보통 / ⚪낮음 |
| `title` | 작업명 | 제목 |
| `project` | 과제명 | 프로젝트명 |
| `system` | 시스템 | 시스템명 |
| `assignee` | 담당자 | |
| `status` | 상태 | ⏸대기 / ▶진행중 / ✅완료 / 🚫취소 |
| `scheduled` | 시작일시 | `scheduled_at` |
| `deadline_dt` | 종료일시 | `deadline` |
| `effort` | 예상공수 | |
| `actual_effort` | 실투입 | |
| `dday` | D-Day | 마감까지 남은 일수 |

### 컬럼 추가 시 반드시 3곳 동시 수정

```python
TREE_COLS    = ("seq", "priority", "title", ...)     # 1. 컬럼 ID 튜플
TREE_HEADERS = [("seq","순서",42), ...]               # 2. (id, 헤더명, 너비) 리스트
# TaskListPanel._insert() 내 values 튜플              # 3. 행 데이터 값
```

### 행 색상 규칙 (태그 우선순위 낮음→높음)

| 조건 | 태그 | 색상 |
|------|------|------|
| 완료/취소 | `done` | 회색 + 취소선 |
| 마감 초과 | `overdue` | 빨강 |
| D-Day | `dday` | 빨강 |
| 마감 1일 전 | `d1` | 주황 |
| 마감 3일 이내 | `d3` | 노랑 |
| 진행중 | `active` | 파랑 |
| 연관 작업 선택 시 | `related` | 보라 bold (항상 마지막 tag_configure) |

---

## 날짜 선택 팝업

```python
# 시그니처
def pick_datetime(parent, initial_value="", default_hour=9) -> str | None:
    """
    반환값:
      None  → 취소 (변경 없음)
      ""    → 지우기 (값 삭제)
      "YYYY-MM-DDTHH:MM" → 선택된 날짜·시각
    """

class DateTimePickerDialog(tk.Toplevel):
    def __init__(self, parent, initial_value="", default_hour=9):
        # initial_value 없으면 default_hour 시각으로 초기화
```

**호출 규칙**: 예정 일시 `default_hour=9`, 마감 일시 `default_hour=18`.

텍스트 레이블 클릭과 📅 버튼 양쪽 모두 `_pick_dt(var, default_hour)` 를 호출한다.

---

## 공수 형식

```
"1d 4h 30m"  →  1일(8h) + 4시간 + 30분 = 780분
"2.5h"       →  150분
"30m"        →  30분
```

```python
parse_effort_min(s: str) -> int    # 분 단위 정수
format_effort_min(m: int) -> str   # "1d 4h 30m" 형식
```

---

## 날짜 범위 판별

```python
_is_date_task(task, target_date)  # scheduled_at ~ deadline 범위에 target_date 포함 여부
_is_today_task(task)              # 오늘 기준으로 _is_date_task 호출
```

---

## 데이터 스키마

### task_manager_data.json

```json
{
  "next_id": 13,
  "next_memo_id": 4,
  "today_display_order": [11, 12, 3, 2],
  "tasks": [ /* Task 객체 배열 */ ]
}
```

### Task 객체

```json
{
  "id": 1,
  "title": "작업명",
  "project": "과제명",
  "system": "시스템",
  "type": "구현",
  "assignee": "담당자",
  "priority": "높음",
  "status": "진행중",
  "scheduled_at": "2026-04-08T09:00",
  "deadline": "2026-04-09T18:00",
  "notify_before_min": 30,
  "effort": "4h",
  "actual_effort": "3h",
  "seq_order": null,
  "description": "",
  "tags": [],
  "parent_id": null,
  "sub_ids": [],
  "linked_ids": [],
  "memos": [
    { "id": 1, "ts": "2026-04-08T14:02", "content": "메모 내용" }
  ],
  "result": { "summary": "결과", "score": 4, "feedback": "" },
  "change_history": [
    {
      "ts": "2026-04-08T14:02",
      "changes": [{ "field": "마감일시", "old": "...", "new": "..." }],
      "comment": "변경 사유"
    }
  ],
  "created_at": "2026-04-08T10:43",
  "updated_at": "2026-04-08T14:16"
}
```

### 열거값

| 필드 | 허용값 |
|------|--------|
| `type` | 구현, 설계, 디버깅, 테스트, 배포, 분석, 회의, 기타 |
| `priority` | 긴급, 높음, 보통, 낮음 |
| `status` | 대기, 진행중, 완료, 취소 |

---

## 클래스 구조

```
TaskManagerApp
├── TaskListPanel (Treeview 3탭)
│   ├── _tree_active   (미종료)
│   ├── _tree_done     (종료)
│   └── _tree_today    (오늘, 드래그 순서 변경)
├── TaskDetailPanel (4탭)
│   ├── 메모 탭         (카드 목록, 편집/삭제)
│   ├── 연결 탭         (부모/서브/연계)
│   ├── 최종결과 탭     (실투입, 요약, 점수, 피드백)
│   └── 변경이력 탭     (colored Text 위젯)
└── NotificationManager (daemon 스레드, 60초 주기)

팝업:
  TaskEditor              (추가/수정 — 기본/일정 탭)
  MemoAddDialog           (메모 추가/편집)
  CloseTaskDialog         (완료 처리: 실투입+결과)
  ChangeCommentDialog     (스케줄/공수 변경 사유)
  SequenceManagerDialog   (순서 관리 GUI)
  EffortReportDialog      (공수 리포트)
  DailyScrumExtractDialog (데일리 스크럼 추출)
  DateTimePickerDialog    (날짜+시간 선택, default_hour 지원)
  LinkSelectorDialog      (연결 작업 선택)
```

---

## 수정 시 체크리스트

| 작업 | 확인 항목 |
|------|-----------|
| 컬럼 추가/삭제 | `TREE_COLS` + `TREE_HEADERS` + `_insert()` values 3곳 동시 |
| Task 필드 추가 | `DEFAULT_TASK` 기본값 + `TaskEditor._fill()/_save()` + 스키마 갱신 |
| 날짜 선택 기본시각 변경 | `_dt_row(default_hour=...)` 호출부 확인 |
| 태그 추가 | `tag_configure` 호출 순서 — `related`가 항상 마지막인지 확인 |
| 알림 조건 변경 | `NotificationManager._loop()` + 알림 중복 방지 `_notified` set 키 |
| 오늘 탭 순서 변경 | `_today_order` 메모리 상태만 조작, `_save_today_order()`로만 파일 갱신 |
| 점수 표시 | `if score > 5: score = round(score/20)` 변환 로직 확인 (구버전 0~100 데이터) |

---

## 연관 파일

- `task_manager_data.json` — 런타임 데이터 (`.gitignore` 제외)
- `tool_hub.pyw` — `task_urgent` 배지 체크로 이 파일 참조
- `daily_scrum.pyw` — 스크럼 추출 시 task_manager 데이터 활용 가능
