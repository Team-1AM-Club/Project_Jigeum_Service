"""공통 제공처 전송: 비밀 없는 오류, 제한된 retry 및 요청 범위 예산."""

import asyncio
import copy
import json
import logging
import math
import time
from collections.abc import Callable
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {502, 503, 504}
RETRYABLE_EXCEPTIONS = (
    asyncio.TimeoutError,
    ConnectionError,
    httpx.TimeoutException,
    httpx.ConnectError,
)
SERVICE_ALIASES = {
    "subway-stations",
    "subway-arrivals",
    "subway-positions",
    "subway-timetable",
    "subway-last-train",
    "subway-path",
    "bus-stations",
    "bus-routes",
    "bus-positions",
    "bus-arrivals",
}
OPERATIONS = {
    "SearchSTNBySubwayLineInfo",
    "realtimeStationArrival",
    "realtimePosition",
    "SearchSTNTimeTableByIDService",
    "SearchSTNTimeTableByFRCodeService",
    "getShtrmPath",
    "getStationByName",
    "getRouteByStation",
    "getBustimeByStation",
    "getBusRouteList",
    "getStaionByRoute",
    "getBusPosByRouteSt",
    "getArrInfoByRouteAll",
}
ERROR_MESSAGES = {
    "PROVIDER_UNAVAILABLE": "제공처 조회에 실패했습니다.",
    "UPSTREAM_TIMEOUT": "제공처 조회 시간 또는 시도 예산을 초과했습니다.",
    "UPSTREAM_RESPONSE_INVALID": "제공처 응답을 검증할 수 없습니다.",
    "RATE_LIMITED": "제공처 호출 한도를 초과했습니다.",
}


class ProviderClientError(Exception):
    """원문 메시지·URL·응답을 보존하지 않는 경계 오류."""

    def __init__(
        self,
        message: str = "",
        status_code: int | None = None,
        retryable: bool = False,
        *,
        error_code: str = "PROVIDER_UNAVAILABLE",
    ):
        self.error_code = (
            error_code
            if isinstance(error_code, str) and error_code in ERROR_MESSAGES
            else "PROVIDER_UNAVAILABLE"
        )
        self.message = ERROR_MESSAGES[self.error_code]
        valid_status = type(status_code) is int and 100 <= status_code <= 599
        self.status_code = status_code if valid_status else None
        self.retryable = retryable is True and (status_code is None or valid_status)
        super().__init__(self.message)


class RequestBudget:
    """한 요청에서만 공유하는 deadline·시도·동시성·중복 조회 조정."""

    def __init__(self, seconds: float, max_attempts: int, concurrency: int):
        if (
            not math.isfinite(seconds)
            or seconds <= 0
            or max_attempts < 0
            or concurrency < 0
        ):
            raise ValueError("올바른 조회 예산이 필요합니다.")
        if max_attempts and not concurrency:
            raise ValueError("외부 조회 동시성은 양수여야 합니다.")
        self.deadline = time.monotonic() + seconds
        self.max_attempts = max_attempts
        self.attempts = 0
        self.semaphore = asyncio.Semaphore(concurrency)
        self.results: dict[tuple, dict] = {}
        self.inflight: dict[tuple, asyncio.Future] = {}

    @classmethod
    def for_operation(cls, operation: str) -> "RequestBudget":
        policies = {
            "health": (3.0, 0, 0),
            "capabilities": (3.0, 0, 0),
            "places": (10.0, 4, 2),
            "plan": (25.0, 12, 4),
            "replan": (25.0, 12, 4),
            "verify": (60.5, 2, 1),
        }
        if operation not in policies:
            raise ValueError("확정된 작업 예산이 필요합니다.")
        return cls(*policies[operation])

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def check_attempt(self) -> None:
        if self.remaining() <= 0 or self.attempts >= self.max_attempts:
            raise ProviderClientError(error_code="UPSTREAM_TIMEOUT")


