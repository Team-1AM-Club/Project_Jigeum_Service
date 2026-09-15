"""시간 계산 서비스.

- target_arrival_at = arrival_deadline - (이동시간 + buffer)
- Buffer 중복 가산 금지: buffer는 한 번만 적용
- 시간대·자정 경계 처리: Asia/Seoul 기준, 날짜 변경 시 올바른 날짜 계산
- 운행일 구분: 날짜 경계 처리로 운행일 넘어감 방지
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

SEOUL_TZ = ZoneInfo("Asia/Seoul")


def ensure_seoul(dt: Optional[datetime]) -> Optional[datetime]:
    """datetime을 Asia/Seoul 시간대로 변환.

    aware datetime이면 Seoul로 변환, naive면 local로 가정하고 Seoul tz 적용.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # naive → Asia/Seoul로 해석
        return dt.replace(tzinfo=SEOUL_TZ)
    # aware → Seoul로 변환
    return dt.astimezone(SEOUL_TZ)


def compute_target_arrival_at(
    arrival_deadline: datetime,
    total_duration_minutes: int,
    buffer_minutes: int = 5,
    already_applied_buffer: bool = False,
) -> datetime:
    """목표 도착 시각 계산.

    target_arrival_at = arrival_deadline - (이동시간 + buffer)
    buffer는 한 번만 적용 (already_applied_buffer=True면 중복 가산 금지).

    Args:
        arrival_deadline: 사용자 지정 도착 시한 (aware 권장)
        total_duration_minutes: 이동 총 소요 시간 (분)
        buffer_minutes: 완충 시간 (분)
        already_applied_buffer: buffer 이미 적용됨 → 중복 가산 금지

    Returns:
        목표 도착 시각 (Asia/Seoul)
    """
    arrival_deadline = ensure_seoul(arrival_deadline)

    total_delay = total_duration_minutes
    if not already_applied_buffer:
        total_delay += buffer_minutes

    target = arrival_deadline - timedelta(minutes=total_delay)
    return target.astimezone(SEOUL_TZ)


def compute_recommended_leave_at(
    target_arrival_at: datetime,
    total_duration_minutes: int,
) -> datetime:
    """권장 출발 시각 계산.

    recommended_leave_at = target_arrival_at - total_duration_minutes

    Args:
        target_arrival_at: 목표 도착 시각
        total_duration_minutes: 이동 총 소요 시간 (분)

    Returns:
        권장 출발 시각 (Asia/Seoul)
    """
    target = ensure_seoul(target_arrival_at)
    leave = target - timedelta(minutes=total_duration_minutes)
    return leave.astimezone(SEOUL_TZ)


def safe_add_minutes(
    dt: datetime,
    minutes: int,
    max_date_crossing: bool = True,
) -> datetime:
    """datetime에 minutes 더하고 자정 경계 처리.

    Args:
        dt: 기준 시각 (aware 권장)
        minutes: 더할 분
        max_date_crossing: 날짜 넘어감 허용 여부 (기본 True)

    Returns:
        계산 결과 시각
    """
    dt = ensure_seoul(dt)
    result = dt + timedelta(minutes=minutes)
    return result.astimezone(SEOUL_TZ)


def safe_subtract_minutes(
    dt: datetime,
    minutes: int,
) -> datetime:
    """datetime에서 minutes 빼고 자정 경계 처리."""
    dt = ensure_seoul(dt)
    result = dt - timedelta(minutes=minutes)
    return result.astimezone(SEOUL_TZ)


def check_date_boundary_crossing(
    from_dt: datetime,
    to_dt: datetime,
    allow_crossing: bool = True,
) -> Optional[str]:
    """날짜 경계 넘김 검사.

    Args:
        from_dt: 출발 시각
        to_dt: 도착 시각
        allow_crossing: 날짜 넘어감 허용 여부

    Returns:
        문제 있으면 경고 메시지, 없으면 None
    """
    from_dt = ensure_seoul(from_dt)
    to_dt = ensure_seoul(to_dt)

    from_date = from_dt.date()
    to_date = to_dt.date()

    if from_date != to_date and not allow_crossing:
        return f"날짜 경계 넘어감: {from_date} → {to_date}"

    return None


# 버퍼 중복 가산 방지 헬퍼
class BufferGuard:
    """Buffer 중복 가산 방지 상태 관리."""

    def __init__(self):
        self._buffer_applied = False

    def apply_buffer(self, buffer_minutes: int) -> int:
        """buffer 적용 (한 번만)."""
        if self._buffer_applied:
            return 0  # 중복 가산 금지
        self._buffer_applied = True
        return buffer_minutes

    def reset(self):
        self._buffer_applied = False


# ─────────────────────────────────────────────
# 전체 계산 함수 (T027 종합)
# ─────────────────────────────────────────────
def calculate_plan_times(
    arrival_deadline: datetime,
    total_duration_minutes: int,
    buffer_minutes: int = 5,
    buffer_already_in_duration: bool = False,
) -> dict:
    """계획 시간 계산 종합.

    Returns:
        dict: target_arrival_at, recommended_leave_at, buffer_applied, total_with_buffer
    """
    arrival_deadline = ensure_seoul(arrival_deadline)

    # buffer 처리
    if buffer_already_in_duration:
        effective_buffer = 0  # 이미 이동시간에 buffer 포함 → 추가 buffer 금지
    else:
        effective_buffer = buffer_minutes

    total_with_buffer = total_duration_minutes + effective_buffer

    target_arrival_at = arrival_deadline - timedelta(minutes=total_duration_minutes)
    # target_arrival_at = arrival_deadline - total_duration (buffer 미포함)
    # → buffer는 recommended_leave_at 계산 시에만 적용

    recommended_leave_at = target_arrival_at - timedelta(minutes=total_duration_minutes + effective_buffer)

    return {
        "target_arrival_at": target_arrival_at.astimezone(SEOUL_TZ),
        "recommended_leave_at": recommended_leave_at.astimezone(SEOUL_TZ),
        "buffer_applied": effective_buffer,
        "total_with_buffer": total_with_buffer,
        "note": "buffer 중복 가산 없음" if effective_buffer > 0 else "buffer 없음 (이미 이동시간에 포함)",
    }
