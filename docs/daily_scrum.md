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

---

## 배지 조건

`hub_config.json`:
```json
"badge_check": { "type": "daily_scrum_json", "history_dir": "daily_scrum_history" }
```
오늘 날짜 파일(`YYYY-MM-DD.json`)이 없으면 `!` 표시.
