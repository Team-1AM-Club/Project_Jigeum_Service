# 지금(가칭) — MCP 서비스 Agent & Skills 제안서

- **문서 버전:** v0.2 — MCP 제공 방향 반영 (파일명 유지)
- **개정일:** 2026-09-14
- **작성일:** 2026-08-24
- **문서 목적:** `지금` 서비스에서 Agent를 어디에 적용하는 것이 타당한지, Agent가 어떤 책임을 가져야 하는지, 그리고 이를 지원하기 위해 어떤 Skills를 설계할 수 있는지 개략적으로 제안한다.
- **범위:** 상세 구현, Prompt, Framework, Tool Schema, Model 선정은 본 문서의 범위에서 제외한다.

---

> **현재 서비스 개발 방향 — 2026-09-14:** 지금은 **MCP로 제공하는 서비스**다. 별도 제품 화면·설치형 클라이언트를 개발하지 않는다. 본인은 MCP 도구·Hermes 연결·확인/선택 흐름·시연을, 친구는 FastAPI·서비스 Agent·교통 데이터·계산·배포를 담당한다. Hermes + Solar Pro4는 개발·시연용 MCP 클라이언트다. 현재 구현 범위와 완료 기준은 IDEA.md를 따른다.

본 문서의 Domain Skill 이름은 내부 책임의 설계 명칭이며 실제 구현된 SKILL.md나 외부 MCP 도구 목록을 뜻하지 않는다. 실제 Skill 원본은 .hermes/skills, 역할은 agent_specs, 현재 구현 범위는 IDEA.md를 따른다. Calendar·GPS·자동 감시·알림·택시 최적화는 후속 기능이다.

## 1. 제안 요약

`지금`은 모든 기능을 하나의 LLM Agent에 맡기는 서비스로 설계해서는 안 된다.

이 서비스의 핵심은 시간 계산, Route 유효성, Retry, Permission, State Transition과 같이 **결과가 재현 가능하고 검증 가능해야 하는 Deterministic Logic**이다.

따라서 Agent는 다음 역할에 집중하는 것이 타당하다.

> **사용자가 확인한 이동 조건과 현재 선택 계획을 바탕으로 필요한 SubAgent·Skill·코드 도구를 조정하고, 검증된 결과를 MCP를 통해 전달하는 역할**

즉 Agent는 "교통 알고리즘 자체"가 아니라 **Orchestration / Interpretation Layer**에 가깝다.

---

## 2. MCP 제공과 서비스 Agent 구조

~~~text
사용자
  ↕ Hermes + Solar Pro4 — 입력·질문·최종 확인·후보 선택
지금 MCP 서버 — 도구 5개·HTTP 연결·결과/오류 전달
  ↕
기존 FastAPI
  ↓
MainAgent — 요청 분류·작업 배정·결과 취합
  ├─ TripIntakeAgent → resolve-trip-details, schedule-ready
  ├─ DeparturePlannerAgent → leave-by, maginot-line, route-risk-checker
  └─ RecoveryAgent → plan-b-recovery, route-risk-checker
  ↓
검증 가능한 도메인 코드·교통 데이터
~~~

Hermes는 개발·시연용 MCP 클라이언트이며 서비스 내부 MainAgent와 구분한다. MCP 계층에 같은 Agent 체계나 교통 계산을 중복 구현하지 않는다. 하나의 SubAgent가 여러 Skill을 사용할 수 있다. 이 구조는 개발용 코딩 에이전트 분업과 별개다.

---

## 3. Core Agent 제안

## 3.1 MainAgent (Mobility Orchestrator)

### 역할

서비스 전체 Flow에서 **현재 무엇을 해야 하는지 결정하는 상위 Coordinator**다.

예:

- 사용자의 자연어를 구조화할지
- 이동 조건의 사용자 최종 확인이 필요한지
- 새로운 Deadline 계산이 필요한지
- 사용자 요청 재탐색을 진행할 조건이 확인됐는지
- 기존 Journey가 깨졌을 때 Replanning을 호출할지
- 사용자 승인 없이 진행하면 안 되는 상태인지

### 하지 말아야 할 것

- 직접 막차시간 계산
- 직접 Route Graph 탐색
- 직접 Safety Buffer 수치 계산
- 직접 Retry 정책 변경
- Permission Rule 임의 변경
- Route Deviation을 감으로 판단

