---
doc_id: JSD-DOM-002
type: DOM
title: 보증금지킴 — 클래스 명세
status: draft
upstream: [JSD-DOM-001, JSD-API-001, JSD-API-002, JSD-UI-001, JSD-INFRA-001]
---

# 클래스 명세: 보증금지킴 (deposit-guard)

---

## 0. 이 문서가 다루는 것

도메인 모델의 개념을 **코드 구조**로 옮긴다. 폴더 배치, 엔티티 클래스, 서비스의 책임과 메서드 이름까지. 테이블·컬럼·인덱스 정의는 ERD·DD(ERD·DD 문서)가 맡는다.

**3줄 요약.** 도메인 모델의 코드 도메인 아홉 개가 `app/domains/` 아래 폴더 아홉 개가 된다. 검토 하나의 흐름은 `review`가 쥐고, 에이전트 루프(`review/service_agent.py`)가 도구 9종을 각 도메인 서비스로 나눠 보낸다. 등급과 수치는 `rules`의 순수 함수가 내고, 모델로 가는 값은 루프와 의견서 작성 두 곳만 지나며 그 전에 이름이 가려진다.

**클래스 세 종류와 이 문서의 범위**

| 종류 | 역할 | 우리 구조 | 정의하는 곳 |
|---|---|---|---|
| Entity | 데이터를 갖는 것 | `domains/*/models.py` | 이 문서 2장 + ERD·DD |
| Control | 유스케이스 흐름을 조율하는 것 | `domains/*/service*.py`, `core/health.py` | 이 문서 3장(의존)·4장(시그니처·다이어그램) |
| Boundary | 바깥과 만나는 것 | `domains/*/router.py`, `jobs.py`, 에이전트 도구 인자 모델(`review/schemas.py`) | API 명세·화면 명세. 3.1에서 Control과의 연결만 |

