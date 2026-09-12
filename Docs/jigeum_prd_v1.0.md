# 지금(가칭) — MVP Product Requirements Document (PRD)

- **문서 버전:** v1.0
- **작성일:** 2026-08-24
- **서비스 지역:** 서울
- **출시 목표:** 실제 앱 출시 및 운영
- **장기 목표:** 사업화 가능성 검증
- **문서 목적:** 서비스 아이디어를 처음 접하는 기획·디자인·개발 팀원이 제품의 문제 정의, 핵심 사용자 가치, 기능 범위, 정책, 상태 전이, 구현 우선순위를 동일하게 이해할 수 있도록 한다.

---

## 1. 제품 한 줄 정의

> **지금**은 약속이나 막차처럼 사용자가 반드시 지켜야 하는 **이동 Deadline**을 기준으로, 언제 출발해야 하는지 계산하고 출발 전후 Journey를 Monitoring하여 기존 이동 계획이 실패할 위험이 생기면 다음 행동을 다시 제안하는 **Deadline-aware Mobility Assistant**이다.

기존 지도 서비스가 주로 **"어떻게 갈 것인가"**를 알려준다면, 지금은 그 위에서 **"언제 움직여야 하는가"**, **"지금 계획이 아직 유효한가"**, **"계획이 깨졌다면 무엇을 해야 하는가"**를 판단하는 Decision Layer를 목표로 한다.

---

## 2. 문제 정의

### 2.1 사용자가 겪는 문제

일반적인 길찾기 서비스는 출발지와 목적지를 입력하면 경로와 예상 소요시간을 제공한다. 그러나 실제 사용자는 다음과 같은 질문을 자주 한다.

- "19시까지 강남역에 가야 하는데 몇 시에 나가야 하지?"
- "약속 10분 전에는 도착하고 싶은데 지금부터 어느 정도 여유를 잡아야 하지?"
- "막차를 놓치지 않고 집에 가려면 지금 있는 곳에서 몇 시까지 출발해야 하지?"
- "원래 경로가 지연됐는데 다른 방법으로는 시간 안에 갈 수 있나?"
- "이미 늦을 것 같은데 지금 가장 빨리 도착할 방법은 무엇인가?"

현재는 사용자가 지도 앱, 막차 정보, 실시간 교통 정보, 개인적인 안전 여유를 직접 조합해 판단해야 하는 경우가 많다.

### 2.2 핵심 Pain Point

1. **출발 시점 판단이 사용자에게 남아 있다.**
   - 경로와 소요시간을 알아도 실제 출발 시각은 사용자가 다시 계산해야 한다.

2. **Deadline이 가까워질수록 경로의 유효성이 계속 변한다.**
   - 교통 지연, 환승 실패 가능성, 막차 연결 여부 등으로 처음 계산한 계획이 무효가 될 수 있다.

3. **막차는 단일 막차시각 조회가 아니라 Journey 전체의 마지막 연결 가능성을 판단해야 한다.**
   - 버스 → 지하철 → 버스와 같이 여러 Transit Leg를 거치는 경우, 각 교통편의 마지막 연결 가능성을 모두 만족해야 한다.

4. **사용자는 이동 중 정상 상황에서는 간섭을 원하지 않지만, 문제가 생긴 순간에는 즉시 대안을 원한다.**

---

## 3. 제품 목표

### 3.1 MVP 핵심 목표

MVP에서 해결해야 하는 Core Job은 다음 두 가지이며 **동등한 우선순위**를 가진다.

#### A. Appointment Deadline
사용자가 약속, 수업, 업무 등 특정 시간까지 목적지에 도착해야 할 때 **Recommended Leave Time**을 계산하고 변경이 발생하면 알린다.

#### B. Last Journey Deadline
사용자가 대중교통으로 목적지까지 귀가할 수 있는 **Recommended Last Departure**를 계산하고, 기존 막차 Journey가 깨질 경우 Alternative Journey를 다시 탐색한다.

### 3.2 보조 목표

- 사용자가 최대한 늦게 출발하고 싶을 때의 효율성 제공
- Calendar 기반으로 반복 입력 부담을 줄임
- 자연어 입력으로 설정 과정 단축
- 사용자 이동 Preference를 Route 판단에 반영

