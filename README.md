# SI WorkTools

Windows 업무 환경을 위한 Python Tkinter 기반 업무 도구 모음.
**도구 허브(tool_hub.pyw)** 하나로 모든 도구를 실행·관리한다.

---

## 도구 목록

| 단축키 | 도구 | 설명 |
|--------|------|------|
| Ctrl+Alt+1 | 📅 데일리 스크럼 | 스탠드업 기록 · 무드미터 |
| Ctrl+Alt+2 | ✉️ 이메일 템플릿 | 변수 치환 이메일 관리 |
| Ctrl+Alt+3 | 📦 파일 배치 이동기 | 폴더구조 유지 배치 복사 |
| Ctrl+Alt+4 | ✏️ 파일명 변경기 | 문자열 제거 일괄 변경 |
| Ctrl+Alt+5 | 💬 빠른 문구 | 자주 쓰는 문구 즉시 복사 |
| Ctrl+Alt+6 | 🗂️ 작업 관리 | 일정·메모·알림 통합 작업 관리 |
| Ctrl+Alt+7 | ⏰ 알람 설정기 | 알람·타이머·스톱워치 |

---

## 요구사항

- Python 3.9+
- 패키지 설치:

```bash
pip install tkcalendar pystray Pillow keyboard
```

---

## 실행 방법

### 도구 허브 (권장)
```bash
pythonw tool_hub.pyw
```
시스템 트레이에 상주하며, 단축키 또는 카드 클릭으로 각 도구 실행.

### 개별 실행
```bash
python task_manager.py
pythonw alarm_clock.pyw
pythonw daily_scrum.pyw
# ...
```

### 자동 시작 설정
도구 허브 `⚙ 설정` → "Windows 시작 시 자동 실행" 체크.

---

## 파일 구조

```
.
├── tool_hub.pyw              # 도구 허브 (메인 런처)
├── hub_config.json           # 허브 설정 (도구 목록, 단축키, 배지 조건)
│
├── task_manager.py           # 작업 관리
├── alarm_clock.pyw           # 알람 설정기
├── daily_scrum.pyw           # 데일리 스크럼
├── email_template.pyw        # 이메일 템플릿
├── quick_phrases.py          # 빠른 문구
├── file_batch_mover.py       # 파일 배치 이동기
├── file_rename/
│   └── rename_tool.py        # 파일명 변경기
│
├── docs/                     # 도구별 상세 문서 + 개발 컨텍스트
│   ├── _patterns.md          # 공통 코드 패턴 레퍼런스
│   ├── _changes.md           # 변경 이력 로그
│   ├── tool_hub.md
│   ├── task_manager.md
│   ├── alarm_clock.md
│   ├── daily_scrum.md
│   ├── email_template.md
│   ├── quick_phrases.md
│   ├── file_batch_mover.md
│   └── file_rename.md
│
└── CLAUDE.md                 # AI 보조 개발 가이드 (탐색 허브)
```

> **런타임 데이터 파일** (`*_data.json`, `daily_scrum_history/` 등)은 `.gitignore`로 제외됨.

---

## 새 도구 추가 방법

1. 도구 스크립트 작성 (`.py` 또는 `.pyw`)
2. `hub_config.json` → `tools` 배열에 항목 추가:

```json
{
  "id": "my_tool",
  "name": "내 도구",
  "description": "도구 설명",
  "icon_emoji": "🔧",
  "launch": { "type": "py", "path": "my_tool.py" },
  "hotkey": "ctrl+alt+8",
  "badge_check": null
}
```

3. 도구 허브 재시작.

---

## 문서

각 도구의 상세 사양은 [`docs/`](./docs/) 폴더 참고.
