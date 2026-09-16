"""계획 서비스 (Plan Service).

출발지·목적지 기반으로 경로 후보 1~3개를 도출하고,
권장 출발시각·근거를 계산한다.

T039: plan_service.py 생성.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.journeys import (
    Comparison,
    Plan,
    PlanSummary,
    TripRequest,
)
from app.services.provider_interfaces import RoutingProvider
from app.services.time_calculation import (
    ensure_seoul,
)

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")


class PlanService:
    """경로 계획 서비스.

    출발지·목적지 기반 후보 경로 1~3개를 도출하고,
    도착 마감시각 + 도착 여유 → target_arrival_at → 권장 출발시각 계산.

    핵심 공식:
    - target_arrival_at = arrival_deadline - arrival_preference_minutes
    - recommended_leave_at = target_arrival_at - total_duration - buffer
    - buffer는 recommended_leave_at 계산 시 한 번만 적용 (중복 가산 금지)
    """

    def __init__(self, routing_provider: RoutingProvider):
        """초기화.

        Args:
            routing_provider: 경로/이동 옵션 제공자.
        """
        self.routing_provider = routing_provider

    async def plan(
        self,
        request: TripRequest,
        buffer_minutes: int = 5,
    ) -> Plan:
        """경로 계획 생성.

        Args:
            request: TripRequest (출발지·목적지·arrival_deadline 등)
            buffer_minutes: 완충 시간 (분), 기본 5분

        Returns:
            Plan: 경로 계획 응답

        Raises:
            ValueError: 출발지 미확정(origin_place_id 빈 값) 시
        """
        # 출발지 확정 검증 (T038/T040 연계: origin_place_id 빈 값이면 422)
        if not request.origin_place_id or not request.origin_place_id.strip():
            raise ValueError(
                f"출발지가 확정되지 않았습니다. origin_place_id가 필요합니다. "
                f"conversation_id={request.conversation_id}"
            )

        origin_id = request.origin_place_id.strip()
        dest_id = request.destination_place_id.strip()

        if not dest_id:
            raise ValueError("목적지가 필요합니다.")

        # provider 호출 → 이동 옵션 조회
        from app.services.routing_search import search_options

        options_data = await search_options(
            self.routing_provider,
            request,
            arrival_deadline=request.arrival_deadline.isoformat()
            if request.arrival_deadline
            else None,
        )

        # Empty supported results are unavailable, never invented routes.
        if not options_data:
            from app.services.last_journey_service import NoFeasibleJourneyError

            raise NoFeasibleJourneyError()

        # 후보 1~3개 제한
        candidate_options = options_data[: request.max_options or 3]

        # target_arrival_at = arrival_deadline - arrival_preference_minutes
        # (buffer는 recommended_leave_at 계산 시 적용)
        arrival_deadline = (
            ensure_seoul(request.arrival_deadline)
            if request.arrival_deadline
            else datetime.now(SEOUL_TZ)
        )

        # 후보별 권장 출발시각 계산
        plan_summaries: list[PlanSummary] = []
        selected_option_id = None

        for idx, opt_data in enumerate(candidate_options):
            total_duration = opt_data.get("total_duration_minutes", 0) or 0
            legs_data = opt_data.get("legs", [])

            # target_arrival_at = arrival_deadline - arrival_preference_minutes
            # (buffer 미적용, buffer는 leave 계산 시에만)
            target_arrival = arrival_deadline - timedelta(
                minutes=request.arrival_preference_minutes or 0
            )

            # 권장 출발시각 = target_arrival - total_duration - buffer
            recommended_leave = target_arrival - timedelta(
                minutes=total_duration + buffer_minutes
            )

            # 근거 생성
            reasoning = self._generate_reasoning(
                opt_data=opt_data,
                transport_mode=request.transport_mode,
                total_duration=total_duration,
                target_arrival=target_arrival,
                buffer_minutes=buffer_minutes,
                arrival_preference=request.arrival_preference_minutes or 0,
            )

            summary = PlanSummary(
                option_id=opt_data.get("option_id", f"opt_{idx}"),
                recommended_leave_at=recommended_leave,
                target_arrival_at=target_arrival,
                total_duration_minutes=total_duration,
                transport_mode=opt_data.get("transport_mode", request.transport_mode),
                reasoning=reasoning,
            )
            plan_summaries.append(summary)

            # 첫 번째 옵션을 기본 선택
            if idx == 0:
                selected_option_id = summary.option_id

        # Comparison 구성
        comparison = Comparison(
            options=plan_summaries,
            selected_option_id=selected_option_id,
            comparison_reason=self._generate_comparison_reason(plan_summaries),
        )

        # Plan 구성: 선택된 옵션의 시간 사용
        selected_summary = next(
            (s for s in plan_summaries if s.option_id == selected_option_id),
            plan_summaries[0] if plan_summaries else None,
        )

        if not selected_summary:
            raise RuntimeError("계획 요약 생성 실패")

        plan = Plan(
            plan_id=f"plan_{origin_id[:8]}_{dest_id[:8]}_{int(datetime.now().timestamp())}",
            conversation_id=request.conversation_id,
            origin_place_id=origin_id,
            destination_place_id=dest_id,
            arrival_deadline=request.arrival_deadline,
            target_arrival_at=selected_summary.target_arrival_at,
            recommended_leave_at=selected_summary.recommended_leave_at,
            total_duration_minutes=selected_summary.total_duration_minutes,
            transport_mode=selected_summary.transport_mode,
            comparison=comparison,
            buffer_applied=buffer_minutes,
            notes=f"권장 출발시각: {selected_summary.recommended_leave_at.strftime('%H:%M')} "
            f"(도착 마감 {arrival_deadline.strftime('%H:%M')} 기준, "
            f"여유 {request.arrival_preference_minutes or 0}분 + Buffer {buffer_minutes}분)",
        )

        return plan

    def _generate_mock_options(
        self,
        origin_id: str,
        dest_id: str,
        transport_mode: str | None = None,
    ) -> list[dict]:
        """Mock 이동 옵션 생성 (제공자 결과 없을 때 fallback)."""
        import random

        base_duration = random.randint(20, 60)
        mode = transport_mode or "subway"

        options = []
        for i in range(min(3, random.randint(1, 3))):
            duration = base_duration + random.randint(-5, 10)
            option = {
                "option_id": f"opt_{mode}_{i + 1}",
                "legs": [
                    {
                        "mode": mode,
                        "departure_at": None,
                        "arrival_at": None,
                        "origin_place_id": origin_id,
                        "destination_place_id": dest_id,
                        "route_id": f"route_{i + 1}",
                        "leg_index": 0,
                        "duration_minutes": duration,
                        "distance_meters": duration * 500,
                    }
                ],
                "total_duration_minutes": duration,
                "total_distance_meters": duration * 500,
                "departure_at": None,
                "arrival_at": None,
                "price": duration * 500,
                "transport_mode": mode,
                "confidence": 0.85 + random.uniform(0, 0.1),
            }
            options.append(option)

        return options

    def _generate_reasoning(
        self,
        opt_data: dict,
        transport_mode: str | None,
        total_duration: int,
        target_arrival: datetime,
        buffer_minutes: int,
        arrival_preference: int,
    ) -> str:
        """옵션별 권장 출발시각 근거 생성."""
        mode = opt_data.get("transport_mode", transport_mode or "unknown")
        legs = opt_data.get("legs", [])

        parts = []
        if mode == "subway":
            parts.append(f"지하철 이용, {total_duration}분 소요")
            if len(legs) > 1:
                parts.append(f"환승 {len(legs) - 1}회 포함")
            else:
                parts.append("직행 노선")
        elif mode == "bus":
            parts.append(f"버스 이용, {total_duration}분 소요")
        elif mode == "walking":
            parts.append(
                f"도보 {total_duration}분 ({opt_data.get('total_distance_meters', 0) // 1000}km)"
            )
        elif mode == "taxi":
            parts.append(f"택시 이용, 약 {total_duration}분")
        else:
            parts.append(f"{total_duration}분 소요")

        # 도착 마감 기준 설명
        deadline_str = target_arrival.strftime("%H:%M")
        parts.append(f"도착 마감 {deadline_str} 기준")
        parts.append(
            f"도착 여유 {arrival_preference}분 + Buffer {buffer_minutes}분 반영"
        )

        return ", ".join(parts)

    def _generate_comparison_reason(self, summaries: list[PlanSummary]) -> str:
        """비교 근거 요약 생성."""
        if not summaries:
            return ""

        fastest = min(summaries, key=lambda s: s.total_duration_minutes)
        return (
            f"총 {len(summaries)}개 후보 중 "
            f"가장 빠른 옵션은 {fastest.option_id} ({fastest.total_duration_minutes}분). "
            f"권장 출발시각: {fastest.recommended_leave_at.strftime('%H:%M')}"
        )

    # ─────────────────────────────────────────────
    # 막차 계획 통합 (User Story 2 - T047)
    # ─────────────────────────────────────────────

    async def plan_last_journey(
        self,
        request: TripRequest,
        buffer_minutes: int = 5,
    ) -> Plan:
        """막차 귀가 경로 계획 생성.

        Args:
            request: TripRequest (막차 계획 요청)
            buffer_minutes: 완충 시간 (분)

        Returns:
            Plan: 막차 경로 계획 응답 (is_last_journey=True)

        Raises:
            ValueError: 출발지 미확정 시
            LastJourneyUnsupportedError: 막차 데이터 미지원 시
            NoFeasibleJourneyError: 지원 범위에서 경로 없음 시
        """
        from app.services.last_journey_service import (
            LastJourneyService,
        )

        # 출발지 확정 검증
        if not request.origin_place_id or not request.origin_place_id.strip():
            raise ValueError(
                f"출발지가 확정되지 않았습니다. origin_place_id가 필요합니다. "
                f"conversation_id={request.conversation_id}"
            )

        # 막차 서비스 생성 및 실행
        last_journey_service = LastJourneyService(
            routing_provider=self.routing_provider
        )
        return await last_journey_service.plan_last_journey(
            request=request,
            buffer_minutes=buffer_minutes,
        )

    async def check_last_journey_availability(
        self,
        request: TripRequest,
    ) -> dict:
        """막차 가용성 확인.

        Args:
            request: TripRequest

        Returns:
            dict: {supported: bool, has_feasible: bool, message: str}
        """
        from app.services.last_journey_service import LastJourneyService

        last_journey_service = LastJourneyService(
            routing_provider=self.routing_provider
        )

        supported = await last_journey_service.check_last_journey_supported()

        if not supported:
            return {
                "supported": False,
                "has_feasible": False,
                "message": "막차 운행 정보를 제공하는 데이터 제공자가 없습니다.",
            }

        # 간단한 가용성 확인 (실제 경로 계산 없이)
        try:
            # 제공자에게 막차 시간대 옵션 조회 시도
            now_seoul = datetime.now(SEOUL_TZ)
            last_departure = now_seoul.replace(
                hour=23, minute=0, second=0, microsecond=0
            )

            result = await self.routing_provider.search_options(
                origin_place_id=request.origin_place_id,
                destination_place_id=request.destination_place_id,
                departure_at=last_departure.isoformat(),
                transport_mode=request.transport_mode,
                max_options=1,
            )

            has_feasible = result.ok and bool(result.data)
            message = (
                "막차 운행 시간대에 이용 가능한 경로가 있습니다."
                if has_feasible
                else "막차 운행 시간대에 이용 가능한 경로가 없습니다."
            )

            return {
                "supported": True,
                "has_feasible": has_feasible,
                "message": message,
            }
        except Exception as e:
            logger.warning(f"막차 가용성 확인 중 오류: {e}")
            return {
                "supported": True,
                "has_feasible": False,
                "message": f"막차 가용성 확인 중 오류: {e}",
            }
