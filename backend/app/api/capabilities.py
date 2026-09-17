from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.schemas.common import Envelope, Meta
from app.schemas.journeys import TripRequest

router = APIRouter()
SEOUL_TZ = ZoneInfo("Asia/Seoul")
_OPTION_LIMITS = TripRequest.model_json_schema()["properties"]["max_options"]


@router.get("/capabilities")
async def get_capabilities() -> Envelope:
    server_time = datetime.now(tz=SEOUL_TZ).isoformat()
    meta = Meta(server_time=server_time, api_version="v1", is_demo=True)
    data = {
        "timezone": "Asia/Seoul",
        "place_search": {
            "supported": True,
            "max_query_length": 200,
            "default_limit": 5,
            "max_limit": 20,
        },
        "interpretation": {
            "supported": True,
            "model": "mock",
        },
        "appointment": {
            "supported": True,
            "max_options": _OPTION_LIMITS["maximum"],
            "include_walking": True,
        },
        "last_journey": {
            "supported": True,
        },
        "transport_modes": ["subway", "bus"],
        "max_options": _OPTION_LIMITS["maximum"],
        "defaults": {
            "arrival_preference_minutes": 0,
            "transport_modes": ["subway", "bus"],
            "transport_mode": "subway",
            "max_options": _OPTION_LIMITS["default"],
            "radius_meters": 5000,
        },
        "buffer_policy": {
            "default_buffer_minutes": 5,
            "max_buffer_minutes": 30,
            "apply_buffer": True,
        },
        "limitations": [
            "실시간 데이터는 mock 제공자로만 동작 (Phase 1)",
            "택시 비용 상한선 미지원",
            "인증·회원 데이터 미포함",
        ],
    }
    return Envelope(status="ok", data=data, meta=meta)