**전제 (앞 단계에서 결정)**
- 도메인 경계는 [[JSD-DOM-001]] 5.1 표 그대로다. 개념 하나는 도메인 하나에만 산다
- 도메인끼리는 ID와 값으로만 주고받는다. 다른 도메인의 ORM 객체를 들고 다니지 않는다 ([[JSD-DOM-001]] 5.2)
- ORM 모델은 저장 형태다. 규칙은 서비스에 둔다. `rules`는 저장소·네트워크·모델을 부르지 않는다
- 등급과 수치는 코드가 정한다. 생성 문장은 옮겨 적을 뿐이다 ([[JSD-PRD-001#R6]] [[JSD-PRD-001#R10]])
- 올린 파일은 디스크에 쓰지 않는다. 이름·주민번호·상세 주소는 로그·모델·공유본에 닿지 않는다 ([[JSD-INFRA-001#C2]] [[JSD-PRD-001#N1]])
- 로그인이 없다. 검토는 추측할 수 없는 `review_id`로만 찾는다. 바깥에 보이는 ID(`review_id`·`document_id`·`message_id`)는 UUID 문자열이고 그 행의 기본키다. 바깥에 안 보이는 행은 정수 기본키다
- 한도: 도구 20회, 질문 5회, 되묻기 차례마다 도구 5회, 파일 10MB·20쪽, IP 하루 5건(예시 제외), 보관 24시간, 공유 링크 7일 ([[JSD-PRD-001#R10]] [[JSD-PRD-001#N2]] [[JSD-API-002]] 4장)

**본문은 언어 중립으로 쓴다.** FastAPI·SQLAlchemy로 어떻게 옮기는지는 6장 부록에 둔다. 다만 폴더와 파일 이름은 파이썬 기준이다.

---

## 1. 폴더 구조

저장소 `deposit-guard` 하나에 **백엔드와 프런트엔드를 나눠 둔다.** 명세와 예시 등기부는 둘 다 쓰므로 루트에 둔다.

**기본형과 다른 점, 그리고 왜.** 싱크독 작성 규약(SYNC-STD-001) 1.9의 기본형을 따른다. 입구가 브라우저 REST 하나이고 배포 단위가 하나라([[JSD-INFRA-001#C6]]) 라우터는 도메인 폴더 안에 둔다. 다른 점은 다섯이다.
- **빠진 파일.** `rules`에는 `crud`·`models`가 없다 — 판정 개념은 값이고 남기는 것은 부른 쪽이다([[JSD-DOM-001]] 5.2). `sample`에도 없다 — 예시 3건은 저장소에 커밋한 파일이다([[JSD-INFRA-001]] 3장 예시 파일). `lookup`·`gate`에는 `router`가 없다 — [[JSD-API-001]]의 16개 경로 중 이 둘이 받는 것이 없다. `gate`는 `schemas`도 없다 — 주고받는 타입이 `shared/types.py`의 것뿐이다
- **더한 파일.** `review/service_agent.py`·`registry/service_parse.py`는 서비스가 길어 기능 단위로 나눈 것이고 계층 이름을 유지한다. `rules/criteria.py`·`report/catalog.py`는 로직 없는 상수다 — 판정 기준 페이지는 코드 상수를 그대로 내려보내야 하고([[JSD-UI-001#UI-4]] 규칙) 할 일·특약 문구는 출처와 함께 한곳에 있어야 고친다
- **`app/jobs.py`.** 배치 명령의 입구다([[JSD-INFRA-001]] 8장). 두 번째 입구지만 서비스 메서드를 부르기만 하고 REST와 따로 쓰는 절차가 없으므로 라우터를 도메인 밖으로 내지 않는다
- **`core/health.py`.** `HealthService`는 도메인 모델의 코드 도메인 표에 없고 앱 자신의 DB 연결만 본다. 도메인 폴더를 새로 만들지 않고 `core`에 둔다
- **`shared/types.py`.** 두 도메인 이상이 쓰는 열거형과, 개념이 아니면서 여러 도메인을 오가는 타입(`Upload` `Error` `Limits` `FileCheck` `ParsedDocument`)만 둔다. 개념의 DTO는 그 개념이 사는 도메인의 `schemas.py`에 있다 — 개념 하나는 도메인 하나에만 산다([[JSD-DOM-001]] 5.1). 파일 자리는 2.8 표의 `자리` 열이다

```
deposit-guard/                  저장소 = 프로젝트
├── backend/                    파이썬 3.12. FastAPI 앱 하나 (INFRA 3장)
│   ├── app/                    임포트 패키지 — from app.domains.review …
│   ├── tests/                  app/ 구조를 그대로 따른다
│   ├── alembic/ · alembic.ini  마이그레이션
│   └── pyproject.toml · uv.lock
│
├── frontend/                   React 18 + TypeScript + Vite + Tailwind. 빌드 → backend/app/static
│
├── assets/samples/             가상 등기부 PDF 3건 + samples.json(목록·기본 조건·기대 등급). 이미지에 함께 담는다
├── docs/specs/                 명세 원본. 백엔드·프런트엔드가 같이 본다
├── Dockerfile · docker-compose.yml   배치 (INFRA 2장). 프런트를 빌드해 백엔드 이미지에 담는 2단계. compose는 app·db
├── .env.example               필요한 환경 변수의 이름만. 값은 비운다. .env는 커밋하지 않는다
├── .gitignore · .dockerignore
└── CLAUDE.md · README.md       에이전트용 · 사람용 (INFRA C11)
```

**backend/app/ 안**

```
app/
├── main.py                 앱 조립. 도메인 라우터 등록 · 검토 경로 공통 의존성 · 업로드 스풀 크기 · 정적 파일과 SPA 폴백 · /health
├── jobs.py                 배치 명령 입구. python -m app.jobs <명령> (4.15)
│
├── core/                   도메인에 속하지 않는 것. 도메인을 import하지 않는다
│   ├── config.py           환경 변수(API 키·모델 ID·DB URL·앱 비밀키)와 한도 상수 LIMITS
│   ├── db.py               비동기 엔진·세션. 예외 문자열에 바인드 값을 싣지 않는다(4.14)
│   ├── errors.py           AppError(code) 하나, 코드 → HTTP 상태 표, 에러 봉투 핸들러 (API-001 2장)
│   ├── logging.py          JSON 로그. 주민번호 형태 숫자를 지우는 필터 ·