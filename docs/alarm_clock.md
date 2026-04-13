# 알람 설정기 (alarm_clock.pyw)

알람·카운트다운 타이머·스톱워치를 통합한 시간 관리 도구.

---

## 기능

### 알람 탭
- 시간(HH:MM) + 라벨 + 반복 주기 설정
- 반복: 한 번 / 매일 / 평일(월~금) / 주말(토~일)
- 켜짐/꺼짐 토글, 확인 체크
- 발화 시 토스트 팝업 + 비프음 (5회)
- "한 번" 알람: 발화 후 `fired_dates`에 기록, 미니 뷰에서 "완료" 표시
- 반복 알람: 확인 체크 시 `confirmed_date` 저장 → 날짜 변경 또는 알람 시각 경과 후 자동 해제

### 타이머 탭
- 시/분/초 직접 입력 또는 프리셋 (5분~1시간)
- 시작 / 일시정지 / 재개 / 초기화
- 완료 시 토스트 팝업 + 비프음

### 스톱워치 탭
- 1/100초 단위 표시 (Consolas 폰트)
- 랩 기록: 최단(초록) / 최장(빨강) 자동 강조
- 랩 번호 / 랩 타임 / 누적 시간

---

## 미니 모드

헤더 `⊟` 클릭으로 컴팩트 뷰로 전환.

- 헤더: KST / UTC 시계 (1초 갱신) + 📌 고정 + ⊞ 복원
- 알람 행: `라벨 [반복주기]` + 남은시간 + ✔/✏/🗑
- 높이 자동 조정 (알람 수 × 26px)

### 남은시간 색상

| 조건 | 색상 |
|------|------|
| 10분 미만 | 빨강 + 깜빡임 |
| 30분 미만 | 주황 |
| 1시간 미만 | 노랑 |
| 이상 | 흰색 |
| 꺼짐 | 회색 |
| 완료 (한 번, 발화 후) | 연초록 |
| 확인됨 | 연초록 |

---

## 토스트 팝업 (NotificationPopup)

- 우하단 슬라이드인 애니메이션
- 알람: `✔ 확인` 버튼으로 즉시 확인 처리
- 타이머: 자동 닫힘 (10초)

---

## 항상 위 (topmost)

헤더 `📌` 클릭 → 파란 배경으로 활성 표시, 다시 클릭 시 해제.
미니 모드에서도 상태 유지.

---

## 데이터 스키마

### alarm_data.json

```json
{
  "next_id": 3,
  "alarms": [
    {
      "id": 1,
      "time": "08:00",
      "label": "기상",
      "repeat": "매일",
      "enabled": true,
      "confirmed": false,
      "confirmed_date": "2026-04-13",
      "fired_dates": []
    }
  ]
}
```

| 필드 | 설명 |
|------|------|
| `time` | `"HH:MM"` 24시간 형식 |
| `repeat` | `"한 번"` `"매일"` `"평일(월~금)"` `"주말(토~일)"` |
| `enabled` | 알람 활성 여부 |
| `confirmed` | 수동 확인 체크 여부 |
| `confirmed_date` | 확인한 날짜 `"YYYY-MM-DD"` — `confirmed=true` 인 경우에만 존재 |
| `fired_dates` | 발화한 날짜 목록, "한 번" 알람 중복 방지용 |

---

## 클래스 구조

```
AlarmClockApp
├── AlarmTab        (카드 목록 CRUD)
├── TimerTab        (카운트다운)
├── StopwatchTab    (스톱워치)
└── AlarmNotifier   (daemon 스레드, 10초 주기)

팝업:
  AlarmEditorDialog   (알람 추가/수정, always-on-top)
  NotificationPopup   (토스트, 슬라이드인)
```

### AlarmNotifier 체크 로직

1. `enabled` 확인
2. **반복 알람** `confirmed=True` 이면:
   - `confirmed_date != today` → `confirmed` 자동 해제
   - `confirmed_date == today` + 현재 시각 > 알람 시각 → `confirmed` 자동 해제
3. `confirmed=True` 이면 알람 울리지 않음
4. 현재 시각 `HH:MM` == 알람 `time` ?
5. 오늘 이미 발화(`fired_today` set) ?
6. 반복 조건 충족 ?
7. → `root.after(0, _notify)` 로 UI 스레드에서 팝업 생성

### 깜빡임 관리

```python
self._blink_after_ids = []   # after ID 목록
# _refresh_mini() 진입 시 전부 cancel 후 clear
# _start_blink() 에서 toggle마다 새 ID append
```

---

## 수정 시 체크리스트

| 작업 | 확인 항목 |
|------|-----------|
| 알람 필드 추가 | `AlarmEditorDialog` 입력 UI + `_save()` + `DEFAULT_ALARM` + 스키마 |
| 반복 조건 추가 | `AlarmNotifier._check_repeat()` + `AlarmEditorDialog` Combobox 선택지 |
| 미니 모드 행 변경 | `_make_mini_row()` + `_refresh_mini()` after ID 목록 초기화 확인 |
| 토스트 팝업 수정 | `NotificationPopup` + `_notify()` 호출부 양쪽 확인 |
| `confirmed` 로직 변경 | `AlarmTab._check()` + `AlarmNotifier` 자동 해제 조건 동시 수정 |

---

## 연관 파일

- `alarm_data.json` — 런타임 데이터 (`.gitignore` 제외)
- `tool_hub.pyw` — 전역 단축키로 앱 실행