---

## 4. 비목표(Non-goals)

MVP에서는 다음을 목표로 하지 않는다.

- Turn-by-turn Navigation 직접 구현
- 자체 지도 플랫폼 구축
- 자동차 Navigation
- 전국 교통지원
- 강화학습 기반 교통 혼잡 예측
- 모든 PM Provider 통합
- 음식점/주변 장소 추천
- 일정관리 앱 전체 기능
- 대중교통 정상 이동 중 지속적인 세부 Navigation 안내

**원칙:** 지금은 지도 앱을 대체하는 서비스가 아니라, 외부 Routing/Navigation 위에서 Deadline 판단과 Exception Handling을 담당하는 서비스다.

---

## 5. 타겟 사용자

### 5.1 1차 타겟

- 막차 시간에 민감한 대학생
- 약속이나 출근 일정에 늦지 않기 위해 출발시간을 자주 확인하는 사용자
- 최대한 불필요한 대기시간 없이 효율적으로 움직이고 싶은 사용자
- 여러 교통수단을 조합해 이동하는 서울 생활권 사용자

### 5.2 대표 Persona

#### Persona A — 약속형
- 20대 대학생 또는 직장인
- "7시까지 도착"은 기억하지만 실제 출발시간 계산을 번거롭게 느낀다.
- 5~20분 정도 미리 도착하는 선호가 있다.
- 일정이 바뀌거나 교통이 지연되면 출발시간을 다시 계산하기 귀찮다.

#### Persona B — 막차형
- 밤늦게 귀가하는 대학생 또는 직장인
- 여러 번 환승해야 할 수 있다.
- 막차 시간을 계속 확인하는 데 피로감을 느낀다.
- 막차가 끊기면 택시+대중교통 Hybrid를 허용할 수도 있다.

---

## 6. 핵심 Product Principle

### 6.1 Time is Hero

지도나 경로보다 **출발해야 하는 시간**을 화면의 가장 중요한 정보로 표시한다.

예:

```text
19:00 약속
18:27 출발 권장
출발까지 34분
```

막차:

```text
23:16
대중교통 귀가 권장 마지노선
```

### 6.2 Exception-driven Monitoring

사용자가 정상적으로 이동 중이라면 앱은 개입하지 않는다.

다음 상황에서만 적극적으로 개입한다.

- 환승 가능성이 낮아짐
- 예정 교통편을 놓침
- Deadline 내 도착이 어려워짐
- 추천 Route 이탈
- 기존 Last Journey가 더 이상 유효하지 않음

### 6.3 Recommended Time과 Hard Deadline을 분리

내부적으로는 이론상 가능한 최후 시각과 안전 여유가 포함된 권장 시각을 구분한다.

- **Hard Deadline:** 데이터상 이론적으로 가능한 최후 시각
- **Recommended Deadline:** Safety Buffer를 적용한 사용자 노출용 권장 시각

기본 화면에서는 Recommended 값을 우선 노출한다.

---

## 7. 서비스 범위

### 7.1 지역

- **MVP:** 출발지와 목적지가 모두 서울 서비스 범위 내인 Journey
- 타 지역 확장은 V1 이후 검토

### 7.2 대중교통

MVP 지원:

- 지하철
- 버스
- 도보
- 지하철+버스 조합

조건부 지원:

- Taxi + Transit Hybrid
  - 사용자가 온보딩에서 Taxi 사용을 허용한 경우에 한함

MVP 이후 검토:

- PM
- 자전거
- 자동차

---

## 8. 핵심 사용자 입력

사용자는 두 경로로 이동 Deadline을 생성할 수 있다.

### 8.1 Natural Language Input

예:

- "오늘 7시까지 강남역 가야 해"
- "11시 반까지 집에 가야 해"
- "내일 9시 수업 10분 전에는 도착하고 싶어"

NLP의 역할은 Core Intelligence가 아니라 **Input UX**다.

시스템은 최소 다음 정보를 추출한다.

- 출발지
- 목적지
- 도착 Deadline
- 출발 관련 표현
- 경유지
- 이동수단
- 사용자 조건

