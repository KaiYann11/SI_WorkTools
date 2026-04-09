# 파일 배치 이동기 (file_batch_mover.py)

폴더 구조를 유지하면서 다수의 파일을 배치로 복사/이동하는 도구.

---

## 기능

- 원본 폴더 선택 및 대상 폴더 선택
- 파일 필터 (확장자, 이름 패턴)
- 폴더 구조 유지 복사/이동
- 진행률 표시

---

## 빌드

PyInstaller로 단일 실행파일로 빌드:

```bash
pyinstaller file_batch_mover.spec
# 결과: dist/file_batch_mover.exe
```

허브에서는 `dist/file_batch_mover.exe`를 직접 실행 (`launch.type: "exe"`).

---

## 허브 설정

```json
{
  "id": "file_batch_mover",
  "launch": { "type": "exe", "path": "dist/file_batch_mover.exe" }
}
```

> `dist/`, `build/` 는 `.gitignore` 제외. 소스(`file_batch_mover.py`, `.spec`)만 관리.