class ProviderClient:
    """기존 제공처 경계를 재사용하는 JSON/XML HTTP 클라이언트."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        retry_delay_ms: int = 500,
        *,
        http_client: httpx.AsyncClient | None = None,
        max_response_bytes: int = 2 * 1024 * 1024,
    ):
        if not 0 < timeout_seconds <= 30 or max_retries not in (0, 1):
            raise ValueError("시도 상한은 30초, retry 상한은 1회입니다.")
        if retry_delay_ms != 500 or max_response_bytes <= 0:
            raise ValueError("retry 대기는 500ms이며 응답 크기 상한은 양수여야 합니다.")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.max_response_bytes = max_response_bytes
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(
            follow_redirects=False, trust_env=False
        )

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self.http_client.aclose()

    async def call(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        idempotency_key: str | None = None,
        headers: dict | None = None,
        retryable: bool = False,
        *,
        params: dict | None = None,
        response_format: str = "json",
        validate_response: Callable[[dict], None] | None = None,
        budget: RequestBudget | None = None,
        service_alias: str = "provider",
        operation: str = "request",
    ) -> dict:
        if response_format not in ("json", "xml"):
            raise ProviderClientError(error_code="UPSTREAM_RESPONSE_INVALID")
        shared = budget or RequestBudget.for_operation("verify")
        alias = service_alias if service_alias in SERVICE_ALIASES else "provider"
        safe_operation = operation if operation in OPERATIONS else "request"
        request_headers = {
            "Accept": (
                "application/json" if response_format == "json" else "application/xml"
            )
        }
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if idempotency_key:
            request_headers["Idempotency-Key"] = idempotency_key
        if headers:
            request_headers.update(headers)
        request_headers = {
            name: value
            for name, value in request_headers.items()
            if name.lower() != "accept-encoding"
        }
        request_headers["Accept-Encoding"] = "identity"
        # 키가 포함될 수 있는 요청 fingerprint는 요청 메모리 안에서만 보존한다.
        # 출력·hash·프로세스 간 캐시·다음 요청 재사용은 하지 않는다.
        fingerprint = (
            method,
            self.base_url,
            path,
            response_format,
            id(validate_response),
            json.dumps(body, sort_keys=True),
            json.dumps(params, sort_keys=True),
            json.dumps(request_headers, sort_keys=True),
            retryable,
        )
        if shared.remaining() <= 0:
            raise ProviderClientError(error_code="UPSTREAM_TIMEOUT")
        if fingerprint in shared.results:
            return copy.deepcopy(shared.results[fingerprint])
        if fingerprint in shared.inflight:
            try:
                async with asyncio.timeout(shared.remaining()):
                    return copy.deepcopy(
                        await asyncio.shield(shared.inflight[fingerprint])
                    )
            except TimeoutError:
                raise ProviderClientError(error_code="UPSTREAM_TIMEOUT") from None

        shared.check_attempt()
        pending = asyncio.get_running_loop().create_future()
        shared.inflight[fingerprint] = pending
        try:
            result = await self._call_with_retry(
                method,
                path,
                body,
                request_headers,
                params,
                response_format,
                validate_response,
                shared,
                retryable,
                alias,
                safe_operation,
            )
            cached, published = copy.deepcopy(result), copy.deepcopy(result)
            if shared.remaining() <= 0:
                raise ProviderClientError(error_code="UPSTREAM_TIMEOUT")
            shared.results[fingerprint] = cached
            pending.set_result(published)
            return result
        except asyncio.CancelledError:
            pending.cancel()
            raise
        except ProviderClientError as error:
            pending.set_exception(error)
            pending.exception()  # follower 없는 경우에도 미회수 Future 경고 방지
            raise error from None
        finally:
            shared.inflight.pop(fingerprint, None)

    async def _call_with_retry(
        self,
        method,
        path,
        body,
        headers,
        params,
        response_format,
        validate_response,
        budget,
        retryable,
        alias,
        operation,
    ) -> dict:
        last_error = ProviderClientError()
        for attempt in range(self.max_retries + 1):
            try:
                budget.check_attempt()
                async with asyncio.timeout(budget.remaining()):
                    async with budget.semaphore:
                        budget.check_attempt()
                        budget.attempts += 1
                        logger.info(
                            "Provider service=%s operation=%s attempt=%s",
                            alias,
                            operation,
                            attempt + 1,
                        )
                        async with asyncio.timeout(
                            min(self.timeout_seconds, budget.remaining())
                        ):
                            response = await self._execute_request(
                                method=method,
                                url=f"{self.base_url}{path}",
                                body=body,
                                headers=headers,
                                params=params,
                                response_format=response_format,
                            )
                status, data = response["status_code"], response["body"]
                error_data = data.get("error")
                explicit_retry = (
                    error_data.get("retryable")
                    if isinstance(error_data, dict)
                    else None
                )
                if 200 <= status < 300:
                    if validate_response:
                        validate_response(data)
                    if budget.remaining() <= 0:
                        raise ProviderClientError(error_code="UPSTREAM_TIMEOUT")
                    if isinstance(error_data, dict):
                        raise ProviderClientError(
                            status_code=error_data.get("status_code", 503),
                            retryable=explicit_retry is True,
                        )
                    return data
                allow_retry = (
                    status in RETRYABLE_STATUS_CODES
                    and explicit_retry is not False
                    and (retryable or explicit_retry is True)
                )
                raise ProviderClientError(
                    status_code=status,
                    retryable=allow_retry,
                    error_code=(
                        "RATE_LIMITED" if status == 429 else "PROVIDER_UNAVAILABLE"
                    ),
                )
            except (ConnectionError, httpx.ConnectError):
                last_error = ProviderClientError(retryable=True)
            except RETRYABLE_EXCEPTIONS:
                last_error = ProviderClientError(
                    error_code="UPSTREAM_TIMEOUT", retryable=True
                )
            except ProviderClientError as error:
                last_error = ProviderClientError(
                    status_code=error.status_code,
                    retryable=error.retryable
                    and error.status_code in (None, 502, 503, 504)
                    and error.error_code
                    not in ("RATE_LIMITED", "UPSTREAM_RESPONSE_INVALID"),
                    error_code=error.error_code,
                )
            except Exception:
                last_error = ProviderClientError(error_code="UPSTREAM_RESPONSE_INVALID")
            if (
                not last_error.retryable
                or attempt >= self.max_retries
                or budget.attempts >= budget.max_attempts
                or budget.remaining() <= 0.5
            ):
                break
            logger.warning("Provider service=%s operation=%s retry=1", alias, operation)
            try:
                async with asyncio.timeout(budget.remaining()):
                    await asyncio.sleep(0.5)
            except TimeoutError:
                last_error = ProviderClientError(error_code="UPSTREAM_TIMEOUT")
                break
        raise last_error from None

    async def _execute_request(
        self,
        method: str,
        url: str,
        body: dict | None,
        headers: dict,
        *,
        params: dict | None = None,
        response_format: str = "json",
    ) -> dict:
        # 라이브러리 wire 로그에는 KEY path/query 및 인증 헤더가 들어갈 수 있다.
        # 공통 전송 경계에서는 wire logger를 차단하고 위의 허용 alias만 기록한다.
        for name in ["httpx", "httpcore", *list(logging.Logger.manager.loggerDict)]:
            if (
                name == "httpx"
                or name == "httpcore"
                or name.startswith(("httpx.", "httpcore."))
            ):
                wire_logger = logging.getLogger(name)
                wire_logger.disabled = True
                wire_logger.setLevel(logging.CRITICAL + 1)
        async with self.http_client.stream(
            method,
            url,
            json=body,
            headers=headers,
            params=params,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as response:
            if 300 <= response.status_code < 400:
                raise ProviderClientError(error_code="UPSTREAM_RESPONSE_INVALID")
            if response.headers.get(
                "Content-Encoding", "identity"
            ).strip().lower() not in ("identity", "utf-8"):
                raise ProviderClientError(error_code="UPSTREAM_RESPONSE_INVALID")
            content = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=8192):
                if len(content) + len(chunk) > self.max_response_bytes:
                    raise ProviderClientError(error_code="UPSTREAM_RESPONSE_INVALID")
                content.extend(chunk)
            try:
                data = self._decode(bytes(content), response_format)
            except (ValueError, ElementTree.ParseError, RecursionError):
                if 400 <= response.status_code < 500:
                    data = {}
                else:
                    raise ProviderClientError(
                        error_code="UPSTREAM_RESPONSE_INVALID"
                    ) from None
            return {"status_code": response.status_code, "body": data}

    @staticmethod
    def _decode(content: bytes, response_format: str) -> dict:
        if response_format == "json":

            def invalid_constant(value):
                raise ValueError("유효하지 않은 JSON 숫자")

            data = json.loads(content, parse_constant=invalid_constant)
            if not isinstance(data, dict):
                raise ValueError("객체 응답이 필요합니다.")
            return data
        text = content.decode("utf-8-sig")
        if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD/entity 및 미지원 encoding은 처리하지 않습니다.")
        root = ElementTree.fromstring(text)
        stack, count = [(root, 1)], 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if depth > 32 or count > 10000:
                raise ValueError("XML 구조 상한 초과")
            stack.extend((child, depth + 1) for child in node)

        def convert(node):
            if not len(node):
                return node.text or ""
            result = {}
            for child in node:
                value = convert(child)
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(value)
                else:
                    result[child.tag] = value
            return result

        return {root.tag: convert(root)}

    def is_retryable_error(self, error: Exception) -> bool:
        if isinstance(error, ProviderClientError):
            return error.retryable
        return isinstance(error, RETRYABLE_EXCEPTIONS)
