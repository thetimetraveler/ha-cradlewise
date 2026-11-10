"""Minimal async client for the Cradlewise Data API (v1, beta, read-only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import API_BASE_URL

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class CradlewiseError(Exception):
    """Base error for the Cradlewise API."""


class CradlewiseConnectionError(CradlewiseError):
    """The API could not be reached."""


class CradlewiseAuthError(CradlewiseError):
    """The token is missing, invalid or expired (HTTP 401)."""


class CradlewiseSubscriptionError(CradlewiseError):
    """The Nurture Plus subscription is not active (HTTP 403)."""


class CradlewiseRateLimitError(CradlewiseError):
    """The rate limit was exceeded (HTTP 429)."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def format_api_time(value: datetime) -> str:
    """Format a datetime the way the API expects: UTC, 'YYYY-MM-DD HH:MM:SS'."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime(_TIME_FORMAT)


def _error_detail(body: Any) -> str:
    """Extract a readable message from either documented error shape."""
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, list):
            return "; ".join(
                str(item.get("msg", item)) if isinstance(item, dict) else str(item)
                for item in detail
            )
        if detail is not None:
            return str(detail)
    return ""


class CradlewiseApi:
    """Client for the Cradlewise Data API."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._session = session
        self._token = token

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            async with self._session.get(
                f"{API_BASE_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                try:
                    body = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    body = None

                if resp.status == 200:
                    return body
                detail = _error_detail(body)
                if resp.status == 401:
                    raise CradlewiseAuthError(detail or "Invalid or expired token")
                if resp.status == 403:
                    raise CradlewiseSubscriptionError(
                        detail or "Nurture Plus subscription is not active"
                    )
                if resp.status == 429:
                    retry_after: int | None = None
                    try:
                        retry_after = int(resp.headers["Retry-After"])
                    except (KeyError, ValueError):
                        pass
                    raise CradlewiseRateLimitError(
                        detail or "Rate limit exceeded", retry_after
                    )
                raise CradlewiseError(f"HTTP {resp.status}: {detail}")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CradlewiseConnectionError(str(err)) from err

    async def get_status(self) -> dict[str, Any]:
        """Return the current baby status."""
        return await self._get("/baby/status")

    async def _get_range(
        self, path: str, start: datetime, end: datetime
    ) -> dict[str, Any]:
        return await self._get(
            path,
            {"start_time": format_api_time(start), "end_time": format_api_time(end)},
        )

    async def get_day_metrics(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Return per-day key metrics (range must span 1-8 days)."""
        return await self._get_range("/sleep/day-metrics", start, end)

    async def get_weekly_metrics(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Return weekly sleep metrics."""
        return await self._get_range("/sleep/weekly-sleep-metrics", start, end)
