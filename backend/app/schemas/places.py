from pydantic import BaseModel, Field
from typing import Optional


class PlaceSearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="검색어")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="대략적 위도 (옵션)")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="대략적 경도 (옵션)")
    radius_meters: Optional[int] = Field(None, ge=100, le=50000, description="검색 반경 미터")
    limit: int = Field(5, ge=1, le=20, description="최대 결과 수")
    offset: int = Field(0, ge=0, description="오프셋")


class PlaceResult(BaseModel):
    place_id: str
    name: str
    address: Optional[str] = None
    latitude: float
    longitude: float
    place_type: str = "unknown"
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class PlacesResponse(BaseModel):
    places: list[PlaceResult] = []
    total_count: int = 0
    limit: int = 5
    offset: int = 0
