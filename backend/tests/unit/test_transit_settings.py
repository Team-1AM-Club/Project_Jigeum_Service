"""교통 자격증명의 명시적 로드·환경변수 우선·비표시 계약."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from app.config import Settings

KEY_NAMES = (
    "SEOUL_SUBWAY_ARRIVAL_API_KEY",
    "SEOUL_SUBWAY_POSITION_API_KEY",
    "SEOUL_SUBWAY_STATIONS_API_KEY",
    "SEOUL_SUBWAY_TIMETABLE_API_KEY",
    "SEOUL_SUBWAY_LAST_TRAIN_API_KEY",
    "SEOUL_SUBWAY_PATH_API_KEY",
    "SEOUL_BUS_STATIONS_API_KEY",
    "SEOUL_BUS_ROUTES_API_KEY",
    "SEOUL_BUS_POSITIONS_API_KEY",
    "SEOUL_BUS_ARRIVALS_API_KEY",
)
SYNTHETIC_KEY = "synthetic-transit-key-for-tests"


@pytest.fixture(autouse=True)
def synthetic_environment(monkeypatch):
    for name in KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SECRET_KEY", "synthetic-app-key")


@pytest.mark.parametrize("name", KEY_NAMES)
def test_server_keys_are_secret_and_not_serialized(name, monkeypatch):
    monkeypatch.setenv(name, SYNTHETIC_KEY)
    settings = Settings(_env_file=None)
    key = getattr(settings, name.lower(), None)
    assert isinstance(key, SecretStr), "서비스별 SecretStr 설정이 필요합니다."
    assert key.get_secret_value() == SYNTHETIC_KEY
    assert SYNTHETIC_KEY not in repr(settings)
    assert SYNTHETIC_KEY not in settings.model_dump_json()


def test_import_settings_does_not_implicitly_read_transit_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.transit.local").write_text(
        f"SEOUL_SUBWAY_PATH_API_KEY={SYNTHETIC_KEY}\n", encoding="utf-8"
    )
    settings = Settings(_env_file=None)
    key = getattr(settings, "seoul_subway_path_api_key", None)
    assert isinstance(key, SecretStr)
    assert key.get_secret_value() == ""


def test_explicit_transit_file_and_existing_env_are_loaded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "SECRET_KEY=synthetic-existing-app-key\nAPI_VERSION=test-v1\n",
        encoding="utf-8",
    )
    transit = tmp_path / "transit.local"
    transit.write_text(f"SEOUL_SUBWAY_PATH_API_KEY={SYNTHETIC_KEY}\n", encoding="utf-8")
    assert hasattr(Settings, "from_transit_file"), "명시적 로드 경계가 필요합니다."
    settings = Settings.from_transit_file(transit)
    assert settings.seoul_subway_path_api_key.get_secret_value() == SYNTHETIC_KEY
    assert settings.api_version == "test-v1"


def test_server_environment_wins_over_local_file(tmp_path, monkeypatch):
    transit = tmp_path / "transit.local"
    transit.write_text(
        "SEOUL_BUS_ARRIVALS_API_KEY=synthetic-local-key\n", encoding="utf-8"
    )
    monkeypatch.setenv("SEOUL_BUS_ARRIVALS_API_KEY", "synthetic-server-key")
    assert hasattr(Settings, "from_transit_file")
    settings = Settings.from_transit_file(transit, env_file=None)
    assert (
        settings.seoul_bus_arrivals_api_key.get_secret_value() == "synthetic-server-key"
    )
    assert settings.seoul_bus_routes_api_key.get_secret_value() == ""


def test_missing_individual_key_keeps_other_settings_available():
    settings = Settings(_env_file=None)
    assert isinstance(getattr(settings, "seoul_bus_routes_api_key", None), SecretStr)
    assert settings.seoul_bus_routes_api_key.get_secret_value() == ""
    assert settings.api_version == "v1"


def test_relative_transit_file_is_rejected():
    assert hasattr(Settings, "from_transit_file")
    with pytest.raises(ValueError, match="절대 경로"):
        Settings.from_transit_file(Path("transit.local"), env_file=None)