모호한 값은 임의 확정하지 않는다.

예:

```text
"내일 8시 잠실"
```

→ 잠실역 / 잠실종합운동장 / 기타 POI 확인  
→ 오전/오후 및 출발/도착 의미가 불명확하면 Confirmation

### 8.2 Calendar Integration

Calendar에서 장소가 포함된 일정을 감지한다.

자동으로 Monitoring을 시작하지 않고 사용자에게 확인한다.

```text
오늘 19:00 성수 일정이 있습니다.
출발 시간을 관리할까요?

[관리하기] [무시]
```

장소가 모호하면 목적지를 다시 확인한다.

---

## 9. Onboarding

초기 Onboarding에서 지나치게 많은 숫자 입력을 요구하지 않는다.

### 9.1 자주 가는 장소

- 집
- 학교
- 회사
- 건너뛰기 가능 항목 허용

### 9.2 도보 Preference

예:

- 적게
- 보통
- 많이
- 직접 설정

### 9.3 Arrival Preference

예:

- 정시
- 5분 전
- 10분 전
- 20분 전
- 직접 설정

이 Preference는 일반 Appointment의 Target Arrival Time 산출에 사용한다.

### 9.4 Taxi 사용

필수 선택:

```text
대중교통이 끊긴 경우 Taxi를 포함한 경로도 찾을까요?

[사용함] [사용 안 함]
```

선택 입력:

```text
허용 가능한 최대 Taxi 비용
[        원]
```

최대 비용을 입력하지 않은 경우 **비용 무제한**으로 해석하지 않는다.  
대신 Taxi Distance / 예상 Taxi Cost를 최소화하는 방향의 Alternative를 우선한다.

### 9.5 Calendar

Calendar 연동은 선택이나, 핵심 Retention 기능으로 적극 안내한다.

---

## 10. Appointment Deadline Flow

```text
Natural Language / Calendar
        ↓
일정 및 목적지 확정
        ↓
도착 Deadline
        ↓
Arrival Preference 적용
        ↓
Target Arrival Time
        ↓
Routing
        ↓
Route-specific Safety Buffer 적용
        ↓
Recommended Leave Time
        ↓
Background Monitoring
        ↓
Adaptive Notification
        ↓
GPS 출발 감지
        ↓
IN_TRANSIT
        ↓
Exception-driven Monitoring
        ↓
ARRIVED
```

### 10.1 이미 늦을 것으로 예상되는 경우

예:

```text
약속 19:00
현재 최단 도착 19:07

약 7분 늦을 가능성이 있습니다.
```

동시에 Alternative Route를 비교한다.

예:

```text
대중교통 19:07 도착
Taxi 18:58 도착
```

사용자를 질책하거나 실패 메시지를 강조하지 않는다.  
목표는 현재 시점에서 피해를 최소화하는 행동을 제공하는 것이다.

---

## 11. Last Journey Flow

막차 기능은 단순히 특정 역의 막차시간을 알려주는 기능이 아니다.

### 11.1 핵심 개념

**Last Feasible Journey**

```text
현재 위치
  ↓ 도보
버스
  ↓ 환승
지하철
  ↓ 환승
버스
  ↓ 도보
목적지
```

각 Transit Leg의 운행시간과 환승 가능성을 만족하는 마지막 Journey를 계산한다.

### 11.2 기본 Flow

```text
출발지 / 목적지
        ↓
Bus + Subway Route 탐색
        ↓
각 Transit Leg 검증
        ↓
Last Feasible Journey 계산
        ↓
Route-specific Safety Buffer
        ↓
Recommended Last Departure
        ↓
Monitoring
        ↓
Journey 유효성 재검증
```

### 11.3 Journey 실패 시

```text
Journey 실패
    ↓
자동 Replan #1
    ↓
Journey 실패
    ↓
자동 Replan #2
    ↓
Journey 실패
    ↓
자동 Replan #3
    ↓
사용자에게 계속 탐색할지 확인
```

자동 Re-routing은 최대 3회의 **사용자 관점 Journey 재제시**까지 허용한다.

Backend의 네트워크 재시도나 API Retry는 이 횟수에 포함하지 않는다.

