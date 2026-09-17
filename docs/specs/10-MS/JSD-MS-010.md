---
doc_id: JSD-MS-010
type: MS
title: 보증금지킴 — 미니스펙 SampleService
status: draft
upstream: [JSD-DOM-002, JSD-SEQ-001, JSD-API-001, JSD-UC-001, JSD-PRD-001]
---

# MINISPEC — SampleService

## 0. 이 문서가 다루는 것

`sample/service.py`의 함수 2개. 클래스 명세 [[JSD-DOM-002#SampleService]](4.10)의 시그니처를 함수 안쪽까지 내린 것이다. 저장소에 커밋한 가상 등기부 3건(다가구는 토지 등기부까지 PDF 4장)의 목록과 파일을 내준다([[JSD-PRD-001#R2]]).

형식은 [[JSD-MS-001]]과 같다. 타입(`SampleCase` `Upload`)은 [[JSD-DOM-002]] 2.8이다. 테이블이 없다.

**이 파일이 지키는 것**
- 읽기만 한다. 결과를 미리 계산해 두지 않는다 — 예시도 매번 에이전트가 돈다
- `expected_grade`는 테스트가 쓰는 정답이고 응답에 싣지 않는다
- 파일 경로는 `samples.json`의 `file_name`에서만 만든다. 요청 값으로 경로를 만들지 않는다

**`assets/samples/samples.json`**

```json
[
  { "sample_id": "multi_family_caution", "title": "신축 빌라", "summary": "시세가 없고 근저당이 큰 다세대",
    "region": "서울 강서구", "deposit_manwon": 18000, "contract_type": "jeonse",
    "file_name": "multi_family_caution.pdf", "land_file_name": null, "expected_grade": "caution" }
]
```

`land_file_name`은 다가구 예시의 토지 등기부 PDF다. 질문 카드의 파일 답으로 사용자가 올린다(화면의 예시 내려받기).

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#SampleService.list]] | 예시 카드 목록 |
| [[#SampleService.file]] | 예시 PDF를 업로드처럼 |

---

## 2. 함수

#### SampleService.list 예시 카드 목록

**시그니처** `list() -> list[SampleCase]`

근거: [[JSD-API-001#GET/api/samples]] · [[JSD-UC-001#UC-A2]] 1 · [[JSD-UI-001#UI-1]]

**처리**
1. 처음 부를 때 `samples.json`을 읽어 메모리에 둔다(프로세스 동안)
2. `→ SampleCase` 목록, 파일 순서. 라우터는 내부 필드(`file_name` `expected_grade`)를 빼고 내보낸다

**테스트 관점** 3건 · 응답 JSON에 `expected_grade`·`file_name`이 없다 · 파일이 없는 항목이 json에 있으면 기동 때 실패한다(아래 file 1)

---

#### SampleService.file 예시 PDF를 업로드처럼

**시그니처** `file(sample_id: str) -> Upload`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-SEQ-001#SEQ-18]] · [[JSD-UC-001#UC-A2]] 2~3

**처리**
1. `case = list()`에서 `sample_id`가 같은 것 · if 없음 → `! missing_input(field sample_id)`
2. `data = (assets/samples/ / case.file_name).read_bytes()`
3. `→ Upload(data, media_type "application/pdf", filename = case.file_name)`

**예외** `missing_input` 없는 예시

**테스트 관점** 세 예시 모두 바이트가 온다 · `../../etc/passwd` 같은 값 → missing_input · 같은 예시 두 번 → 같은 해시

---

## 3. 미결사항

- [ ] 예시 PDF 내려받기 경로 — [[JSD-API-001]]에 없다. `static/samples/`로 정적 제공할지([[JSD-DOM-002]] 7장 미결)
