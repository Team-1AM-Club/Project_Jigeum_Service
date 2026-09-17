"""GET /api/v1/places - 장소 검색 엔드포인트."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from app.schemas.common import Envelope, Meta
from app.schemas.errors import ErrorCode
from app.schemas.places import PlaceResult, PlacesResponse
from app.services.mock.mock_providers import MockPlaceProvider

router = APIRouter()
SEOUL_TZ = ZoneInfo("Asia/Seoul")
mock_place_provider = MockPlaceProvider()


@router.get("/places", response_model=Envelope)
async def get_places(
    query: str = Query(..., min_length=1, max_length=200, description="검색어"),
    latitude: float = Query(None, ge=-90, le=90, description="중심 위도 (옵션)"),
    longitude: float = Query(None, ge=-180, le=180, description="중심 경도 (옵션)"),
    radius_meters: int = Query(
        None, ge=100, le=50000, description="검색 반경 미터 (옵션)"
    ),
    limit: int = Query(5, ge=1, le=20, description="최대 결과 수"),
    offset: int = Query(0, ge=0, description="오프셋"),
) -> Envelope:
    """장소 검색. Mock PlaceProvider 사용, places 배열 반환.

    - 성공 시: envelope.status=ok, data.places=[...]
    - 결과 없음: envelope.status=ok, data.places=[] (빈 배열)
    - provider 오류: error 응답
    """
    server_time = datetime.now(tz=SEOUL_TZ).isoformat()
    meta = Meta(server_time=server_time, api_version="v1", is_demo=True)

    # 입력 검증 (빈 검색어 이미 Query에서 막힘)
    if not query.strip():
        from app.api.responses import error_response

        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="검색어는 비어있을 수 없습니다.",
            status_code=422,
        )

    try:
        result = await mock_place_provider.search_places(
            query=query.strip(),
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        from app.api.responses import error_response

        return error_response(
            error_code=ErrorCode.PLACE_PROVIDER_UNAVAILABLE,
            message=f"장소 제공자 오류: {exc}",
            status_code=503,
        )

    if not result.ok:
        from app.api.responses import error_response

        return error_response(
            error_code=ErrorCode.PLACE_PROVIDER_UNAVAILABLE,
            message=result.error_message or "장소 제공자 오류",
            status_code=result.http_status or 503,
        )

    places: list[PlaceResult] = result.data if result.data else []
    response = PlacesResponse(
        places=places,
        total_count=len(places),
        limit=limit,
        offset=offset,
    )

    # envelope 직접 구성 (success_response 사용 시 data에 PlacesResponse 전체가 들어가므로)
    return Envelope(
        status="ok",
        data=response.model_dump(),
        meta=meta,
    )
