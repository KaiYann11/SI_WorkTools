# 파일명 변경기 (file_rename/rename_tool.py)

특정 문자열을 제거하거나 치환하여 파일명을 일괄 변경하는 도구.

---

## 기능

- 폴더 선택 후 파일 목록 표시
- 제거할 문자열 또는 치환 패턴 입력
- 변경 전/후 미리보기
- 일괄 적용 (하위 폴더 포함 옵션)

---

## 실행

```bash
python file_rename/rename_tool.py
```

허브 단축키: `Ctrl+Alt+4`

---

## 수정 시 체크리스트

| 작업 | 확인 항목 |
|------|-----------|
| 패턴 방식 변경 (문자열→정규식) | UI 입력 필드 설명 텍스트 + 미리보기 로직 동시 수정 |
| 하위 폴더 처리 변경 | `os.walk` vs `os.listdir` 분기 확인 |
| 파일 필터 추가 | 확장자 Combobox/Entry + 필터 적용 로직 |

---

## 연관 파일

- `hub_config.json` — `launch.path: "file_rename/rename_tool.py"` 참조
- `file_rename/.claude/` — 서브 디렉토리 전용 Claude 설정 (있을 경우)
