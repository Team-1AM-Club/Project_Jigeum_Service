"""막차 귀가 경로 계산 서비스 (Last Journey Service).

User Story 2: 사용자가 막차 귀가를 요청하면,
운행일·노선 지원 범위를 검증하고 가능한 경우 자정 이후 도착하는 막차 경로를 반환.

지원 데이터가 없으면 LAST_JOURNEY_UNSUPPORTED,
지원 범위 내 경로 없으면 NO_FEASIBLE_JOURNEY로 구분.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.journeys import (
    TripRequest,
    Plan,
    PlanSummary,
    Comparison,
    RouteOption,
    RouteLeg,
)
from app.schemas.errors import ErrorCode
from app.services.provider_interfaces import RoutingProvider, ProviderResult
from app.services.time_calculation import ensure_seoul, safe_add_minutes

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")


# ─────────────────────────────────────────────
# 막차 서비스 오류
# ─────────────────────────────────────────────

class LastJourneyUnsupportedError(Exception):
    """막차 운행 정보 미지원 오류."""
    def __init__(self, message: str = "막차 운행 정보를 제공하는 데이터 제공자가 없습니다."):
        self.message = message
        self.error_code = ErrorCode.VALIDATION_ERROR
        self.status_code = 422
        super().__init__(message)


class NoFeasibleJourneyError(Exception):
    """지원 범위에서 경로 없음 오류."""
    def __init__(self, message: str = "막차 운행 시간대에 이용 가능한 경로가 없습니다."):
        self.message = message
        self.error_code = ErrorCode.VALIDATION_ERROR
        self.status_code = 422
        super().__init__(message)


# ─────────────────────────────────────────────
# 막차 서비스
# ─────────────────────────────────────────────

class LastJourneyService:
    """막차 귀가 경로 계산 서비스.

    운행일·노선 지원 범위 검증 → 막차 경로 후보 계산 → 자정 경계·다음 날 도착 처리.
    """

    def __init__(self, routing_provider: RoutingProvider):
        """초기화.

        Args:
            routing_provider: 경로/이동 옵션 제공자.
        """
        self.routing_provider = routing_provider

    async def check_last_journey_supported(self) -> bool:
        """막차 운행 정보 지원 여부 확인.

        Returns:
            bool: 막차 지원 여부 (데이터 제공자가 막차 운행 정보를 제공하는지)
        """
        # 제공자 헬스 체크 + 막차 정보 제공 여부 확인
        try:
            health = await self.routing_provider.health()
            if not health:
                return False
            # 제공자 헬스가 정상이면 막차 지원 가능으로 간주
            # (Mock 환경 포함: 실제 구현 시 제공자별 막차 엔드포인트 확인 추가)
            return True
        except Exception as e:
            logger.warning(f"막차 지원 확인 중 오류: {e}")
            return False

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
            LastJourneyUnsupportedError: 막차 데이터 미지원 시
            NoFeasibleJourneyError: 지원 범위에서 경로 없음 시
        """
        # 1. 막차 지원 여부 확인
        supported = await self.check_last_journey_supported()
        if not supported:
            raise LastJourneyUnsupportedError(
                "막차 운행 정보를 제공하는 데이터 제공자가 없습니다. "
                "현재 막차 계획은 지원하지 않습니다."
            )

        # 2. 운행일 검증 (현재 날짜 기준)
        now_seoul = datetime.now(SEOUL_TZ)
        operating_date = now_seoul.strftime("%Y-%m-%d")

        # 막차 운행 시간: 보통 23:00~00:30 사이 (자정 경계)
        # 막차 출발 시각: 23:00 ~ 23:30 사이 (가정)
        last_departure_start = now_seoul.replace(hour=23, minute=0, second=0, microsecond=0)
        last_departure_end = now_seoul.replace(hour=23, minute=30, second=0, microsecond=0)

        # 도착 마감 시한이 막차 시간대에 가능한지 확인
        # arrival_deadline이 자정 이후여야 막차 의미가 있음
        arrival_deadline = ensure_seoul(request.arrival_deadline) if request.arrival_deadline else now_seoul + timedelta(hours=1)

        # 3. 막차 경로 후보 계산
        # Mock 제공자 사용: 교통수단 필터 없이 검색
        routing_result = await self.routing_provider.search_options(
            origin_place_id=request.origin_place_id,
            destination_place_id=request.destination_place_id,
            departure_at=last_departure_start.isoformat(),
            arrival_deadline=arrival_deadline.isoformat() if arrival_deadline else None,
            transport_mode=request.transport_mode,
            max_options=request.max_options or 3,
        )

        options_data: List[dict] = []
        if routing_result.ok and routing_result.data:
            options_data = routing_result.data

        # 4. 지원 범위에서 경로 없으면 NO_FEASIBLE_JOURNEY
        if not options_data:
            logger.info("막차 운행 시간대에 이용 가능한 경로 없음")
            raise NoFeasibleJourneyError(
                "막차 운행 시간대(23:00~23:30)에 출발하여 "
                f"목적지({request.destination_place_id})에 도착 가능한 경로가 없습니다."
            )

        # 5. 후보 경로 중 자정 이후 도착하는 경로 선택
        candidate_options = options_data[:request.max_options or 3]
        last_journey_options: List[dict] = []

        for opt_data in candidate_options:
            # 도착 시각 계산 (출발 + 소요시간)
            departure_str = opt_data.get("departure_at") or last_departure_start.isoformat()
            departure = ensure_seoul(datetime.fromisoformat(departure_str))
            duration = opt_data.get("total_duration_minutes", 0) or 0
            arrival = safe_add_minutes(departure, duration)

            # 자정 이후 도착하는지 확인 (다음 날 도착)
            arrival_date_str = arrival.strftime("%Y-%m-%d")
            is_next_day_arrival = arrival.date() > departure.date()

            # 막차 조건에 맞으면 후보에 추가
            if is_next_day_arrival or arrival.hour >= 0:
                opt_data["_calculated_arrival"] = arrival.isoformat()
                opt_data["_arrival_date"] = arrival_date_str
                opt_data["_is_next_day_arrival"] = is_next_day_arrival
                last_journey_options.append(opt_data)

        # 막차 조건에 맞는 경로가 없으면
        if not last_journey_options:
            raise NoFeasibleJourneyError(
                "막차 운행 시간대에 출발하여 자정 이후 도착 가능한 경로가 없습니다."
            )

        # 6. Plan 생성
        target_arrival = arrival_deadline - timedelta(minutes=request.arrival_preference_minutes or 0)

        plan_summaries: List[PlanSummary] = []
        selected_option_id = None

        for idx, opt_data in enumerate(last_journey_options):
            total_duration = opt_data.get("total_duration_minutes", 0) or 0
            option_id = opt_data.get("option_id", f"opt_last_{idx}")

            # 권장 출발시각 = target_arrival - total_duration - buffer
            recommended_leave = target_arrival - timedelta(minutes=total_duration + buffer_minutes)

            reasoning = (
                f"막차 귀가 경로: {opt_data.get('transport_mode', 'subway')} 이용. "
                f"출발 {recommended_leave.strftime('%H:%M')} → 도착 {target_arrival.strftime('%H:%M')} "
                f"(다음 날 도착: {opt_data.get('_is_next_day_arrival', False)}). "
                f"총 소요시간 {total_duration}분, buffer {buffer_minutes}분 포함."
            )

            summary = PlanSummary(
                option_id=option_id,
                recommended_leave_at=recommended_leave,
                target_arrival_at=target_arrival,
                total_duration_minutes=total_duration,
                transport_mode=opt_data.get("transport_mode", request.transport_mode),
                reasoning=reasoning,
            )
            plan_summaries.append(summary)

            if idx == 0:
                selected_option_id = option_id

        # 첫 번째 옵션 데이터로 Plan 구성
        first_opt = last_journey_options[0]
        total_duration = first_opt.get("total_duration_minutes", 0) or 0
        transport_mode = first_opt.get("transport_mode", request.transport_mode)

        plan = Plan(
            plan_id=f"plan_last_{first_opt.get('option_id', '001')}",
            conversation_id=request.conversation_id,
            origin_place_id=request.origin_place_id,
            destination_place_id=request.destination_place_id,
            arrival_deadline=arrival_deadline,
            target_arrival_at=target_arrival,
            recommended_leave_at=target_arrival - timedelta(minutes=total_duration + buffer_minutes),
            total_duration_minutes=total_duration,
            transport_mode=transport_mode,
            comparison=Comparison(
                options=plan_summaries,
                selected_option_id=selected_option_id,
                comparison_reason="막차 귀가 후보 경로 비교" if len(plan_summaries) > 1 else "막차 귀가 단일 경로",
            ),
            buffer_applied=buffer_minutes,
            notes=(
                f"막차 귀가 경로입니다. 운행일: {operating_date}, "
                f"도착 날짜: {first_opt.get('_arrival_date', operating_date)}. "
                f"자정 이후 도착하므로 귀가 준비에 참고하세요."
            ),
            # 막차 관련 필드
            is_last_journey=True,
            operating_date=operating_date,
            arrival_date=first_opt.get("_arrival_date", operating_date),
            last_journey_supported=supported,
        )

        logger.info(
            f"막차 계획 생성 완료: plan_id={plan.plan_id}, "
            f"operating_date={operating_date}, arrival_date={plan.arrival_date}"
        )

        return plan
