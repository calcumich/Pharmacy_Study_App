import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5


class RateLimiter:
    """Token-bucket-ish limiter: at most `rate` calls per `per` seconds."""

    def __init__(self, rate: int, per: float = 1.0) -> None:
        self._rate = rate
        self._per = per
        self._slots: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            self._slots = [t for t in self._slots if now - t < self._per]
            if len(self._slots) >= self._rate:
                wait = self._per - (now - self._slots[0])
                await asyncio.sleep(max(wait, 0))
                now = asyncio.get_event_loop().time()
                self._slots = [t for t in self._slots if now - t < self._per]
            self._slots.append(now)


@asynccontextmanager
async def http_client(
    *,
    base_url: str = "",
    headers: dict[str, str] | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    default_headers = {
        "Accept": "application/json",
        "User-Agent": "pharmacy-study-app/0.1 (ingestion)",
    }
    if headers:
        default_headers.update(headers)
    async with httpx.AsyncClient(
        base_url=base_url,
        headers=default_headers,
        timeout=_DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as client:
        yield client


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
    limiter: RateLimiter | None = None,
) -> httpx.Response:
    backoff = 1.0
    for attempt in range(1, _MAX_RETRIES + 1):
        if limiter is not None:
            await limiter.acquire()
        try:
            response = await client.get(url, params=params, headers=headers)
        except httpx.TransportError as exc:
            if attempt == _MAX_RETRIES:
                raise
            log.warning("transport error on %s (attempt %d): %s", url, attempt, exc)
            await asyncio.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES:
            retry_after = response.headers.get("Retry-After")
            sleep_for = float(retry_after) if retry_after and retry_after.isdigit() else backoff
            log.warning(
                "retryable %d from %s (attempt %d), sleeping %.1fs",
                response.status_code,
                url,
                attempt,
                sleep_for,
            )
            await asyncio.sleep(sleep_for)
            backoff *= 2
            continue
        return response
    raise RuntimeError(f"exhausted retries for {url}")
