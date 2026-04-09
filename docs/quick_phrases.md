# 빠른 문구 (quick_phrases.py)

자주 사용하는 문구를 등록하고 클립보드에 즉시 복사하는 도구.

---

## 기능

- 문구 추가/편집/삭제
- 카테고리 분류
- 클릭 한 번으로 클립보드 복사
- 검색 필터

---

## 데이터

저장 파일: `quick_phrases.json`

```json
{
  "phrases": [
    {
      "id": 1,
      "category": "인사",
      "title": "수고 인사",
      "content": "수고하셨습니다."
    }
  ]
}
```

> `quick_phrases.json`은 사용자 데이터로 `.gitignore` 제외.
