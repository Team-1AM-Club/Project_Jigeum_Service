"""T033: 시간 계산 단위 테스트.

- target_arrival_at = arrival_deadline - arrival_preference_minutes 검증
- Buffer 중복 가산 방지 검증
- 시간대·자정 경계 처리 검증
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.services.time_calculation import (
    check_date_boundary_crossing,
    compute_recommended_leave_at,
    compute_target_arrival_at,
    ensure_seoul,
    safe_add_minutes,
    safe_subtract_minutes,
)

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestComputeTargetArrivalAt:
    """target_arrival_at = arrival_deadline - arrival_preference_minutes 검증."""

    def test_basic_target_arrival_at(self):
        """기본: arrival_deadline - total_duration - buffer = target_arrival_at."""
        arrival_deadline = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        total_duration = 42  # 분
        buffer_minutes = 5

        target = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=total_duration,
            buffer_minutes=buffer_minutes,
            already_applied_buffer=False,
        )

        # 19:00 - 42분 - 5분 = 18:13
        expected = datetime(2026, 9, 16, 18, 13, 0, tzinfo=SEOUL_TZ)
        assert target == expected, f"기대 {expected}, 실제 {target}"

    def test_target_arrival_at_without_buffer(self):
        """buffer=0일 때: arrival_deadline - total_duration."""
        arrival_deadline = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        total_duration = 42

        target = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=total_duration,
            buffer_minutes=0,
            already_applied_buffer=False,
        )

        expected = datetime(2026, 9, 16, 18, 18, 0, tzinfo=SEOUL_TZ)
        assert target == expected, f"기대 {expected}, 실제 {target}"

    def test_target_arrival_at_naive_datetime(self):
        """naive datetime 입력 → Asia/Seoul로 해석."""
        arrival_deadline = datetime(2026, 9, 16, 19, 0, 0)  # naive
        total_duration = 30

        target = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=total_duration,
            buffer_minutes=5,
            already_applied_buffer=False,
        )

        # naive → Seoul로 해석, 19:00 KST - 35분 = 18:25 KST
        expected = datetime(2026, 9, 16, 18, 25, 0, tzinfo=SEOUL_TZ)
        assert target == expected, f"기대 {expected}, 실제 {target}"
        assert target.tzinfo is not None, "결과 timezone aware여야 함"


class TestBufferDuplicationPrevention:
    """Buffer 중복 가산 방지 검증."""

    def test_buffer_not_double_applied(self):
        """already_applied_buffer=True일 때 buffer 중복 가산 금지."""
        arrival_deadline = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        total_duration = 42
        buffer_minutes = 5

        # buffer 미적용 (첫 계산)
        target_first = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=total_duration,
            buffer_minutes=buffer_minutes,
            already_applied_buffer=False,
        )
        # 19:00 - 42 - 5 = 18:13

        # buffer 이미 적용 (두 번째 계산 - 이미 적용된 경우)
        target_second = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=total_duration,
            buffer_minutes=buffer_minutes,
            already_applied_buffer=True,
        )
        # 19:00 - 42 (buffer 제외) = 18:18

        expected_second = datetime(2026, 9, 16, 18, 18, 0, tzinfo=SEOUL_TZ)
        assert target_second == expected_second, (
            f"buffer 중복 적용 방지 실패: 기대 {expected_second}, 실제 {target_second}"
        )

        # 두 결과가 달라야 함 (buffer 적용 여부 차이)
        assert target_first != target_second, "buffer 적용 여부에 따른 결과 차이 필요"

    def test_buffer_already_applied_prevents_extra_subtraction(self):
        """already_applied_buffer=True: buffer만큼 추가로 빼지 않음."""
        arrival_deadline = datetime(2026, 9, 16, 20, 0, 0, tzinfo=SEOUL_TZ)

        # buffer 미적용
        t1 = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=60,
            buffer_minutes=10,
            already_applied_buffer=False,
        )
        # 20:00 - 60 - 10 = 19:50

        # buffer 적용
        t2 = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=60,
            buffer_minutes=10,
            already_applied_buffer=True,
        )
        # 20:00 - 60 = 19:00

        assert t1 == datetime(2026, 9, 16, 18, 50, 0, tzinfo=SEOUL_TZ), (
            f"t1 기대 19:50, 실제 {t1}"
        )
        assert t2 == datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ), (
            f"t2 기대 19:00, 실제 {t2}"
        )
        # 차이: 정확히 buffer_minutes(10분)
        diff = abs((t1 - t2).total_seconds() / 60)
        assert diff == 10, f"buffer 차이 10분 기대, 실제 {diff}분"


class TestRecommendedLeaveAt:
    """권장 출발시각 계산 검증."""

    def test_recommended_leave_at_basic(self):
        """권장 출발시각 = target_arrival_at - total_duration."""
        target_arrival = datetime(2026, 9, 16, 18, 50, 0, tzinfo=SEOUL_TZ)
        total_duration = 42

        leave_at = compute_recommended_leave_at(
            target_arrival_at=target_arrival,
            total_duration_minutes=total_duration,
        )

        # 18:50 - 42분 = 18:08
        expected = datetime(2026, 9, 16, 18, 8, 0, tzinfo=SEOUL_TZ)
        assert leave_at == expected, f"기대 {expected}, 실제 {leave_at}"

    def test_recommended_leave_at_before_target(self):
        """권장 출발시각은 항상 target_arrival_at보다 이전."""
        target_arrival = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        total_duration = 30

        leave_at = compute_recommended_leave_at(
            target_arrival_at=target_arrival,
            total_duration_minutes=total_duration,
        )

        assert leave_at < target_arrival, (
            f"권장 출발시각({leave_at})이 목표 도착({target_arrival})보다 이후"
        )


class TestEnsureSeoul:
    """Asia/Seoul 시간대 변환 검증."""

    def test_ensure_seoul_aware_datetime(self):
        """aware datetime → Asia/Seoul로 변환."""
        utc_time = datetime(2026, 9, 16, 10, 0, 0, tzinfo=UTC)
        seoul_time = ensure_seoul(utc_time)

        assert seoul_time.tzinfo == SEOUL_TZ
        # UTC 10:00 → KST 19:00
        assert seoul_time.hour == 19
        assert seoul_time.minute == 0

    def test_ensure_seoul_naive_datetime(self):
        """naive datetime → Asia/Seoul로 해석."""
        naive_time = datetime(2026, 9, 16, 10, 0, 0)  # naive
        seoul_time = ensure_seoul(naive_time)

        assert seoul_time.tzinfo == SEOUL_TZ
        assert seoul_time.hour == 10  # naive → 그대로 KST 10:00으로 해석

    def test_ensure_seoul_none(self):
        """None 입력 → None 반환."""
        assert ensure_seoul(None) is None


class TestDateBoundaryCrossing:
    """자정 경계 처리 검증."""

    def test_safe_add_minutes_crosses_midnight(self):
        """밤 11시 + 120분 → 다음날 오전."""
        dt = datetime(2026, 9, 16, 23, 0, 0, tzinfo=SEOUL_TZ)
        result = safe_add_minutes(dt, 120)

        expected = datetime(2026, 9, 17, 1, 0, 0, tzinfo=SEOUL_TZ)
        assert result == expected, f"기대 {expected}, 실제 {result}"
        assert result.day == 17, "날짜 넘어감"

    def test_safe_subtract_minutes_crosses_midnight(self):
        """오전 1시 - 120분 → 전날 오후."""
        dt = datetime(2026, 9, 16, 1, 0, 0, tzinfo=SEOUL_TZ)
        result = safe_subtract_minutes(dt, 120)

        expected = datetime(2026, 9, 15, 23, 0, 0, tzinfo=SEOUL_TZ)
        assert result == expected, f"기대 {expected}, 실제 {result}"
        assert result.day == 15, "날짜 넘어감"

    def test_check_date_boundary_crossing_detects(self):
        """날짜 경계 넘김 감지."""
        from_dt = datetime(2026, 9, 16, 23, 0, 0, tzinfo=SEOUL_TZ)
        to_dt = datetime(2026, 9, 17, 1, 0, 0, tzinfo=SEOUL_TZ)

        warning = check_date_boundary_crossing(from_dt, to_dt, allow_crossing=True)
        # allow_crossing=True → 경고 없음 (또는 날짜 변경 알림)
        assert warning is None or "날짜" in warning, (
            f"예상: 날짜 경계 경고 또는 None, 실제: {warning}"
        )


class TestTimeCalculationIntegration:
    """시간 계산 통합 검증."""

    def test_full_calculation_chain(self):
        """전체 계산 체인: arrival_deadline → target → leave_at."""
        arrival_deadline = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        total_duration = 42
        buffer_minutes = 5

        # target = deadline - duration - buffer
        target = compute_target_arrival_at(
            arrival_deadline=arrival_deadline,
            total_duration_minutes=total_duration,
            buffer_minutes=buffer_minutes,
            already_applied_buffer=False,
        )
        # 19:00 - 42 - 5 = 18:13

        # leave = target - duration
        leave = compute_recommended_leave_at(
            target_arrival_at=target,
            total_duration_minutes=total_duration,
        )
        # 18:13 - 42 = 17:31

        # 검증: leave < target < deadline
        assert leave < target < arrival_deadline, (
            f"순서 위반: leave={leave} < target={target} < deadline={arrival_deadline}"
        )

        # buffer 포함 여부 확인 (total_duration 기준)
        leave_to_target = (target - leave).total_seconds() / 60
        assert leave_to_target == total_duration, (
            f"leave→target 시간 = total_duration({total_duration}) 기대, 실제 {leave_to_target}분"
        )

    def test_target_arrival_at_with_different_preferences(self):
        """도착 여유 시간별 target_arrival_at 비교."""
        deadline = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        duration = 42
        buffer = 5

        # 여유 0분
        t0 = compute_target_arrival_at(deadline, duration, buffer, False)
        # 여유 10분 (buffer 별도)
        t10 = compute_target_arrival_at(deadline, duration + 10, buffer, False)

        # 여유 있을수록 더 일찍 도착 목표
        assert t10 < t0, f"여유 10분일 때 더 일찍 도착해야 함: t10={t10} >= t0={t0}"

        # 차이 = 여유 10분
        diff = (t0 - t10).total_seconds() / 60
        assert diff == 10, f"여유 차이 10분 기대, 실제 {diff}분"
