"""제공자 클라이언트 추상 베이스 클래스 (Provider Interfaces).

실제 제공자와 Mock 제공자 모두 아래 추상 클래스를 구현한다.
각 인터페이스는 최소한의 계약만 정의하며, 구체적인 요청/응답 스키마는
호출 측에서 담당한다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional


# ─────────────────────────────────────────────
# 공통 결과 래퍼
# ─────────────────────────────────────────────
@dataclass
class ProviderResult:
    """제공자 호출 결과 공통 래퍼."""
    ok: bool
    data: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    http_status: Optional[int] = None


# ─────────────────────────────────────────────
# RoutingProvider: 경로/이동 옵션 조회
# ─────────────────────────────────────────────
class RoutingProvider(ABC):
    """경로 제공자 추상 베이스 클래스.

    출발지-도착지 간 이동 옵션(list of MobilityOption)을 반환한다.
    """

    @abstractmethod
    async def search_options(
        self,
        origin_place_id: str,
        destination_place_id: str,
        departure_at: Optional[str] = None,
        arrival_deadline: Optional[str] = None,
        transport_mode: Optional[str] = None,
        max_options: int = 5,
    ) -> ProviderResult:
        """이동 옵션 검색.

        Args:
            origin_place_id: 출발지 장소 ID
            destination_place_id: 도착지 장소 ID
            departure_at: 출발 희망 시각 (ISO 8601, 옵션)
            arrival_deadline: 도착 희망 시한 (ISO 8601, 옵션)
            transport_mode: 교통수단 필터 (subway|bus|walking|taxi|bicycle, 옵션)
            max_options: 최대 옵션 수

        Returns:
            ProviderResult: ok=True 시 data에 MobilityOption 리스트 포함
        """
        ...

    @abstractmethod
    async def health(self) -> bool:
        """제공자 헬스 체크. 연결 가능 여부 반환."""
        ...


# ─────────────────────────────────────────────
# TransitProvider: 환승/대중교통 상세
# ─────────────────────────────────────────────
class TransitProvider(ABC):
    """대중교통/환승 제공자 추상 베이스 클래스.

    특정 옵션의 상세 환승 정보, 운행 시간표, 실시간 정보 등을 반환한다.
    """

    @abstractmethod
    async def get_transit_details(
        self,
        option_id: str,
        departure_at: Optional[str] = None,
    ) -> ProviderResult:
        """특정 옵션의 대중교통 상세 정보 조회.

        Args:
            option_id: 이동 옵션 ID
            departure_at: 출발 시각 (ISO 8601, 옵션)

        Returns:
            ProviderResult: ok=True 시 data에 상세 transit 정보 포함
        """
        ...

    @abstractmethod
    async def health(self) -> bool:
        """제공자 헬스 체크."""
        ...


# ─────────────────────────────────────────────
# PlaceProvider: 장소 검색
# ─────────────────────────────────────────────
class PlaceProvider(ABC):
    """장소 검색 제공자 추상 베이스 클래스.

    사용자 쿼리 기반 장소 검색 결과를 반환한다.
    """

    @abstractmethod
    async def search_places(
        self,
        query: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: Optional[int] = None,
        limit: int = 5,
        offset: int = 0,
    ) -> ProviderResult:
        """장소 검색.

        Args:
            query: 검색어
            latitude: 중심 위도 (옵션)
            longitude: 중심 경도 (옵션)
            radius_meters: 검색 반경 (미터, 옵션)
            limit: 최대 결과 수
            offset: 오프셋

        Returns:
            ProviderResult: ok=True 시 data에 PlaceResult 리스트 포함
        """
        ...

    @abstractmethod
    async def health(self) -> bool:
        """제공자 헬스 체크."""
        ...


# ─────────────────────────────────────────────
# ModelProvider: 자연어 해석 (LLM/규칙 기반)
# ─────────────────────────────────────────────
class ModelProvider(ABC):
    """자연어 해석 제공자 추상 베이스 클래스.

    사용자 자연어 입력을 구조화된 조건/의도로 해석한다.
    실제 구현에서는 LLM API 또는 규칙 기반 파서를 사용할 수 있다.
    """

    @abstractmethod
    async def interpret(
        self,
        user_text: str,
        context: Optional[dict] = None,
    ) -> ProviderResult:
        """사용자 발화 자연어 해석.

        Args:
            user_text: 사용자 발화 텍스트
            context: 대화 컨텍스트 (conversation_id, 기존 조건 등, 옵션)

        Returns:
            ProviderResult: ok=True 시 data에 해석 결과 (dict) 포함
        """
        ...

    @abstractmethod
    async def health(self) -> bool:
        """제공자 헬스 체크."""
        ...
