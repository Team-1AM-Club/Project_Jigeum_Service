from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter
from app.schemas.common import Meta, Envelope

router = APIRouter()
SEOUL_TZ = ZoneInfo("Asia/Seoul")


@router.get("/health")
async def get_health() -> Envelope:
    server_time = datetime.now(tz=SEOUL_TZ).isoformat()
    meta = Meta(server_time=server_time, api_version="v1", is_demo=True)
    return Envelope(
        status="ok",
        data={
            "service": "jigeum-api",
            "status": "ok",
            "server_time": server_time,
        },
        meta=meta,
    )
