"""재탐색 서비스 (Replan Service).

User Story 3: 사용자가 놓침·변경 후 재탐색을 요청하면,
현재 서버 시각 기준으로 새 경로를 계산하고 이전 선택 대비 시각 변화를 반환.

재탐색 실패·취소는 이전 선택을 삭제하지 않으며,
이전 경로가 여전히 유효하다는 보장으로 표시하지 않음.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

from app.schemas.journeys import (
    TripRequest,
    Plan,
    PlanSummary,
    Comparison,
    ReplanRequest,
    ReplanResponse,
    ReplanComparison,
    ReplanReason,
)
from app.schemas.errors import ErrorCode
from app.services.provider_interfaces import RoutingProvider, ProviderResult
from app.services.plan_service import PlanService
from app.services.time_calculation import ensure_seoul

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")


# ─────────────────────────────────────────────
# 재탐색 서비스
# ─────────────────────────────────────────────

class ReplanService:
    """재탐색 서비스.

    현재 서버 시각 기준 새 경로 계산,
    이전 선택 비교 (arrival_change_minutes, leave_change_minutes),
    이전 선택 유지 보장.
    """

    def __init__(self, plan_service: PlanService):
        """초기화.

        Args:
            plan_service: 경로 계획 서비스 (재탐색 시 내부적으로 사용)
        """
        self.plan_service = plan_service

    async def replan(
        self,
        request: ReplanRequest,
        buffer_minutes: int = 5,
    ) -> ReplanResponse:
        """재탐색 실행.

        Args:
            request: ReplanRequest (재탐색 요청)
            buffer_minutes: 완충 시간 (분)

        Returns:
            ReplanResponse: 재탐색 결과 + 이전 선택 대비 변화

        Raises:
            ValueError: 요청 검증 실패 시
        """
        # 1. 요청 검증
        if not request.conversation_id:
            raise ValueError("conversation_id가 필요합니다.")

        if not request.trip or not request.trip.get("origin_place_id"):
            raise ValueError("재탐색할 trip 정보(origin_place_id)가 필요합니다.")

        if not request.user_confirmed:
            raise ValueError("사용자 확인이 필요합니다. user_confirmed=true로 재요청하세요.")

        # 2. 현재 서버 시각 기준 새 경로 계산
        now_seoul = datetime.now(SEOUL_TZ)

        # 재탐색용 TripRequest 생성
        # current_origin_place_id가 있으면 이를 출발지로 사용, 없으면 trip의 origin 사용
        origin_id = request.current_origin_place_id or request.trip.get("origin_place_id")
        dest_id = request.trip.get("destination_place_id")

        if not origin_id:
            raise ValueError("출발지(origin_place_id)가 필요합니다.")

        if not dest_id:
            raise ValueError("목적지(destination_place_id)가 필요합니다.")

        # 새 plan 요청을 위한 TripRequest 생성
        # arrival_deadline: 현재 시각에서 적절한 마감 시각 설정
        # (기존 계획이 있으면 기존 target_arrival_at 기준으로)
        arrival_deadline = now_seoul + timedelta(hours=2)  # 기본 2시간 후

        if request.previous_plan:
            prev_target = request.previous_plan.get("target_arrival_at")
            if prev_target:
                try:
                    prev_dt = ensure_seoul(datetime.fromisoformat(prev_target))
                    # 이전 계획 대비 최소 동일한 도착 시각 보장
                    arrival_deadline = max(now_seoul + timedelta(minutes=30), prev_dt)
                except (ValueError, TypeError):
                    pass

        trip_request = TripRequest(
            conversation_id=request.conversation_id,
            origin_place_id=origin_id,
            destination_place_id=dest_id,
            arrival_deadline=arrival_deadline,
            arrival_preference_minutes=request.previous_plan.get("arrival_preference_minutes", 10) if request.previous_plan else 10,
            transport_mode=request.trip.get("transport_mode"),
            max_options=request.max_options or 3,
        )

        # 3. 새 경로 계산 (PlanService 사용)
        new_plan = await self.plan_service.plan(
            request=trip_request,
            buffer_minutes=buffer_minutes,
        )

        # 4. 이전 선택 대비 변화 계산
        arrival_change_minutes = None
        leave_change_minutes = None

        if request.previous_plan:
            prev_target_str = request.previous_plan.get("target_arrival_at")
            prev_leave_str = request.previous_plan.get("recommended_leave_at")

            if prev_target_str and new_plan.target_arrival_at:
                try:
                    prev_target = ensure_seoul(datetime.fromisoformat(prev_target_str))
                    new_target = ensure_seoul(new_plan.target_arrival_at)
                    arrival_change_minutes = int((new_target - prev_target).total_seconds() / 60)
                except (ValueError, TypeError):
                    pass

            if prev_leave_str and new_plan.recommended_leave_at:
                try:
                    prev_leave = ensure_seoul(datetime.fromisoformat(prev_leave_str))
                    new_leave = ensure_seoul(new_plan.recommended_leave_at)
                    leave_change_minutes = int((new_leave - prev_leave).total_seconds() / 60)
                except (ValueError, TypeError):
                    pass

        # 5. 이전 선택 유지 확인 (삭제되지 않음)
        previous_plan_preserved = True
        previous_plan_valid = False  # 이전 경로가 여전히 유효한지는 보장되지 않음

        # 6. ReplanResponse 생성
        comparison = ReplanComparison(
            new_plan=new_plan,
            arrival_change_minutes=arrival_change_minutes,
            leave_change_minutes=leave_change_minutes,
            previous_plan_preserved=previous_plan_preserved,
            previous_plan_valid=previous_plan_valid,
        )

        # notes 생성
        notes_parts = []
        if arrival_change_minutes is not None:
            if arrival_change_minutes > 0:
                notes_parts.append(f"이전 계획 대비 {arrival_change_minutes}분 늦게 도착합니다.")
            elif arrival_change_minutes < 0:
                notes_parts.append(f"이전 계획 대비 {abs(arrival_change_minutes)}분 일찍 도착합니다.")
            else:
                notes_parts.append("이전 계획과 도착 시각이 동일합니다.")

        if leave_change_minutes is not None:
            if leave_change_minutes > 0:
                notes_parts.append(f"출발 시각도 {leave_change_minutes}분 늦어집니다.")
            elif leave_change_minutes < 0:
                notes_parts.append(f"출발 시각도 {abs(leave_change_minutes)}분 앞당겨집니다.")

        notes = " ".join(notes_parts) if notes_parts else "재탐색이 완료되었습니다."

        replan_response = ReplanResponse(
            replan_id=f"replan_{uuid.uuid4().hex[:12]}",
            conversation_id=request.conversation_id,
            reason=request.reason,
            comparison=comparison,
            notes=notes,
        )

        logger.info(
            f"재탐색 완료: replan_id={replan_response.replan_id}, "
            f"arrival_change={arrival_change_minutes}, leave_change={leave_change_minutes}"
        )

        return replan_response

    async def check_replan_feasibility(
        self,
        request: ReplanRequest,
    ) -> dict:
        """재탐색 가능성 사전 확인.

        Args:
            request: ReplanRequest

        Returns:
            dict: {feasible: bool, reason: str, estimated_arrival_change: Optional[int]}
        """
        # 기본 점검
        if not request.trip or not request.trip.get("origin_place_id"):
            return {"feasible": False, "reason": "출발지 정보가 필요합니다."}

        if not request.trip.get("destination_place_id"):
            return {"feasible": False, "reason": "목적지 정보가 필요합니다."}

        if not request.user_confirmed:
            return {"feasible": False, "reason": "사용자 확인이 필요합니다."}

        # 간단한 가용성 확인
        try:
            origin_id = request.current_origin_place_id or request.trip.get("origin_place_id")
            dest_id = request.trip.get("destination_place_id")

            result = await self.plan_service.routing_provider.search_options(
                origin_place_id=origin_id,
                destination_place_id=dest_id,
                transport_mode=request.trip.get("transport_mode"),
                max_options=1,
            )

            if result.ok and result.data:
                return {
                    "feasible": True,
                    "reason": "재탐색 가능한 경로가 있습니다.",
                    "estimated_arrival_change": None,  # 실제 계산 전까지 알 수 없음
                }
            else:
                return {
                    "feasible": False,
                    "reason": "현재 위치에서 목적지까지 이용 가능한 경로가 없습니다.",
                    "estimated_arrival_change": None,
                }
        except Exception as e:
            logger.warning(f"재탐색 가능성 확인 중 오류: {e}")
            return {
                "feasible": False,
                "reason": f"재탐색 가능성 확인 중 오류: {e}",
                "estimated_arrival_change": None,
            }
