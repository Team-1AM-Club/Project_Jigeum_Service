# 지금(가칭) — MCP 서비스 Product Requirements Document (PRD)

- **문서 버전:** v1.1 — MCP 제공 방향 반영 (파일명은 참조 보존을 위해 유지)
- **개정일:** 2026-09-14
- **작성일:** 2026-08-24
- **서비스 지역:** 서울
- **제공 목표:** MCP 도구를 통한 서비스 제공·운영. Hermes + Solar Pro4를 개발·시연용 MCP 클라이언트로 사용
- **장기 목표:** 사업화 가능성 검증
- **문서 목적:** 서비스 아이디어를 처음 접하는 기획·디자인·개발 팀원이 제품의 문제 정의, 핵심 사용자 가치, 기능 범위, 정책, 상태 전이, 구현 우선순위를 동일하게 이해할 수 있도록 한다.

---

## 0. 현재 개발 기준

> **현재 서비스 개발 방향 — 2026-09-14:** 지금은 **MCP로 제공하는 서비스**다. 별도 제품 화면·설치형 클라이언트를 개발하지 않는다. 본인은 MCP 도구·Hermes 연결·확인/선택 흐름·시연을, 친구는 FastAPI·서비스 Agent·교통 데이터·계산·배포를 담당한다. Hermes + Solar Pro4는 개발·시연용 MCP 클라이언트다. 현재 구현 범위와 완료 기준은 IDEA.md를 따른다.

이 PRD의 기존 도메인 정책은 보존하되 현재 4일 MVP와 후속 확장을 구분한다. GPS·상태 자동 감지·Calendar·Push·택시 최적화·개인화는 후속 확장 정책이며 구현 지시나 완료 주장으로 해석하지 않는다.

서비스 구조는 사용자 ↔ Hermes + Solar Pro4 ↔ 지금 MCP 서버 ↔ 기존 FastAPI·서비스 Agent·계산 ↔ 검증된 교통 데이터다. 외부 기능 인터페이스는 MCP이며 FastAPI는 내부 계산 API다. MCP는 임시 시연 방식이나 별도 제품 개발 전 단계가 아니다.

## 1. 제품 한 줄 정의

> **지금**은 약속·막차의 **이동 Deadline**에 맞춘 출발시각과 계획 실패 시 대안을 MCP 도구로 제공하는 **Deadline-aware Mobility MCP Service**다. 현재 MVP는 사용자 요청·확인·선택을 기준으로 동작한다.

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

현재는 사용자가 지도 서비스, 막차 정보, 실시간 교통 정보, 개인적인 안전 여유를 직접 조합해 판단해야 하는 경우가 많다.

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

제품의 두 Core Job은 약속 출발 판단과 막차 귀가 판단이다. 4일 MVP에서는 약속 흐름을 먼저 종단 간 연결하고, 막차는 첫날 검증한 노선·운행일·환승 데이터 범위에서 제공한다.

#### A. Appointment Deadline
사용자가 약속, 수업, 업무 등 특정 시간까지 목적지에 도착해야 할 때 **Recommended Leave Time**을 계산해 요청 결과로 전달한다. 변경 재계산은 사용자 요청으로 시작하며 자동 알림은 현재 범위가 아니다.

#### B. Last Journey Deadline
사용자가 대중교통으로 목적지까지 귀가할 수 있는 **Recommended Last Departure**를 계산하고, 기존 막차 Journey가 깨질 경우 Alternative Journey를 다시 탐색한다.

### 3.2 보조 목표

- 사용자가 최대한 늦게 출발하고 싶을 때의 효율성 제공
- Calendar 기반 반복 입력 감소는 후속 확장으로 보존
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
- 일정관리 서비스 전체 기능
- 대중교통 정상 이동 중 지속적인 세부 Navigation 안내

**원칙:** 지금은 지도 서비스을 대체하는 서비스가 아니라, 외부 Routing/Navigation 위에서 Deadline 판단과 Exception Handling을 담당하는 서비스다.

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

MCP 도구 결과와 Hermes 설명에서 **출발해야 하는 시간**을 가장 먼저 제시한다. 별도 결과 화면을 구현하지 않는다.

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

### 6.2 사용자 요청 기반 예외 대응