사용자가 계속 탐색을 승인하면 새 Cycle로 전환한다.

---

## 12. Taxi + Transit Hybrid

Taxi 사용 허용 사용자의 경우, 순수 대중교통 Journey가 더 이상 불가능할 때 Hybrid를 탐색할 수 있다.

예:

```text
Taxi 2.8km
↓
지하철 막차
↓
도보
목적지
```

정책:

- Taxi 사용 허용 여부는 Onboarding에서 필수 선택
- 최대 Taxi 비용은 선택값
- 최대 비용 입력 시 Cost Constraint 적용
- 미입력 시 Taxi 사용량/거리/예상비용 최소화 우선
- 예상 비용은 사용자에게 표시

---

## 13. Safety Buffer

### 13.1 MVP

Safety Buffer는 Route 특성에 따라 차등 적용한다.

예시 구성:

```text
기본 여유
+ 도보 구간 Buffer
+ 환승 유형 Buffer
+ 환승 횟수 Buffer
```

MVP에서 상세 규칙과 수치는 Technical Spike/실데이터 검증 후 확정한다.

### 13.2 장기 확장

향후 사용자 실제 이동 데이터를 기반으로 개인화한다.

예:

- 특정 역의 사용자 실제 환승시간
- 평균 보행속도
- 사용자가 반복적으로 늦는 구간
- 사용자별 Arrival Preference

---

## 14. Monitoring 정책

### 14.1 출발 전 Monitoring

Continuous Polling을 기본으로 하지 않는다.

Recommended Leave Time에 가까워질수록 재계산 주기를 점진적으로 좁히는 방식 등을 검토한다.

### 14.2 Adaptive Notification Threshold

일반 Appointment는 남은 시간에 따라 알림 민감도를 다르게 한다.

예시 정책:

| 출발까지 남은 시간 | 알림 조건 예시 |
|---|---:|
| 60분 초과 | Leave Time이 10분 이상 당겨짐 |
| 30~60분 | 5분 이상 |
| 10~30분 | 3분 이상 |
| 10분 이내 | 1~2분 이상 |
| Last Journey | 중요 변화 즉시 |

정확한 값은 MVP QA 및 사용성 테스트에서 조정한다.

막차 Scenario는 일반 약속보다 더 민감하게 처리한다.

---

## 15. 출발 판단

### 15.1 Primary Source

**GPS 기반 자동 판단**

```text
AT_ORIGIN
    ↓
POSSIBLY_DEPARTED
    ↓
DEPARTED
```

단일 좌표 이탈만으로 출발을 확정하지 않는다.

고려해야 할 예외:

- GPS Drift
- 편의점 등 단거리 외출
- 고층건물/지하 공간
- 위치 정확도 저하

### 15.2 Manual Override

GPS 오판 시 사용자가 직접 수정 가능하다.

```text
[이미 출발했어요]
```

GPS가 Primary Source인 정책은 유지하되 Escape Hatch를 제공한다.

---

## 16. 출발 후 Monitoring

### 16.1 Product Boundary

출발 후에도 목적지 도착까지 관리한다.

다만 **Turn-by-turn Navigation을 하지 않는다.**

정상 이동 시:

```text
Journey 정상
→ No Action
```

문제 발생 시:

```text
환승 실패 가능성
경로 이탈
Deadline Risk
Last Journey Loss
→ 개입
```

### 16.2 Checkpoint-based Monitoring

초기 구현은 모든 순간을 1초 단위로 추적하기보다 주요 Checkpoint 중심으로 설계한다.

예:

- 출발 여부
- 첫 Transit Leg 탑승 예상시각
- 환승시각 접근
- 환승 가능성
- 다음 Transit Leg 탑승 가능성
- 목적지 접근

---

## 17. Route Deviation 정책

사용자가 추천 경로와 다른 교통편을 이용한 경우 앱은 즉시 새 경로를 강제하지 않는다.

정책:

```text
추천 Route 이탈 감지
        ↓
기존 Journey Monitoring 종료/일시중단
        ↓
"현재 위치에서 다시 계산할까요?"
        ↓
사용자 승인
   ┌──────┴──────┐
   │             │
 거절            승인
   │             │
 종료        새 Journey 생성
                 ↓
             Monitoring 재개
```

