# 지금(가칭) — Agent & Skills 제안서

- **문서 버전:** v0.1
- **작성일:** 2026-08-24
- **문서 목적:** `지금` 서비스에서 Agent를 어디에 적용하는 것이 타당한지, Agent가 어떤 책임을 가져야 하는지, 그리고 이를 지원하기 위해 어떤 Skills를 설계할 수 있는지 개략적으로 제안한다.
- **범위:** 상세 구현, Prompt, Framework, Tool Schema, Model 선정은 본 문서의 범위에서 제외한다.

---

## 1. 제안 요약

`지금`은 모든 기능을 하나의 LLM Agent에 맡기는 서비스로 설계해서는 안 된다.

이 서비스의 핵심은 시간 계산, Route 유효성, Retry, Permission, State Transition과 같이 **결과가 재현 가능하고 검증 가능해야 하는 Deterministic Logic**이다.

따라서 Agent는 다음 역할에 집중하는 것이 타당하다.

> **사용자의 자연어·Calendar·현재 Journey 상태를 이해하고, 필요한 Domain Skill을 호출해 다음 행동을 Orchestration하며, 결과를 사용자에게 이해하기 쉽게 설명하는 역할**

즉 Agent는 "교통 알고리즘 자체"가 아니라 **Orchestration / Interpretation Layer**에 가깝다.

---

## 2. 권장 Agent 구조

초기 MVP에서는 여러 개의 복잡한 Multi-Agent 구조보다 **1개의 Orchestrator Agent + Domain Skills** 구조를 권장한다.

```text
사용자 / Calendar / App Event
            ↓
     Mobility Orchestrator
            ↓
   필요한 Skill 선택/호출
            ↓
┌───────────┼─────────────┐
│           │             │
Intent    Deadline      Routing
Skill      Skill         Skill
│           │             │
└───────────┼─────────────┘
            ↓
       Monitoring
          Skill
            ↓
       Replanning
          Skill
            ↓
       결과 설명
```

장점:

- 상태 추적이 단순하다.
- Agent 간 충돌이 적다.
- 테스트하기 쉽다.
- 대학생 팀 규모에서 운영 가능하다.
- 이후 필요 시 특정 Domain만 독립 Agent로 분리할 수 있다.

---

## 3. Core Agent 제안

## 3.1 Mobility Orchestrator Agent

### 역할

서비스 전체 Flow에서 **현재 무엇을 해야 하는지 결정하는 상위 Coordinator**다.

예:

- 사용자의 자연어를 구조화할지
- Calendar 일정 Confirmation이 필요한지
- 새로운 Deadline 계산이 필요한지
- Monitoring을 시작할지
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

Agent는 최소 다음 Context를 이해할 수 있어야 한다.

### User Context
- 자주 가는 장소
- Arrival Preference
- Walking Preference
- Taxi 허용 여부
- 선택적 Taxi 최대비용
- Permission 상태

### Journey Context
- 출발지
- 목적지
- Deadline
- Target Arrival Time
- Recommended Leave Time
- Current Route
- Current Journey State
- Replan Count

### Environment Context
- 현재 시간
- 현재 위치 또는 수동 출발지
- Calendar Event
- Routing 결과
- 교통 상태 변화
- Notification 상태

Agent가 직접 모든 값을 계산하는 것이 아니라 **Domain Service/Skill 결과를 받아 Context로 관리**한다.

---

## 5. 권장 Skill 구성

다음 Skills는 초기 설계에서 개별 책임으로 분리하는 것이 타당하다.

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

Agent는 이 Skill 결과에서 모호성이 높으면 Confirmation UI를 요청한다.

---

## 5.2 `interpret_calendar_event`

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

- 저장된 장소 Mapping
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

## 5.9 `monitor_journey_state`

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

## 5.10 `detect_departure`

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

## 5.11 `detect_arrival`

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

- 자동 Replan 최대 3회
- 3회 초과 시 사용자 Confirmation 필요
- Route Deviation 시 자동 실행 금지
- Route Deviation은 사용자 승인 후 Replan

Agent는 이 정책을 임의 변경해서는 안 된다.

---

## 5.13 `search_taxi_transit_hybrid`

### 목적

순수 대중교통이 불가능하고 사용자가 Taxi를 허용한 경우 Taxi + Transit 대안을 검색한다.

최적화 기준:

- 최대 Taxi 비용 입력 시 Cost Constraint 적용
- 미입력 시 Taxi 사용량/거리/예상 비용 최소화

---

## 5.14 `evaluate_notification`

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

### Monitoring Engine
- GPS Event
- Checkpoint
- State Transition
- Background Job

