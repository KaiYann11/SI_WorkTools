# 데일리 스크럼 (daily_scrum.pyw)

매일 스탠드업 미팅 내용을 기록하고 히스토리를 관리하는 도구.

---

## 기능

- 오늘 할 일 / 완료한 일 / 이슈 입력
- 무드미터 (팀 컨디션 기록)
- 날짜별 히스토리 조회
- 오늘 기록이 없으면 도구 허브 카드에 `!` 배지 표시

---

## 데이터

히스토리 파일: `daily_scrum_history/YYYY-MM-DD.json`

```json
{
  "date": "2026-04-09",
  "mood": 4,
  "yesterday": "완료한 작업 내용",
  "today": "오늘 할 작업",
  "issues": "이슈 및 블로커"
}
```

| 필드 | 설명 |
|------|------|
| `date` | `"YYYY-MM-DD"` |
| `mood` | 1~5 정수 (무드미터) |
| `yesterday` | 어제 완료 내용 |
| `today` | 오늘 계획 |
| `issues` | 이슈/블로커 |

---

## 배지 조건

`hub_config.json`:
```json
"badge_check": { "type": "daily_scrum_json", "history_dir": "daily_scrum_history" }
```
오늘 날짜 파일(`YYYY-MM-DD.json`)이 없으면 `!` 표시.

---

## 수정 시 체크리스트

| 작업 | 확인 항목 |
|------|-----------|
| 입력 필드 추가 | `_save()` 직렬화 + 히스토리 로드/표시 로직 + JSON 스키마 |
| 무드미터 단계 변경 | UI Spinbox/Combobox 범위 + 저장값 범위 검증 |
| 히스토리 파일 경로 변경 | `hub_config.json` `history_dir` 필드와 동기화 필수 |

---

## 연관 파일

- `daily_scrum_history/` — 런타임 데이터 (`.gitignore` 제외)
- `tool_hub.pyw` — `daily_scrum_json` 배지 체크로 이 디렉토리 참조