즉:

**C → B → 사용자 허가 시 A**

---

## 18. 도착 판단

### 18.1 자동 판단

GPS를 기반으로 목적지 Geofence 진입 후 일정 조건을 충족하면 ARRIVED로 판단한다.

```text
IN_TRANSIT
    ↓
POSSIBLY_ARRIVED
    ↓
ARRIVED
```

### 18.2 Manual Override

```text
[도착했어요]
```

를 제공한다.

### 18.3 POI 정확도

"강남역"과 "강남역 인근 식당"은 다른 목적지다.  
가능한 경우 목적지를 POI 수준까지 확정한 뒤 Monitoring을 시작한다.

---

## 19. Calendar Conflict

동시에 여러 Calendar 일정이 충돌하는 경우 시스템이 임의로 우선순위를 결정하지 않는다.

예:

```text
18:00 학교 수업
18:30 강남 약속
```

→ 사용자에게 어떤 일정을 관리할지 선택 요청

```text
일정 시간이 겹쳐 있어요.
어떤 이동을 관리할까요?
```

상태 예시:

```text
CALENDAR_EVENT_DETECTED
        ↓
CONFLICT_DETECTED
        ↓
USER_DECISION_REQUIRED
        ↓
SELECTED
        ↓
MONITORING
```

---

## 20. Permission 정책

### 20.1 Location Permission

거부 시 앱 전체를 차단하지 않고 **Limited Mode**를 제공한다.

#### Full Mode
- 현재 위치 자동 인식
- GPS 출발 감지
- Route Deviation 감지
- 이동 중 Monitoring
- 자동 도착 감지

#### Limited Mode
사용자가 직접 출발지를 입력한다.

제공:
- Recommended Leave Time
- Last Journey 계산
- 기본 Route 조회
- Calendar 관리
- 시간 기반 알림

제한:
- 자동 출발 감지
- 실제 이동 기반 Monitoring
- Route Deviation 감지
- 자동 도착 감지

### 20.2 Notification Permission

알림을 거부해도 앱 자체 사용은 가능하다.

다만 명확히 고지한다.

> 알림을 허용하지 않으면 출발시간 변경이나 막차 마지노선 변화를 앱 밖에서 알려드릴 수 없습니다.

서비스 Notification과 마케팅 수신 동의는 명확히 분리한다.

예시 내부 카테고리:

- Journey / Deadline
- Calendar
- Marketing

Marketing은 별도 선택 동의다.

---

## 21. 주요 상태 모델

### 21.1 Main State

```text
SCHEDULED
    ↓
MONITORING
    ↓
READY_TO_LEAVE
    ↓
POSSIBLY_DEPARTED
    ↓
DEPARTED
    ↓
IN_TRANSIT
    ↓
POSSIBLY_ARRIVED
    ↓
ARRIVED
```

### 21.2 Exception State

- LATE_RISK
- ROUTE_AT_RISK
- MISSED_CONNECTION
- LAST_JOURNEY_LOST
- ROUTE_DEVIATED
- REPLANNING
- MANUAL_REPLAN_REQUIRED
- CANCELLED
- CONFLICT_DETECTED
- USER_DECISION_REQUIRED

상태 전이는 Backend 구현 전에 별도 State Transition Table로 상세화한다.

---

## 22. 화면 요구사항

### 22.1 Home

Home은 지도보다 Time을 중심으로 구성한다.

예:

```text
오늘

19:00 저녁 약속
강남역

18:27 출발 권장
출발까지 1시간 14분

[경로 보기]
```

막차:

```text
집으로 가기

23:16
대중교통 귀가 권장 마지노선

현재 가능한 Alternative 3개
```

### 22.2 Natural Language Input

```text
어디에 언제까지 가야 하나요?

"오늘 7시까지 강남역"
```

### 22.3 Interpretation Confirmation

- 출발지
- 목적지
- Deadline
- Arrival Buffer
- 이동수단
- Taxi 허용
- 모호성 재확인

### 22.4 Leave-by Detail

