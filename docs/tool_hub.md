# 도구 허브 (tool_hub.pyw)

모든 업무 도구를 한 곳에서 실행·관리하는 메인 런처.

---

## 기능

- 등록된 도구를 카드 그리드로 표시 및 클릭 실행
- 전역 단축키로 어느 화면에서든 도구 직접 실행
- 시스템 트레이 상주 (창 닫아도 종료 안 됨)
- 배지(`!`) 표시: 긴급/마감초과 작업, 미작성 데일리 스크럼
- Windows 시작 시 자동 실행 옵션
- 단일 인스턴스 보장 (Named Mutex)

---

## 설정 파일: hub_config.json

```json
{
  "tools": [ ... ],
  "settings": {
    "autostart": false,
    "start_minimized": false
  }
}
```

### tools[] 항목 구조

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 고유 식별자 |
| `name` | string | 카드에 표시할 이름 |
| `description` | string | 카드 설명 텍스트 |
| `icon_emoji` | string | 카드 이모지 아이콘 |
| `launch.type` | `py` \| `pyw` \| `exe` | 실행 방식 |
| `launch.path` | string | BASE_DIR 기준 상대 경로 |
| `hotkey` | string | 전역 단축키 (`ctrl+alt+N`) |
| `badge_check` | object \| null | 배지 조건 설정 |

### badge_check 타입

**daily_scrum_json**: 오늘 날짜 히스토리 파일이 없으면 `!`
```json
{ "type": "daily_scrum_json", "history_dir": "daily_scrum_history" }
```

**task_urgent**: 긴급 우선순위 또는 마감 초과 미완료 작업이 있으면 `!`
```json
{ "type": "task_urgent", "data_file": "task_manager_data.json" }
```

---

## 클래스 구조

```
HubApp              (메인 Tk 창)
TrayManager         (pystray 트레이 아이콘)
HotkeyManager       (keyboard 라이브러리 전역 단축키)
SettingsPanel       (설정 Toplevel)
```

---

## 새 도구 등록

1. 도구 스크립트를 `BASE_DIR`에 배치
2. `hub_config.json` → `tools[]`에 항목 추가
3. 도구 허브 재시작 (트레이 → 종료 후 재실행)