Agent는 **정의된 Skill을 호출하고 상태를 Orchestration**해야 한다.

---

## 4. Agent가 관리할 핵심 Context

### 현재 이동 조건

- 사용자 확인 출발 기준점·목적지·날짜·Deadline
- 도착 여유·버스/지하철 선호·적용한 기본값
- 최종 조건 확인 상태와 해당 조건의 버전·수명
- 필요한 정보가 남아 있는지와 질문할 항목

### 계획과 데이터

- 현재 선택 Plan·option_id와 재탐색 비교용 요약
- 서버 시각·교통 데이터 출처·기준시각
- 조회된 후보·경고·지원 범위·오류·데모 여부
- 이전 선택과 새 후보의 구분

문맥·확인·선택 상태의 소유권·저장 위치·수명은 구현 전에 합의한다. 서버가 과거 대화를 영구 보존한다고 가정하지 않는다. 저장된 집 주소나 개인 선호가 없으면 필요한 최소 정보를 다시 확인한다.

Agent는 Domain Service·코드 도구의 결과를 받아 Context로 다룬다. Taxi 비용·GPS 위치 스트림·Calendar·알림 상태는 해당 후속 기능을 승인해 도입하기 전까지 필수 Context가 아니다.

---

## 5. 권장 Skill 구성

아래는 내부 기능의 책임 분리 제안이다. 현재 핵심은 입력·장소·Deadline·경로·막차·Buffer·재탐색·설명이며, 후속 항목은 본문 제목에 표시한다. 이 목록을 외부 MCP 도구 15개로 그대로 노출하지 않는다.

---

## 5.1 `parse_mobility_request`

### 목적

사용자 자연어에서 이동 관련 Intent와 Constraint를 구조화한다.

입력 예:

```text
"오늘 11시 반까지 집 가야 하는데 버스랑 지하철로 가고 싶어"
```

출력 개념:

- origin
- destination
- arrival deadline
- transport preference
- via
- ambiguity
- confidence

### Agent와의 관계

Agent는 미확정 필드를 구조화해 반환하고 Hermes 대화에서 필요한 확인 질문을 전달한다.

---

## 5.2 `interpret_calendar_event` — 후속 확장, 현재 비적용

### 목적

Calendar Event가 실제 이동이 필요한 일정인지 해석하고, 장소와 Deadline 후보를 추출한다.

예:

```text
19:00 회식
장소: 강남
```

결과:

- 이동 일정 가능성
- 목적지 후보
- Confirmation 필요 여부

### 주의

자동으로 Monitoring을 시작하지 않는다.  
정책상 사용자의 `관리하기` 승인이 필요하다.

---

## 5.3 `resolve_place`

### 목적

"잠실", "집", "학교", Calendar의 불명확한 장소 등을 실제 Route 계산 가능한 Location/POI로 해석한다.

### 주요 기능

- 사용자 확인 장소 후보 Mapping. 저장된 장소가 존재한다고 가정하지 않음
- POI 후보 반환
- Ambiguity 표시
- 사용자의 최종 Confirmation 반영

---

## 5.4 `calculate_deadline`

### 목적

사용자의 Appointment Deadline과 Arrival Preference를 기반으로 실제 목표 도착시각을 계산한다.

개념 예:

```text
약속 19:00
사용자 Preference 10분 전
→ Target Arrival 18:50
```

### 구현 성격

LLM Skill이라기보다 Deterministic Domain Skill에 가깝다.

---

## 5.5 `search_transit_routes`

### 목적

외부 Routing Provider를 통해 버스/지하철/도보 Route 후보를 조회한다.

### Agent 관점

Agent는 Provider 자체를 알 필요가 없다.

```text
search_transit_routes(...)
```

라는 공통 Skill만 사용하고 내부 Adapter가 Provider를 결정하도록 한다.

---

## 5.6 `find_last_feasible_journey`

### 목적

주어진 출발지/목적지에서 버스+지하철을 이용해 목적지까지 연결 가능한 마지막 Journey를 계산한다.

### 핵심 검증

- Transit Leg 운행시각
- 환승 가능성
- 마지막 서비스
- 종착역
- 도보 구간
- Safety Buffer 적용 전 Hard Deadline

이 Skill은 `지금`의 핵심 Domain Skill 중 하나다.

---

## 5.7 `apply_safety_buffer`

### 목적

Route 특성에 맞는 Safety Buffer를 계산한다.

MVP:

- 기본 여유
- 환승 유형
- 환승 횟수
- 도보 구간

향후:

- 사용자 개인화

### 원칙

규칙 기반 결과여야 하며 LLM이 임의로 숫자를 정하지 않는다.

---

## 5.8 `calculate_leave_time`

### 목적

Routing 결과, Target Arrival Time, Safety Buffer를 결합해 Recommended Leave Time을 산출한다.

Appointment와 Last Journey 모두에서 사용 가능하도록 설계한다.

---

## 5.9 `monitor_journey_state` — 후속 확장, 현재 비적용

### 목적

현재 Journey가 정상인지 위험한지 판단한다.

입력 개념:

- Current Journey
- Current Time
- Current Location
- Transit Schedule
- Previous Checkpoint

출력 상태 예:

- NORMAL
- ROUTE_AT_RISK
- ROUTE_DEVIATED
- MISSED_CONNECTION
- LATE_RISK
- POSSIBLY_ARRIVED

### 특징

이 Skill은 Agent보다 Domain Logic 비중이 높다.

---

## 5.10 `detect_departure` — 후속 확장, 현재 비적용

### 목적

GPS와 시간 흐름을 기반으로 사용자가 실제로 출발했는지 판별한다.

예:

```text
AT_ORIGIN
→ POSSIBLY_DEPARTED
→ DEPARTED
```

### 보완

사용자의 `[이미 출발했어요]` Override를 별도 Event로 받을 수 있어야 한다.

---

## 5.11 `detect_arrival` — 후속 확장, 현재 비적용

### 목적

목적지 Geofence와 이동 상태를 바탕으로 도착 가능성을 판단한다.

상태:

```text
IN_TRANSIT
→ POSSIBLY_ARRIVED
→ ARRIVED
```

사용자 Manual Override도 지원한다.

---

## 5.12 `replan_journey`

### 목적

기존 Journey가 실패하거나 위험할 때 현재 위치/시간을 기준으로 Alternative Journey를 생성한다.

### 정책 연동

- 현재 MVP는 사용자 요청·확인 후 Replan
- 새 후보를 반환한 뒤 사용자 선택 전에는 기존 계획에 적용하지 않음
- 자동 감시·주기당 3회 재제시는 후속 정책이며 수동 요청 횟수 제한이 아님
- 변경된 출발 기준점·목적지·Deadline은 다시 확인

Agent는 이 정책을 임의 변경해서는 안 된다.

---

## 5.13 `search_taxi_transit_hybrid` — 후속 확장, 현재 비적용

### 목적

순수 대중교통이 불가능하고 사용자가 Taxi를 허용한 경우 Taxi + Transit 대안을 검색한다.

최적화 기준:

- 최대 Taxi 비용 입력 시 Cost Constraint 적용
- 미입력 시 Taxi 사용량/거리/예상 비용 최소화

---

## 5.14 `evaluate_notification` — 후속 확장, 현재 비적용

### 목적

현재 변화가 사용자에게 Push할 만큼 중요한지 판단한다.

입력:

- 기존 Recommended Leave Time
- 새 Recommended Leave Time
- Deadline Type
- 남은 시간
- Risk State

출력:

- notify / silent
- notification severity
- reason

### 원칙

Notification Threshold는 Product Policy 기반 Rule로 관리한다.

---

## 5.15 `explain_recommendation`

### 목적

계산된 결과를 사용자에게 짧고 명확하게 설명한다.

예:

```text
교통 지연으로 출발 권장 시간이 18:27에서 18:22로 변경되었습니다.
5분 일찍 출발하는 것이 좋습니다.
```

또는:

```text
예정했던 환승이 어려워졌습니다.
다음 버스를 이용하면 19:07에 도착할 수 있습니다.
```

이 영역은 LLM 활용 가치가 높다.

---

## 6. Agent가 직접 실행하지 않아야 하는 기능

다음은 별도 Backend Service 또는 Deterministic Engine으로 두는 것이 좋다.

### Deadline Engine
- Target Arrival Time
- Recommended Leave Time
- Hard Deadline
- Retry Counter

### Routing Engine / Adapter
- 외부 Route API
- Provider Failover
- Route Normalization

### Monitoring Engine — 후속 확장
- GPS Event
- Checkpoint
- State Transition
- Background Job

### Notification Engine — 후속 확장
- Push 발송
- Notification Permission
- Category Preference

