"""고정된 공식 endpoint만 조회하는 운영자 최소 검증. --live가 필수다."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from app.services.provider_client import (
    ProviderClient,
    ProviderClientError,
    RequestBudget,
)

if TYPE_CHECKING:
    from app.config import Settings


@dataclass(frozen=True)
class ProbeSpec:
    operation: str
    key_field: str
    family: str
    base_url: str
    fields: tuple[str, ...]


STATIC = "http://openapi.seoul.go.kr:8088"
REALTIME = "http://swopenapi.seoul.go.kr"
BUS = "http://ws.bus.go.kr"
CATALOG = {
    "subway-stations": ProbeSpec(
        "SearchSTNBySubwayLineInfo",
        "seoul_subway_stations_api_key",
        "static",
        STATIC,
        ("STATION_CD", "FR_CODE", "STATION_NM", "LINE_NUM"),
    ),
    "subway-arrivals": ProbeSpec(
        "realtimeStationArrival",
        "seoul_subway_arrival_api_key",
        "realtime",
        REALTIME,
        ("subwayId", "statnId", "updnLine", "recptnDt", "barvlDt"),
    ),
    "subway-positions": ProbeSpec(
        "realtimePosition",
        "seoul_subway_position_api_key",
        "realtime",
        REALTIME,
        ("subwayId", "statnId", "trainNo", "recptnDt", "updnLine"),
    ),
    "subway-timetable": ProbeSpec(
        "SearchSTNTimeTableByIDService",
        "seoul_subway_timetable_api_key",
        "static",
        STATIC,
        (
            "STATION_CD",
            "FR_CODE",
            "TRAIN_NO",
            "ARRIVETIME",
            "LEFTTIME",
            "WEEK_TAG",
            "INOUT_TAG",
        ),
    ),
    "subway-last-train": ProbeSpec(
        "SearchSTNTimeTableByFRCodeService",
        "seoul_subway_last_train_api_key",
        "static",
        STATIC,
        ("STATION_CD", "FR_CODE", "TRAIN_NO", "ARRIVETIME", "LEFTTIME", "FL_FLAG"),
    ),
    "subway-path": ProbeSpec(
        "getShtrmPath",
        "seoul_subway_path_api_key",
        "path",
        STATIC,
        ("reqHr", "wtngHr", "trainDptreTm", "trainArvlTm", "trainno", "tmnlStnCd"),
    ),
    "bus-stations": ProbeSpec(
        "getStationByName",
        "seoul_bus_stations_api_key",
        "bus",
        BUS,
        ("stId", "arsId", "posX", "posY"),
    ),
    "bus-routes": ProbeSpec(
        "getStaionByRoute",
        "seoul_bus_routes_api_key",
        "bus",
        BUS,
        ("busRouteId", "station", "seq", "section", "gpsX", "gpsY"),
    ),
    "bus-positions": ProbeSpec(
        "getBusPosByRouteSt",
        "seoul_bus_positions_api_key",
        "bus",
        BUS,
        ("busRouteId", "sectOrd", "vehId", "dataTm"),
    ),
    "bus-arrivals": ProbeSpec(
        "getArrInfoByRouteAll",
        "seoul_bus_arrivals_api_key",
        "bus",
        BUS,
        ("stId", "staOrd", "mkTm", "isLast1", "isLast2", "arrmsg1"),
    ),
}


def invalid_response():
    raise ProviderClientError(error_code="UPSTREAM_RESPONSE_INVALID")


def response_diagnostics(data: dict, spec: ProbeSpec) -> dict:
    """구조와 고정 코드만 분류하고 임의 제공처 텍스트는 반환하지 않는다."""
    if "RESULT" in data:
        shape, frame = "business_result", data.get("RESULT")
    elif spec.operation in data:
        shape, frame = "operation", data.get(spec.operation)
        if isinstance(frame, dict):
            frame = frame.get("RESULT") or frame.get("errorMessage")
    elif "ServiceResult" in data:
        shape, frame = "bus", data.get("ServiceResult")
        frame = frame.get("msgHeader") if isinstance(frame, dict) else None
    elif "document" in data:
        shape, frame = "path", data.get("document")
        frame = frame.get("header") if isinstance(frame, dict) else None
    else:
        shape, frame = "unknown", None
    known = {
        "INFO-000",
        "INFO-100",
        "INFO-200",
        "ERROR-300",
        "ERROR-301",
        "ERROR-310",
        "ERROR-331",
        "ERROR-332",
        "ERROR-333",
        "ERROR-334",
        "ERROR-335",
        "ERROR-336",
        "ERROR-500",
        "ERROR-600",
        "ERROR-601",
        "0",
        "00",
    }
    code = None
    if isinstance(frame, dict):
        code = (
            frame.get("CODE")
            or frame.get("code")
            or frame.get("headerCd")
            or frame.get("resultCode")
        )
    return {
        "response_shape": shape,
        "business_code": code if isinstance(code, str) and code in known else "unknown",
    }


def row_list(value) -> list[dict]:
    if value in (None, ""):
        return []
    rows = value if isinstance(value, list) else [value]
    if not all(isinstance(row, dict) for row in rows):
        invalid_response()
    return rows


def inspect_response(data: dict, spec: ProbeSpec) -> tuple[list[dict], str]:
    """문서에 명시된 업무 상태만 판정한다. 미지의 원문은 출력하지 않는다."""
    top_result = data.get("RESULT")
    frame = data.get(spec.operation)
    if spec.family == "realtime" and isinstance(frame, dict):
        header = frame.get("errorMessage")
        if isinstance(header, dict):
            code = header.get("code")
            if code == "INFO-100":
                raise ProviderClientError(status_code=403)
            if code == "INFO-200":
                return [], "INFO-200"
            if code != "INFO-000" or str(header.get("status")) != "200":
                invalid_response()
            tag = (
                "realtimeArrivalList"
                if spec.operation == "realtimeStationArrival"
                else "realtimePositionList"
            )
            if tag not in frame:
                invalid_response()
            return row_list(frame[tag]), "INFO-000"
    result = top_result or (frame.get("RESULT") if isinstance(frame, dict) else None)
    if isinstance(result, dict):
        code = result.get("CODE") or result.get("code")
        if code == "INFO-100":
            raise ProviderClientError(status_code=403)
        if code == "INFO-200":
            return [], "INFO-200"
        if code != "INFO-000":
            invalid_response()
        if not isinstance(frame, dict):
            invalid_response()
        rows = row_list(frame.get("row"))
        if not rows and str(frame.get("list_total_count", "")) != "0":
            invalid_response()
        return rows, "INFO-000"
    if spec.family == "bus":
        frame = data.get("ServiceResult")
        gateway = data.get("OpenAPI_ServiceResponse")
        if isinstance(gateway, dict):
            header = gateway.get("cmmMsgHeader", {})
            code = header.get("returnReasonCode") if isinstance(header, dict) else None
            if code in ("20", "30", "31"):
                raise ProviderClientError(status_code=403)
            if code in ("22", "23"):
                raise ProviderClientError(status_code=429, error_code="RATE_LIMITED")
            invalid_response()
        if not isinstance(frame, dict) or not isinstance(frame.get("msgHeader"), dict):
            invalid_response()
        if frame["msgHeader"].get("headerCd") != "0":
            invalid_response()
        body = frame.get("msgBody")
        if body in (None, ""):
            return [], "0"
        if not isinstance(body, dict):
            invalid_response()
        return row_list(body.get("itemList")), "0"
    if spec.family == "path":
        frame = data.get("document")
        if not isinstance(frame, dict) or not isinstance(frame.get("header"), dict):
            invalid_response()
        if frame["header"].get("resultCode") != "00":
            invalid_response()
        body = frame.get("body")
        if not isinstance(body, dict) or not isinstance(body.get("paths"), dict):
            invalid_response()
        return row_list(body["paths"].get("path")), "00"
    invalid_response()


def build_request(spec: ProbeSpec, key: str) -> tuple[str, dict | None]:
    """인증 probe는 공식 예제 입력을 사용하며 실제 계획으로 해석하지 않는다."""
    if spec.family == "bus":
        category = {
            "getStationByName": "stationinfo",
            "getStaionByRoute": "busRouteInfo",
            "getBusPosByRouteSt": "buspos",
            "getArrInfoByRouteAll": "arrive",
        }[spec.operation]
        params = {"serviceKey": key}
        if spec.operation == "getStationByName":
            params["stSrch"] = "서울역"
        else:
            params["busRouteId"] = "100100118"
        if spec.operation == "getBusPosByRouteSt":
            params.update(startOrd="1", endOrd="10")
        return f"/api/rest/{category}/{spec.operation}", params
    segments = [key, "xml", spec.operation]
    if spec.family == "realtime":
        segments += [
            "0",
            "1",
            "서울" if spec.operation == "realtimeStationArrival" else "1호선",
        ]
    else:
        segments += ["1", "1"]
        if spec.operation == "SearchSTNTimeTableByIDService":
            segments += ["0309", "1", "1"]
        elif spec.operation == "SearchSTNTimeTableByFRCodeService":
            segments += ["132", "1", "1"]
        elif spec.family == "path":
            segments += ["답십리", "역삼", "2025-10-17 10:00:00"]
    prefix = "/api/subway" if spec.family == "realtime" else ""
    return (
        prefix + "/" + "/".join(quote(segment, safe="") for segment in segments),
        None,
    )


def report_for(alias: str | None, state: str, **safe_values) -> dict:
    spec = CATALOG.get(alias)
    return {
        "service_alias": alias if spec else None,
        "operation": spec.operation if spec else None,
        "state": state,
        "verified_for_planning": False,
        **safe_values,
    }


async def verify_service(
    alias: str, settings: Settings, *, http_client: httpx.AsyncClient | None = None
) -> dict:
    spec = CATALOG.get(alias)
    if spec is None:
        return report_for(None, "invalid_input")
    key = getattr(settings, spec.key_field).get_secret_value()
    if not key:
        return report_for(alias, "missing_key", attempts=0)
    path, params = build_request(spec, key)
    client = ProviderClient(base_url=spec.base_url, http_client=http_client)
    budget = RequestBudget.for_operation("verify")
    diagnostics = {}

    def validate(data):
        diagnostics.update(response_diagnostics(data, spec))
        return inspect_response(data, spec)

    try:
        data = await client.call(
            "GET",
            path,
            params=params,
            response_format="xml",
            validate_response=validate,
            budget=budget,
            service_alias=alias,
            operation=spec.operation,
            retryable=True,
        )
        rows, business_code = inspect_response(data, spec)
        return report_for(
            alias,
            "real_call_verified" if rows else "empty",
            row_count=len(rows),
            business_code=business_code,
            fields_present=[
                field for field in spec.fields if any(field in row for row in rows)
            ],
            attempts=budget.attempts,
            retrieved_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
            basis_at=None,
        )
    except ProviderClientError as error:
        state = (
            "authentication_failed"
            if error.status_code in (401, 403)
            else {
                "RATE_LIMITED": "rate_limited",
                "UPSTREAM_TIMEOUT": "timeout",
                "UPSTREAM_RESPONSE_INVALID": "unverified_response",
            }.get(error.error_code, "provider_failure")
        )
        return report_for(
            alias,
            state,
            http_status=error.status_code,
            error_code=error.error_code,
            attempts=budget.attempts,
            **diagnostics,
        )
    except Exception:
        return report_for(alias, "unverified_response", attempts=budget.attempts)
    finally:
        await client.aclose()


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("운영자 입력을 확인해 주세요.")


def cli_main(argv=None, *, settings_loader=None) -> int:
    parser = SafeParser(
        description="공식 서비스 최소 검증. 키·원문 응답을 출력하지 않습니다."
    )
    parser.add_argument("--service", required=True, choices=tuple(CATALOG))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--env-file", type=Path)
    try:
        args = parser.parse_args(argv)
        if not args.live:
            result = report_for(args.service, "requires_live")
        elif args.env_file is not None and not args.env_file.is_absolute():
            result = report_for(args.service, "invalid_input")
        else:
            loader = settings_loader
            if loader is None:
                from app.config import Settings

                loader = Settings.from_transit_file
            settings = loader(args.env_file, env_file=None)
            result = asyncio.run(verify_service(args.service, settings))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["state"] in ("real_call_verified", "empty") else 2
    except Exception:
        print(json.dumps(report_for(None, "invalid_input"), ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())