현재 MCP MVP는 상시 감시하거나 자발적으로 개입하지 않는다. 사용자가 다음 상황을 알려 재탐색을 요청하면 현재 조건을 확인하고 대안을 조회한다. 자동 감시는 후속 확장이다.

- 환승 가능성이 낮아짐
- 예정 교통편을 놓침
- Deadline 내 도착이 어려워짐
- 추천 Route 이탈
- 기존 Last Journey가 더 이상 유효하지 않음

### 6.3 Recommended Time과 Hard Deadline을 분리

내부적으로는 이론상 가능한 최후 시각과 안전 여유가 포함된 권장 시각을 구분한다.

- **Hard Deadline:** 데이터상 이론적으로 가능한 최후 시각
- **Recommended Deadline:** Safety Buffer를 적용한 사용자 노출용 권장 시각

도구 결과를 설명할 때 Recommended 값을 우선하고 Hard Deadline과 구분한다.

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

현재 MVP 제외:

- Taxi + Transit Hybrid와 택시비 상한선. 관련 정책은 후속 확장에만 적용한다.

MVP 이후 검토:

- PM
- 자전거
- 자동차

---

## 8. 핵심 사용자 입력

현재 사용자는 Hermes 대화로 이동 Deadline을 입력한다. Calendar 연동은 후속 확장이다.

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

### 8.2 Calendar Integration — 후속 확장, 현재 비적용

Calendar에서 장소가 포함된 일정을 감지한다.

자동으로 Monitoring을 시작하지 않고 사용자에게 확인한다.

```text
오늘 19:00 성수 일정이 있습니다.
출발 시간을 관리할까요?

[관리하기] [무시]
```

장소가 모호하면 목적지를 다시 확인한다.

---

## 9. MCP 입력 조건과 선호 확인

별도 온보딩 화면·사용자 계정·장소 저장 기능을 만들지 않는다.

- 이번 이동에서 사용자가 명시한 출발 기준점·목적지·Deadline·도착 여유·교통수단을 우선한다.
- 확인된 선호가 없으면 capabilities 기본값을 최종 조건 요약에 표시한다.
- 집·학교·회사 표현을 저장된 위치로 임의 해석하지 않고 가까운 역·정류장·건물 출입구 등 필요한 최소 장소를 확인한다.
- 이용 교통수단은 버스·지하철, 도보는 연결 구간으로 기본 허용한다.
- 도착 여유는 Deadline과 구분한다. “19시까지 도착”을 여유 미지정 때문에 다시 묻지 않는다.
- 필수 조건이 부족하면 한 번에 최대 3개의 질문을 한다. 모든 조건이 정리되면 실제 계산 전에 최종 확인을 받는다.
- 택시 허용·비용 상한선과 Calendar 권한은 현재 입력·저장 범위가 아니다.

---

## 10. Appointment Deadline Flow

~~~text
Hermes 자연어 입력
        ↓
interpret_trip / search_places
        ↓
장소·날짜·Deadline·도착 여유·이동수단 확인
        ↓
사용자 최종 확인
        ↓
plan_journey → FastAPI
        ↓
검증된 Routing + 코드 기반 Safety Buffer
        ↓
Recommended Leave Time · Target Arrival · 근거
        ↓
사용자가 후보 선택
        ↓
사용자 요청 시 replan_journey → 비교 → 선택 후 적용
~~~

자동 감시·GPS 출발/도착 판정·예약 알림은 이 흐름에 포함하지 않는다.

---

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
확인된 대중교통 후보 A: 19:07 도착
다른 후보: 실제 조회 결과가 있을 때만 비교
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
출발지 / 목적지 / 운행일 확인
        ↓
사용자 최종 확인 → plan_journey
        ↓
Bus + Subway Route 탐색
        ↓
각 Transit Leg 검증
        ↓
Last Feasible Journey 계산
        ↓
Route-specific Safety Buffer
        ↓
Recommended Last Departure + Hard Deadline + 근거
        ↓