- Recommended Leave Time
- Target Arrival Time
- 예상 도착시간
- Safety Buffer
- Route summary
- Deadline Risk
- 경로 보기

### 22.5 Last Journey Detail

- Recommended Last Departure
- Hard Deadline(상세 정보)
- Last Feasible Journey
- Alternative Journey
- Taxi Hybrid 가능 여부

### 22.6 Exception UI

예:

```text
기존 환승이 어려워졌습니다.
다른 경로를 찾았습니다.

[새 경로 보기]
```

Route 이탈:

```text
추천 경로를 벗어난 것 같아요.
현재 위치에서 다시 계산할까요?

[다시 계산] [종료]
```

---

## 23. Routing / Navigation 원칙

### 23.1 Routing Layer

외부 Routing API 또는 공공데이터를 활용한다.

후보 Provider는 Technical Spike에서 검증하며, 특정 Provider를 PRD 단계에서 고정하지 않는다.

권장 구조:

```text
RoutingProvider Interface
├─ Provider A
├─ Provider B
├─ PublicDataAdapter
└─ MockProvider
```

목표는 특정 Provider 장애나 제휴 조건 변경이 전체 서비스 구조에 영향을 주지 않도록 하는 것이다.

### 23.2 Navigation Handoff

Turn-by-turn Navigation은 외부 지도/Navigation 앱으로 연결하는 방식을 우선 검토한다.

---

## 24. Agent / AI 사용 원칙

AI는 서비스의 판단 전부를 담당하지 않는다.

### AI에 적합한 영역
- Natural Language Parsing
- 모호한 입력 구조화
- Calendar 제목/장소 문맥 이해 보조
- 사용자에게 결과를 자연스럽게 설명

### Deterministic Logic이 우선인 영역
- Deadline 계산
- Last Journey 검증
- Safety Buffer 적용
- Permission 정책
- Retry Counter
- State Transition
- Notification Threshold
- Route 유효성 판정

**원칙:** LLM은 Input/Explanation Layer에 가깝고, 핵심 시간 계산과 상태 전이는 검증 가능한 Rule/Algorithm으로 구현한다.

---

## 25. MVP 기능 우선순위

### MUST

- Natural Language 일정 입력
- 목적지/시간 Parsing
- Ambiguity Confirmation
- 현재 위치/지정 출발지
- Arrival Preference
- Recommended Leave Time
- 버스+지하철 Routing
- Last Feasible Journey
- Route-specific Safety Buffer
- Deadline Notification
- Adaptive Notification Threshold
- Background Recalculation
- Alternative Journey
- Calendar Event Detection
- Calendar Event 사용자 승인
- GPS 출발 감지
- Manual Departure Override
- Exception-driven In-trip Monitoring
- Route Deviation 감지 및 사용자 재탐색 확인
- GPS 도착 감지
- Manual Arrival Override
- 자동 Replan 최대 3회
- Location Limited Mode
- Notification Permission 안내
- Navigation Handoff

### SHOULD

- Taxi + Transit Hybrid
- Taxi 최대비용 선택 입력
- 도보 Preference
- 자주 사용하는 장소
- 일정별 Arrival Preference Override
- Checkpoint Monitoring 고도화

### COULD / V1+

- PM
- 자전거
- 행사/통제 데이터 고도화 반영
- 개인화 Safety Buffer
- 사용자 실제 이동시간 학습
- 타 지역 확장
- 자동차

### OUT OF SCOPE

- 자체 Turn-by-turn Navigation
- 자체 지도
- 강화학습 기반 혼잡 예측
- 모든 이동수단 통합
- 주변 장소 추천

---

## 26. Technical Spike

본 개발 전 다음 3개 Spike를 먼저 수행한다.

### Spike 1 — Appointment

목표:

```text
출발지
목적지
도착 Deadline
→ Route
→ ETA
→ Safety Buffer
→ Recommended Leave Time
```

검증 항목:
- 기본 Routing API 사용 가능 여부
- ETA 신뢰도
- 미래 일정 처리 방식
- 재계산 비용

### Spike 2 — Last Journey

목표:

