"""Provider Client - 재시도 정책 완성.

T064: 재시도 정책
- 최대 1회 재시도
- 500ms 대기
- 연결 실패·timeout·retryable=true 502/503/504에만 적용
- 같은 Idempotency-Key·같은 body로 재시도
- 4xx·409·410·검증 실패·invalid response는 재시도 안 함
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Any, Callable, Awaitable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")

# 재시도 가능 HTTP 상태 코드
RETRYABLE_STATUS_CODES = {502, 503, 504}

# 재시도 가능 예외 유형
RETRYABLE_EXCEPTIONS = (
    asyncio.TimeoutError,
    ConnectionError,
    OSError,  # 네트워크 관련 OS 오류
)


class ProviderClientError(Exception):
    """Provider 호출 오류."""

    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


class ProviderClient:
    """Provider HTTP 클라이언트 (재시도 정책 포함).

    T064: 재시도 정책 완성
    - 최대 1회 재시도
    - 500ms 대기
    - 연결 실패·timeout·retryable=true 502/503/504에만 적용
    - 같은 Idempotency-Key·같은 body로 재시도
    - 4xx·409·410·검증 실패·invalid response는 재시도 안 함
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        retry_delay_ms: int = 500,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms

    async def call(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
        headers: Optional[dict] = None,
        retryable: bool = False,
    ) -> dict:
        """Provider 호출 (재시도 정책 적용).

        Args:
            method: HTTP 메서드 (GET/POST/PUT/DELETE)
            path: API 경로 (예: /api/v1/route/search)
            body: 요청 본문 (JSON)
            idempotency_key: Idempotency-Key (재시도 시 동일 key 사용)
            headers: 추가 헤더
            retryable: 계약상 retryable=true 여부

        Returns:
            dict: 응답 본문

        Raises:
            ProviderClientError: 호출 실패 시
        """
        url = f"{self.base_url}{path}"
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            request_headers["Idempotency-Key"] = idempotency_key
        if headers:
            request_headers.update(headers)

        last_error: Optional[ProviderClientError] = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    f"Provider 호출: {method} {url} (시도 {attempt + 1}/{self.max_retries + 1})"
                )

                # 실제 HTTP 호출 (실제 구현 시 httpx/requests 사용)
                # 여기서는 Mock/실제 제공자 인터페이스 호출로 대체
                response = await self._execute_request(
                    method=method,
                    url=url,
                    body=body,
                    headers=request_headers,
                )

                # 성공 (2xx)
                if 200 <= response.get("status_code", 200) < 300:
                    return response.get("body", {})

                # 4xx → 재시도 안 함
                if 400 <= response.get("status_code", 0) < 500:
                    logger.warning(
                        f"Provider 4xx 응답: {response.get('status_code')} - 재시도 안 함"
                    )
                    raise ProviderClientError(
                        message=f"Provider 오류: {response.get('status_code')} {response.get('body', {}).get('message', 'Unknown')}",
                        status_code=response.get("status_code"),
                        retryable=False,
                    )

                # 5xx → retryable 여부 확인
                status = response.get("status_code", 0)
                if status in RETRYABLE_STATUS_CODES or retryable:
                    logger.warning(
                        f"Provider retryable 5xx 응답: {status} - 재시도"
                    )
                    last_error = ProviderClientError(
                        message=f"Provider 오류: {status}",
                        status_code=status,
                        retryable=True,
                    )
                else:
                    logger.warning(
                        f"Provider non-retryable 5xx 응답: {status} - 재시도 안 함"
                    )
                    raise ProviderClientError(
                        message=f"Provider 오류: {status}",
                        status_code=status,
                        retryable=False,
                    )

            except RETRYABLE_EXCEPTIONS as e:
                # 연결 실패·timeout → 재시도
                logger.warning(
                    f"Provider 연결 실패/timeout (시도 {attempt + 1}): {e}"
                )
                last_error = ProviderClientError(
                    message=f"Provider 연결 실패: {str(e)}",
                    retryable=True,
                )

            except ProviderClientError as e:
                # ProviderClientError 재발생
                if e.retryable and attempt < self.max_retries:
                    last_error = e
                else:
                    raise

            # 재시도 대기 (500ms)
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay_ms / 1000.0)

        # 모든 시도 실패
        if last_error:
            raise last_error
        raise ProviderClientError("Provider 호출 실패 (알 수 없는 오류)")

    async def _execute_request(
        self,
        method: str,
        url: str,
        body: Optional[dict],
        headers: dict,
    ) -> dict:
        """실제 HTTP 요청 실행 (구현 시 httpx 등으로 대체).

        현재는 Mock/실제 제공자 인터페이스 호출로 대체.
        """
        # TODO: 실제 HTTP 클라이언트 구현 (httpx.AsyncClient 등)
        # 예:
        # async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
        #     response = await client.request(
        #         method=method,
        #         url=url,
        #         json=body,
        #         headers=headers,
        #     )
        #     return {
        #         "status_code": response.status_code,
        #         "body": response.json(),
        #     }

        # 임시: NotImplementedError (실제 구현 시 교체)
        raise NotImplementedError(
            f"Provider HTTP 호출 미구현: {method} {url}. "
            "실제 httpx/requests 구현으로 교체 필요."
        )

    def is_retryable_error(self, error: Exception) -> bool:
        """오류가 재시도 가능한지 확인.

        Args:
            error: 발생한 예외

        Returns:
            True: 재시도 가능, False: 아님
        """
        if isinstance(error, ProviderClientError):
            return error.retryable
        if isinstance(error, RETRYABLE_EXCEPTIONS):
            return True
        return False