### Calendar Integration — 후속 확장
- Calendar Permission
- Event Detection
- Conflict Detection

Agent는 이 Engine들을 Tool/Skill 형태로 호출한다.

---

## 7. Agent Invocation이 필요한 대표 상황

### Case A — 자연어 일정

```text
사용자:
"오늘 7시까지 강남역 가야 해"

Agent:
1. parse_mobility_request
2. resolve_place
3. calculate_deadline
4. search_transit_routes
5. apply_safety_buffer
6. calculate_leave_time
7. 결과 설명
```

---

### Case B — Calendar 일정 감지 (후속 확장)

```text
Calendar Event
        ↓
interpret_calendar_event
        ↓
사용자 "관리하기"
        ↓
Deadline 생성
        ↓
Monitoring 시작
```

---

### Case C — 막차

```text
"오늘 막차 타고 집 가려면?"

Agent:
1. destination = 집 resolve
2. find_last_feasible_journey
3. apply_safety_buffer
4. calculate_leave_time
5. 결과·근거 전달 → 사용자 후보 선택
```

---

### Case D — 사용자 요청 재탐색

~~~text
사용자: 환승을 놓쳤어. 다시 찾아줘
        ↓
현재 출발 기준점·유지할 조건 확인
        ↓
사용자 요청 확인 → replan_journey
        ↓
현재 데이터로 계산한 후보·변화량
        ↓
사용자 후보 선택 후 적용
~~~

### Case E — 다른 경로로 이동 중인 경우

사용자가 바뀐 경로를 알리면 현재 출발 기준점을 확인한다. 자동 이탈 감지나 기존 계획 교체를 수행하지 않는다. 사용자가 재탐색을 승인하면 도구를 호출하고 결과 선택을 기다린다.

---

## 8. Agent와 MCP 확인·선택 상태의 관계

Agent가 확인·선택 상태를 임의로 생성하면 안 된다. 현재 흐름은 입력 부족 → 조건 요약 → 최종 확인 → 계산 결과 → 사용자 후보 선택이다. 재탐색은 사용자 요청으로 시작하며 새 결과와 적용은 별개다.

- ready_for_plan=true는 입력 준비 상태이지 사용자 동의가 아니다.
- 모델이 user_confirmed=true를 생성했다는 사실만으로 동의를 검증했다고 보지 않는다.
- 확인 조건·사용자 응답·계산 요청을 결부하고 조건 변경 시 재확인한다.
- 늦게 도착한 응답이나 새 후보가 현재 선택을 덮어쓰지 않도록 코드로 검증한다.
- 이전 문맥을 잃으면 다시 질문하고 자동 복원을 주장하지 않는다.

공개 API의 status는 기존 ok / needs_confirmation / unavailable / error를 유지한다. 확인·선택 상태의 세부 저장 모델은 공동 합의하며, 진행 상태·영구 이력·자동 알림은 현재 범위에서 제외한다.

---

## 9. 권장 구현 우선순위

### Phase 1 — MCP 연결과 검증 가능한 Core

먼저 Hermes의 get_capabilities → MCP → FastAPI 호출을 검증한다. 이어서 AI의 추측 없이 다음 Domain Logic이 동작해야 한다.

- Route Search
- Deadline Calculation
- Safety Buffer
- Last Feasible Journey
- 사용자 확인·선택 상태
- 사용자 요청 Replanning

이 단계가 실패하면 Agent를 넣어도 제품은 성립하지 않는다.

---

### Phase 2 — Input Agent

추가:

- Natural Language Parsing
- Place Resolution 보조
- Calendar Interpretation은 후속 확장

목표:
사용자가 구조화 필드를 모두 직접 작성해야 하는 부담을 줄이되 최종 조건 확인은 유지한다.

---

### Phase 3 — Orchestration Agent

추가:

- 상황별 Skill 선택
- 사용자 Confirmation 관리
- Replanning Orchestration
- 결과 설명

---

### Phase 4 — Personalization

추가 후보:

- 사용자별 Buffer 추천
- 반복 이동 Pattern
- 개인화 Explanation
- Preference 자동 보조

---

## 10. 서비스 Agent 범위와 개발 분업

현재 기준은 MainAgent가 역할별 SubAgent를 지휘하는 구조다. 한 SubAgent가 여러 Skill을 사용할 수 있으며 매 요청마다 모든 Agent·Skill을 실행하지 않는다. 호출 횟수·전체 제한시간·실패 반환 규칙을 정한다.