```text
출발지
목적지
→ Bus/Subway Journey
→ 각 Leg 운행시간
→ 환승 가능성
→ Last Feasible Journey
```

**가장 중요한 Go / No-Go Point**

검증 항목:
- 버스/지하철 시간표 확보
- 마지막 운행편 판별
- 환승 연결 검증 가능 여부
- 종착역 차이 처리
- 데이터 라이선스
- API Quota/비용
- 서울 전체 Coverage

### Spike 3 — Journey Monitoring

목표:

```text
기존 Journey
+ 현재 위치
+ 현재 시간
→ 정상 / 위험 / 이탈 판정
```

검증 항목:
- Background Location
- Checkpoint 감지
- 배터리 사용량
- Route Deviation 판정
- Re-routing Latency
- Push Timing

---

## 27. 핵심 KPI 제안

MVP 출시 후 아래 지표를 우선 관찰한다.

### North Star 후보

**Managed Journey Success Rate**

> 지금이 관리한 Journey 중 사용자가 설정한 Deadline을 만족하거나, 실패 위험 발생 시 적절한 Alternative를 제공한 비율

### Supporting KPI

- Deadline 등록 → Monitoring 시작 전환율
- Calendar 감지 → 관리하기 선택률
- Recommended Leave Notification 확인율
- 실제 출발시간과 Recommended Leave Time 차이
- Deadline On-time Arrival Rate
- Last Journey 성공률
- Automatic Replan 성공률
- Manual Replan 요청률
- Route Deviation 발생률
- Location Permission 허용률
- Notification Permission 허용률
- D7 / D30 Retention
- 주간 Managed Journey 수

---

## 28. 주요 리스크

### 28.1 데이터 신뢰성

막차와 환승은 수 분의 오차가 치명적이다.

대응:
- Hard Deadline과 Recommended Deadline 분리
- Safety Buffer
- 신뢰도 문구
- Provider/Data Source 검증

### 28.2 Routing Provider 종속성

외부 API 정책/비용/제휴 조건이 변경될 수 있다.

대응:
- Provider Interface 추상화
- Technical Spike
- Mock/Fallback 설계

### 28.3 Background Location

배터리, Permission, OS 정책 문제가 있다.

대응:
- Checkpoint-based Monitoring
- Limited Mode
- Manual Override

### 28.4 Notification Fatigue

작은 시간 변화마다 Push하면 서비스가 피로해진다.

대응:
- Adaptive Threshold
- Appointment/Last Journey 정책 분리
- 정상 Journey는 침묵

### 28.5 Scope Creep

Navigation, PM, 자동차, 장소 추천까지 확장하면 MVP가 실패할 수 있다.

대응:
- Deadline/Monitoring Engine 중심 유지
- Non-goal 준수

---

## 29. 출시 판단 기준

다음 조건을 만족해야 MVP 개발을 본격화한다.

1. 서울에서 버스+지하철 Route를 안정적으로 조회할 수 있다.
2. Last Feasible Journey를 현실적으로 산출할 데이터 또는 API가 확보된다.
3. Route-specific Safety Buffer 적용이 가능하다.
4. Background Location 기반 Checkpoint Monitoring이 현실적인 배터리/권한 수준에서 동작한다.
5. Route Risk 또는 Route Deviation을 MVP 수준에서 판별할 수 있다.
6. 외부 Navigation Handoff가 사용자 Flow를 훼손하지 않는다.

Spike 2가 실패하면 막차 기능을 단순화하거나 대체 데이터 전략을 먼저 수립한다.

---

## 30. 개발 원칙 요약

> **지금은 길을 알려주는 앱이 아니라, 움직여야 할 순간을 판단하는 앱이다.**

개발 과정에서 새로운 기능을 검토할 때 다음 질문을 우선한다.

1. 이 기능이 Deadline 판단 정확도를 높이는가?
2. 사용자가 움직여야 할 시점을 더 잘 알려주는가?
3. Journey가 깨지는 순간 더 나은 결정을 제공하는가?
4. 기존 지도 앱이 이미 잘하는 일을 중복 구현하는 것은 아닌가?

위 질문에 명확히 답하지 못하는 기능은 MVP에서 제외한다.
