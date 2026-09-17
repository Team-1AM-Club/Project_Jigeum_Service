"""앱 설정. 환경 변수 검증 포함."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    secret_key: str = "change-me-in-production"
    database_url: str = "sqlite:///./jigeum.db"
    environment: str = "development"
    api_version: str = "v1"
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"
    places_provider: str = "mock"
    routing_provider: str = "mock"
    transit_provider: str = "mock"
    model_provider: str = "mock"
    model_provider_base_url: str = "http://localhost:8001"
    model_provider_api_key: str = ""
    openai_compatibility_mode: bool = False

    seoul_subway_arrival_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_subway_position_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_subway_stations_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_subway_timetable_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_subway_last_train_api_key: SecretStr = Field(
        default=SecretStr(""), repr=False
    )
    seoul_subway_path_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_bus_stations_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_bus_routes_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_bus_positions_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    seoul_bus_arrivals_api_key: SecretStr = Field(default=SecretStr(""), repr=False)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True
    )

    @classmethod
    def from_transit_file(
        cls,
        path: Path | None = None,
        *,
        env_file: str | Path | None = ".env",
    ) -> "Settings":
        """운영자 명시 실행에서만 로컬 교통 파일을 읽는다. 환경변수가 우선한다."""
        transit_path = (
            path or Path(__file__).resolve().parents[1] / ".env.transit.local"
        )
        if not transit_path.is_absolute():
            raise ValueError("교통 설정 파일은 절대 경로여야 합니다.")
        files = (env_file, transit_path) if env_file is not None else (transit_path,)
        return cls(_env_file=files)

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "change-me-in-production":
            import warnings

            warnings.warn(
                "secret_key가 기본값입니다. 프로덕션에서는 반드시 변경하세요.",
                RuntimeWarning,
                stacklevel=2,
            )
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL은 필수입니다.")
        return v

    @property
    def is_debug(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# 모듈 레벨 검증: import 시점에 필수 설정 확인
_settings = get_settings()
if (
    _settings.secret_key == "change-me-in-production"
    and _settings.environment == "production"
):
    import warnings

    warnings.warn(
        "프로덕션 환경에서 secret_key가 기본값입니다. 서버를 중단하지 않지만 경고합니다.",
        RuntimeWarning,
    )