- 본인: MCP 도구 5개, 백엔드 연결·오류 매핑, Hermes 확인/선택 흐름, 설치·시연.
- 친구: 기존 FastAPI·MainAgent·SubAgent·Skill, 장소·교통 데이터, 코드 계산·재탐색, 테스트·배포.
- 공동: API·MCP 계약, 실제 사용자 확인·문맥·선택 상태의 소유권과 통합 검증.

개발용 Hermes가 도구를 호출한다는 사실과 서비스 내부 SubAgent·Skill이 실제 실행됐다는 증거를 구분한다. 별도 제품 화면 개발 역할은 없다.

---

## 11. Skill 설계 원칙

### 11.1 Single Responsibility

각 Skill은 하나의 명확한 책임을 갖는다.

예:

- `resolve_place`
- `calculate_leave_time`
- `replan_journey`

를 하나의 거대한 `plan_everything` Tool로 합치지 않는다.

### 11.2 Deterministic First

시간, 비용, 상태, Retry는 가능한 한 Deterministic하게 계산한다.

### 11.3 Agent-safe Output

Skill 결과는 Agent가 오해하기 어려운 Structured Output을 제공한다.

예:

```text
status
recommended_leave_time
hard_deadline
risk_level
reason_code
requires_user_confirmation
```

### 11.4 User Confirmation Boundary

다음은 Agent가 자동 진행하지 않는다.

- 모호한 목적지 확정
- 조건 확정 후 계획 계산
- 변경 조건에서 재탐색
- 새 후보를 기존 계획에 적용
- 도구 연결 권한·개인정보 관련 결정

Calendar·자동 재제시 횟수 정책은 해당 후속 기능을 도입할 때 별도로 승인받는다.

### 11.5 Observability

각 Skill 호출과 결과를 추적할 수 있어야 한다.

특히:

- 어떤 Route를 선택했는가
- 어떤 Safety Buffer가 적용됐는가
- 어떤 조건에 사용자가 확인했고 어떤 후보를 선택했는가
- 왜 Replanning을 수행했는가

를 Log로 남길 수 있어야 한다.

---

## 12. Agent Evaluation 제안

Agent 품질은 일반 Chatbot 지표보다 Task Success 기준으로 보는 것이 적절하다.

### 평가 후보

- Intent Parsing Accuracy
- Place Ambiguity Detection Rate
- 불필요한 Confirmation 비율
- 잘못된 자동 확정 비율
- Skill Selection Accuracy
- State-invalid Action Rate
- Replan Policy Violation Rate
- Explanation Accuracy
- Hallucinated Time/Route 비율

가장 중요한 원칙:

> Agent는 실제 Routing/Deadline 결과에 없는 시간이나 경로를 만들어내면 안 된다.

---

## 13. 보안 / 개인정보 관점

Agent Prompt에 불필요한 사용자 이동 History 전체를 노출하지 않는다.

필요한 Context만 최소 단위로 전달한다.

예:

필요:
- 현재 Journey
- 현재 위치
- 사용자 Arrival Preference

불필요:
- 과거 모든 위치 기록
- 다른 Calendar Event 전체 내용
- 마케팅 정보

위치, Calendar 등 민감도가 높은 데이터는 가능한 한 Domain Service에서 처리하고 Agent에는 최소 정보만 전달한다.

---

## 14. 최종 MCP 제공 구조

~~~text
Hermes + Solar Pro4
  ↕
MCP 도구
  get_capabilities · search_places · interpret_trip
  plan_journey · replan_journey
  ↕
FastAPI → MainAgent → 역할별 SubAgent·Skill
  ↓
Deadline / Routing / Last Journey / Buffer / Replanning 코드
  ↓
검증된 장소·교통 데이터
~~~

핵심은 검증 가능한 Domain Logic을 재사용해 MCP로 제공하는 것이다. MCP 도구와 내부 Domain Skill은 일대일 대응이 아니다. Calendar·Push·GPS·Taxi는 현재 필수 연결이 아니다.

> **MCP Interface + Deadline Engine + Last Journey Logic + User-confirmed Replanning + Agent-assisted Conversation**



---

이 구조를 유지하면 AI가 없어도 핵심 서비스가 동작하고, AI를 추가했을 때 사용성과 자동화 수준이 올라가는 안정적인 아키텍처를 만들 수 있다.