### Notification Engine
- Push 발송
- Notification Permission
- Category Preference

### Calendar Integration
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

### Case B — Calendar 일정 감지

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
5. Monitoring 등록
```

---

### Case D — Journey 실패

```text
monitor_journey_state
→ MISSED_CONNECTION
        ↓
replan_journey
        ↓
Replan Count 확인
        ↓
Alternative 전달
```

3회 초과:

```text
MANUAL_REPLAN_REQUIRED
→ 사용자에게 계속 찾을지 질문
```

---

### Case E — Route 이탈

```text
monitor_journey_state
→ ROUTE_DEVIATED
        ↓
기존 Monitoring 중단
        ↓
Agent:
"현재 위치에서 다시 계산할까요?"
        ↓
사용자 승인
        ↓
replan_journey
```

---

## 8. Agent와 App State Machine의 관계

Agent가 State를 자유롭게 만들면 안 된다.

Agent는 정의된 State Machine 안에서만 행동한다.

예:

```text
SCHEDULED
→ MONITORING
→ READY_TO_LEAVE
→ DEPARTED
→ IN_TRANSIT
→ ARRIVED
```

Exception:

```text
LATE_RISK
ROUTE_AT_RISK
MISSED_CONNECTION
ROUTE_DEVIATED
REPLANNING
MANUAL_REPLAN_REQUIRED
```

Agent의 역할은:

- 현재 State에 맞는 Skill 호출
- 필요한 사용자 Confirmation 요청
- 결과 설명

State Transition 자체는 Backend Domain Logic에서 검증한다.

---

## 9. 권장 구현 우선순위

### Phase 1 — Agent 없는 Core Prototype

먼저 Agent 없이 다음 Domain Logic이 동작해야 한다.

- Route Search
- Deadline Calculation
- Safety Buffer
- Last Feasible Journey
- Monitoring State
- Replanning

이 단계가 실패하면 Agent를 넣어도 제품은 성립하지 않는다.

---

### Phase 2 — Input Agent

추가:

- Natural Language Parsing
- Place Resolution 보조
- Calendar Interpretation

목표:
사용자가 구조화된 Form을 직접 입력해야 하는 부담을 줄인다.

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

## 10. Multi-Agent 확장 여부

초기에는 권장하지 않는다.

향후 서비스 규모가 커지면 다음처럼 분리 가능하다.

### Candidate Agent

- **Input Agent**
  - 자연어 / Calendar

- **Journey Planning Agent**
  - Deadline / Route / Last Journey

- **Monitoring Agent**
  - 상태 변화 / Risk

- **Recovery Agent**
  - Replanning / Taxi Hybrid

하지만 MVP에서는 Agent 간 Hand-off와 Context 동기화 비용이 제품 가치보다 클 가능성이 높다.

따라서:

> **MVP: Single Orchestrator + Skills**

를 권장한다.

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
- Calendar 일정 관리 시작
- Route Deviation 후 Replan
- Replan 3회 초과
- Permission 관련 결정

### 11.5 Observability

각 Skill 호출과 결과를 추적할 수 있어야 한다.

특히:

- 어떤 Route를 선택했는가
- 어떤 Safety Buffer가 적용됐는가
- 왜 Notification을 보냈는가
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

## 14. 최종 제안

### MVP 권장 구조

```text
Mobile App
   ↓
Backend API
   ↓
Mobility Orchestrator Agent
   ↓
┌────────────────────────────┐
│ parse_mobility_request     │
│ interpret_calendar_event   │
│ resolve_place              │
│ calculate_deadline         │
│ search_transit_routes      │
│ find_last_feasible_journey │
│ apply_safety_buffer        │
│ calculate_leave_time       │
│ monitor_journey_state      │
│ detect_departure           │
│ detect_arrival             │
│ replan_journey             │
│ search_taxi_transit_hybrid │
│ evaluate_notification      │
│ explain_recommendation     │
└────────────────────────────┘
   ↓
Deterministic Domain Services
   ↓
Routing / Public Data / Calendar / Push / Location
```

핵심은 Agent를 서비스의 "두뇌"처럼 포장하는 것이 아니라, **정확한 Domain Logic을 연결하는 Orchestrator**로 제한하는 것이다.

`지금`의 경쟁력은 Agent 자체가 아니라 다음 조합에서 나온다.

> **Deadline Engine + Last Journey Logic + Monitoring + Replanning + Agent-assisted UX**

이 구조를 유지하면 AI가 없어도 핵심 서비스가 동작하고, AI를 추가했을 때 사용성과 자동화 수준이 올라가는 안정적인 아키텍처를 만들 수 있다.