사용자 요청 시 현재 조건 확인 후 재탐색
```

### 11.3 Journey 실패 시

~~~text
사용자: 환승을 놓쳤어. 다시 찾아줘
        ↓
현재 출발 기준점·유지할 목적지·Deadline 확인
        ↓
사용자 요청 확인 → replan_journey
        ↓
검증된 대안·기존 계획 대비 변화
        ↓
사용자 후보 선택 후 적용
~~~

자동 재탐색·주기당 재제시 3회 정책은 현재 수동 요청 횟수 제한이 아니다. 해당 정책은 자동 감시를 도입할 때 별도 사용자 승인·주기 설계와 함께 검토한다. 네트워크 재시도는 사용자에게 새 Journey를 제시한 횟수와 구분한다.

---

## 12. Taxi + Transit Hybrid — 후속 확장, 현재 비적용

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

- 후속 도입 시 Taxi 사용 여부·비용 조건을 별도 확인한다. 현재는 수집하지 않는다.
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

## 14. Monitoring 정책 — 후속 확장, 현재 비적용

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

이 수치는 후속 자동 알림 도입 시 검증할 정책 예시이며 현재 MCP MVP의 알림 구현 요구가 아니다.

막차 Scenario는 일반 약속보다 더 민감하게 처리한다.

---

## 15. 출발 판단 — 후속 센서 연동 정책, 현재 비적용

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

## 16. 출발 후 Monitoring — 후속 확장, 현재 비적용

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

## 17. 사용자 요청 재탐색과 선택 정책

현재 MCP MVP는 경로 이탈을 자동 감지하지 않는다. 사용자가 다른 경로로 이동했다고 알리면 다음을 수행한다.

1. 새 출발 기준점과 유지할 목적지·Deadline을 확인한다.
2. 사용자가 재탐색을 요청·확인하면 현재 서버 시각 기준으로 replan_journey를 호출한다.
3. 후보와 이전 선택 대비 변화를 반환한다.
4. 사용자 선택 전에는 기존 계획을 교체하지 않는다.
5. 실패·취소 시 기존 선택을 지우지 않되 그 경로의 현재 유효성을 보장하지 않는다.

후속 센서 연동에서 이탈을 감지하더라도 사용자 선택 없이 새 계획을 강제하지 않는다.

---

## 18. 도착 판단 — 후속 센서 연동 정책, 현재 비적용

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

## 19. Calendar Conflict — 후속 확장, 현재 비적용

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

## 20. MCP 권한·확인·개인정보 정책

- Hermes의 도구 연결 권한과 사용자가 특정 이동 조건에 동의했다는 사실은 별개다.
- get_capabilities·search_places·interpret_trip 결과를 전달하고, 계산 전 최종 조건 확인을 받는다.
- ready_for_plan=true 또는 모델이 생성한 user_confirmed=true만으로 사람의 동의가 검증됐다고 보지 않는다. 확인한 조건·사용자 응답을 요청에 결부하는 방법을 코드와 명세에서 정하고 테스트한다.
- 조건이 바뀌면 재확인하며 재탐색 결과는 사용자 후보 선택 후 적용한다.
- 위치는 사용자에게 필요한 최소 기준점을 확인한다. OS 위치 권한이나 상시 GPS 접근을 요구하지 않는다.
- 현재 MVP에는 알림 발송·마케팅 수신·Calendar 접근 권한을 요구하지 않는다.
- 대화별 문맥·선택 계획의 위치와 수명을 공동 합의하고 다른 사용자의 상태와 섞지 않는다.
- 도구 응답·설정 예제·로그·영상에 실제 교통·모델 비밀키를 노출하지 않는다.
- 원격 MCP 또는 공개 백엔드 운영에는 별도의 접근 제어·호출 제한·인증 검토가 필요하다. 로컬 시연 성공이 공개 운영 보안 검증을 뜻하지 않는다.

---

## 21. 현재 대화의 조건·선택 상태

개념 흐름은 입력 부족 → 조건 요약 → 사용자 최종 확인 → 계산 결과 → 후보 선택 → 사용자 요청 재탐색 → 새 후보 선택이다.

이는 새로운 REST status enum을 추가하는 정의가 아니다. 기존 공개 응답 status는 ok / needs_confirmation / unavailable / error를 유지한다. 확인·선택 상태의 저장 위치와 수명은 구현 전에 합의한다.

- 요청별 계산 서버가 과거 대화를 영구 보존한다고 가정하지 않는다.
- Plan과 선택 option_id를 기준으로 재탐색 요청의 trip·previous_plan을 구성한다.
- 필요한 문맥을 잃으면 다시 확인하고 임의 복원하지 않는다.
- 늦게 도착한 과거 응답이 최신 조건·선택을 덮어쓰지 않도록 한다.
- SCHEDULED/DEPARTED/ARRIVED 같은 진행 상태 자동 추적·영구 이력·알림 상태는 현재 필수 모델이 아니다.

---

## 22. MCP 도구와 결과 전달 요구사항

본인 담당은 화면 개발이 아니라 MCP 도구·백엔드 연결·Hermes 확인/선택 흐름이다. 사용자가 읽는 대화는 Hermes가 제공한다.

| MCP 도구 | 기존 백엔드 API | 역할 |
|---|---|---|
| get_capabilities | GET /api/v1/capabilities | 지원 지역·교통수단·운행일·기본값·데이터 상태 |
| search_places | GET /api/v1/places | 정확한 출발·도착 기준점 후보 |
| interpret_trip | POST /api/v1/mobility/interpret | 구조화 조건·부족 정보·확인 질문 |
| plan_journey | POST /api/v1/journeys/plan | 사용자 확인 후 약속·막차 계획 |
| replan_journey | POST /api/v1/journeys/replan | 요청 기반 대안·기존 선택 대비 변화 |

### 조건 확인

출발지·목적지·날짜·Deadline·도착 여유·이동수단을 요약한다. 불명확한 값만 질문하고 최종 사용자 확인을 받는다.

### 계획 결과

권장 출발시각, 목표 도착·예상 도착, 검증된 경로, Safety Buffer 근거, Deadline 위험, 출처·기준시각·데모 여부를 전달한다. 막차는 Recommended Last Departure와 Hard Deadline을 구분한다.

### 실패와 대안

업무상 미지원·경로 없음과 제공처 장애·시간 초과를 구분한다. 확인되지 않은 시간을 생성하지 않는다. 재탐색 결과는 후보이며 사용자 선택 전 자동 적용하지 않는다.

MCP 세부 JSON Schema·실행 오류 매핑은 공동 합의한다. REST 경로·필드·오류를 바꾸려면 API_SPEC.md와 예제 JSON을 함께 갱신한다.

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

Turn-by-turn Navigation은 구현하지 않는다. 검증된 외부 지도·Navigation URL이 서버 응답에 있을 때 전달할 수 있다.

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

## 25. MCP MVP 기능 우선순위

### MUST

- Hermes + Solar Pro4의 MCP 도구 발견·실제 호출
- 정확한 장소·시간 해석, 부족 정보 질문, 사용자 최종 조건 확인
- 실제 데이터·코드 계산에 근거한 약속 출발시각·도착시각·근거
- 사용자 요청 재탐색·후보 비교·선택 후 적용
- 구조화 결과, 출처·기준시각·데모 표시
- 지원 범위 밖·데이터 없음·API 실패·시간 초과 구분
- 확인·문맥·선택 상태의 검증과 비밀키 보호
- 재현 가능한 실행 안내·Hermes 설정 예시·시연·테스트 근거

### 첫날 데이터 검증 후 제공

- Last Feasible Journey와 Recommended Last Departure
- 운행일·방향·종착역·환승 연결이 검증된 범위의 막차
- 서버가 제공하는 검증된 외부 Navigation URL

### 후속 MCP 기능 확장

- Calendar, 자동 감시·알림, GPS·센서 연동, 개인화
- Taxi + Transit Hybrid·비용 제약, 여러 일정 관리
- 자주 쓰는 장소·영구 이동 이력·계정 기능
- 타 지역·다른 교통수단 지원

후속 기능도 MCP 서비스 확장 후보이며 별도 제품 화면 출시 계획을 의미하지 않는다. 현재 도구·권한이 연결되거나 기능이 구현된 것으로 설명하지 않는다.

### OUT OF SCOPE

- 별도 제품 화면·설치형 사용자 클라이언트·스토어 배포
- 자체 Turn-by-turn Navigation·자체 지도
- 강화학습 기반 혼잡 예측·모든 교통수단 통합·주변 장소 추천

---

## 26. Technical Spike

첫날 다음 MCP 연결·데이터 검증을 수행한다. 모든 결과는 실제 실행 증거로 남긴다.

### Spike 0 — Hermes·MCP 연결

Solar Pro4가 get_capabilities를 실제 호출해 MCP → FastAPI 응답을 받는지 검증한다. 설치 버전·모델 ID·실행 경로·의존성과 시연 Base URL을 기록한다.

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

### Spike 3 — 사용자 요청 재탐색

기존 선택 계획과 사용자 확인 현재 출발지 → replan_journey → 새로운 후보·변화량 → 사용자 선택 후 적용을 검증한다.

- 서버 시각 기준 조회·계산
- 과거 선택과 새로운 후보의 구분
- 미확인·변경 조건의 재확인
- 데이터 실패·시간 초과·문맥 유실 시 처리
- 실제 응답·fixture 분리와 코드 계산 정확성

Background Location·배터리·Push Timing 검증은 후속 기능 도입 시 다룬다.

---

## 27. MCP 서비스 KPI 제안

### 핵심 지표 후보

확인된 입력에 대해 근거 있는 출발 계획 또는 적절한 불가 사유를 전달한 비율을 우선 관찰한다. 실제 이동 성공은 사용자 확인이나 별도 검증 데이터 없이 추정하지 않는다.

### Supporting KPI

- MCP 도구 발견·호출·백엔드 응답 성공률
- 입력 → 사용자 최종 확인 → 계획 결과 전환율
- 불필요한 재질문·잘못된 장소/시간 확정 비율
- 출처·기준시각·데모 구분 누락률
- 사용자 확인 없는 계산·선택 없는 적용 발생률
- 재탐색 성공률·응답 지연·적절한 실패 안내 비율
- 사용자 제공 실제 도착 결과가 있을 때의 Deadline 만족률

Calendar·GPS·자동 알림 지표는 해당 후속 기능을 도입한 경우에만 수집한다. 수집 목적·보존 기간·개인정보 권한을 먼저 합의한다.

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
- 제공처 실패와 데이터 미지원 구분. 실제 조회 실패를 Mock 결과로 자동 대체하지 않음

### 28.3 Background Location — 후속 확장 리스크

배터리, Permission, OS 정책 문제가 있다.

대응:
- Checkpoint-based Monitoring
- Limited Mode
- Manual Override

### 28.4 Notification Fatigue — 후속 확장 리스크

작은 시간 변화마다 Push하면 서비스가 피로해진다.

대응:
- Adaptive Threshold
- Appointment/Last Journey 정책 분리
- 정상 Journey는 침묵

### 28.5 Scope Creep

Navigation, PM, 자동차, 장소 추천까지 확장하면 MVP가 실패할 수 있다.

대응:
- MCP 도구·Deadline 계산·사용자 요청 재탐색 중심 유지
- Non-goal 준수

---

## 29. MCP 제공·제출 판단 기준

1. 다른 환경에서 Hermes의 MCP 연결·도구 호출·백엔드 응답을 재현한다.
2. 확인된 입력으로 약속 출발시각과 검증 근거를 전달한다.
3. Safety Buffer 중복·자정·운행일 경계·사용자 고정 조건을 검증한다.
4. 확인 없는 계산과 선택 없는 적용을 차단한다.
5. 사용자 요청 재탐색과 실패 처리를 검증한다.
6. 막차를 제공한다면 확보된 데이터의 지원 범위를 명시하고 실제 연결 근거를 확인한다.
7. 실행 방법·설정 예제·비밀키 보호·테스트·시연 자료를 준비한다.
8. 주최 측의 원격 MCP 주소·배포·사용 모델 증빙 조건을 별도 확인한다.

막차 Spike가 실패하면 범위를 제한하거나 보류한다. 로컬 도구 호출 성공을 실시간 교통 연동·원격 공개·모든 클라이언트 호환성까지 검증한 것으로 표현하지 않는다.

---

## 30. 개발 원칙 요약

> **지금은 움직여야 할 순간과 다음 행동을 MCP 도구로 제공하는 서비스다.**

개발 과정에서 새로운 기능을 검토할 때 다음 질문을 우선한다.

1. 이 기능이 Deadline 판단 정확도를 높이는가?
2. 사용자가 움직여야 할 시점을 더 잘 알려주는가?
3. Journey가 깨지는 순간 더 나은 결정을 제공하는가?
4. 기존 지도 서비스이 이미 잘하는 일을 중복 구현하는 것은 아닌가?

위 질문에 명확히 답하지 못하는 기능은 MVP에서 제외한다.
