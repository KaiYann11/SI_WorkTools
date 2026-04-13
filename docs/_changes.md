# 변경 이력

최근 유의미한 코드 변경 로그. 역순(최신 우선).
버그 수정 / 기능 추가 / 동작 변경만 기록하고 문서 수정은 생략한다.

---

## 2026-04-13

### alarm_clock.pyw — 반복 알람 확인 날짜 추적

**변경 내용**
- `AlarmTab._check()`: 확인 체크 시 `confirmed_date = "YYYY-MM-DD"` 저장, 해제 시 제거
- `AlarmNotifier._loop()`: 반복 알람(`repeat != "한 번"`)이 `confirmed=True` 인 경우
  - `confirmed_date != today` 이거나
  - `confirmed_date == today` 이고 현재 시각이 알람 시각 이후이면
  → `confirmed=False`, `confirmed_date` 삭제 후 파일 저장

**이유**: 매일/평일/주말 반복 알람이 한 번 확인 처리하면 이후에 영구 비활성 상태가 되는 문제 수정.

**영향 파일**: `alarm_clock.pyw`, `alarm_data.json` (스키마 변경)

**스키마 추가**
```json
{ "confirmed_date": "2026-04-13" }   // confirmed=true 인 경우에만 존재
```

---

### task_manager.py — 날짜 선택 UX 개선

**변경 내용**
- `DateTimePickerDialog.__init__()`: `default_hour=9` 파라미터 추가
  - 초기값이 없을 때 시(hour)를 `default_hour`로 초기화
- `pick_datetime()`: `default_hour=9` 파라미터 추가, `DateTimePickerDialog`에 전달
- `TaskEditor._pick_dt()`: `default_hour=9` 파라미터 추가, `pick_datetime`에 전달
- `TaskEditor._build_sched()` 내 `_dt_row()`:
  - `default_hour` 파라미터 추가
  - 레이블(`tk.Label`)에 `<Button-1>` 바인딩 추가 → 클릭만으로 달력 팝업
  - 예정 일시: `default_hour=9`, 마감 일시: `default_hour=18`

**이유**: 텍스트창 클릭 시 달력이 안 열리는 UX 문제 수정. 마감 일시 기본값이 09:00으로 부자연스러웠던 문제 수정.

**영향 파일**: `task_manager.py`

---

## 2026-04-09 (초기 커밋 이후)

### tool_hub.pyw, task_manager.py, alarm_clock.pyw

초기 커밋 후 다수의 기능 개선 및 버그 수정이 포함된 커밋.
상세 내용은 `git log` 참고 (`git log --oneline`).
