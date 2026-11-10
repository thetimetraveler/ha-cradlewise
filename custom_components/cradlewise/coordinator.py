"""Data update coordinators for Cradlewise."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    CradlewiseApi,
    CradlewiseAuthError,
    CradlewiseConnectionError,
    CradlewiseError,
    CradlewiseRateLimitError,
    CradlewiseSubscriptionError,
)
from .const import BABY_STATUSES, DAY_METRICS_WINDOW, DOMAIN, WEEKLY_WINDOW

_LOGGER = logging.getLogger(__name__)

type CradlewiseConfigEntry = ConfigEntry[CradlewiseData]


def parse_api_datetime(value: Any) -> datetime | None:
    """Parse an API timestamp (ISO 8601 or 'YYYY-MM-DD HH:MM:SS[.ffffff]'), as UTC."""
    if not isinstance(value, str):
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


@dataclass
class BabyStatus:
    """Parsed /baby/status response."""

    status: str | None
    since: datetime | None
    is_in_crib: bool | None
    bounce: bool | None
    music: bool | None


@dataclass
class SleepData:
    """Parsed sleep metrics."""

    # Current day (day start -> now)
    soothes: float | None = None
    naps: float | None = None
    nap_details: list[dict[str, Any]] = field(default_factory=list)
    longest_stretch_seconds: float | None = None
    time_in_bed_minutes: float | None = None
    awake_in_bed_seconds: float | None = None
    rise_time: datetime | None = None
    bedtime: datetime | None = None
    day: datetime | None = None
    # Last 7 days
    avg_sleep_minutes: float | None = None
    avg_day_sleep_minutes: float | None = None
    avg_night_sleep_minutes: float | None = None
    avg_nap_duration_minutes: float | None = None
    avg_naps_per_day: float | None = None


@dataclass
class CradlewiseData:
    """Runtime data stored on the config entry."""

    status: StatusCoordinator
    sleep: SleepCoordinator


def _on_error(err: CradlewiseError) -> None:
    """Translate API errors into coordinator exceptions."""
    if isinstance(err, CradlewiseAuthError):
        raise ConfigEntryAuthFailed(
            "The Cradlewise token is invalid or has expired"
        ) from err
    if isinstance(err, CradlewiseSubscriptionError):
        raise UpdateFailed(
            "A Cradlewise Nurture Plus subscription is required"
        ) from err
    if isinstance(err, CradlewiseRateLimitError):
        raise UpdateFailed(
            f"Rate limited by Cradlewise (retry after {err.retry_after}s)"
        ) from err
    if isinstance(err, CradlewiseConnectionError):
        raise UpdateFailed(f"Error communicating with Cradlewise: {err}") from err
    raise UpdateFailed(str(err)) from err


class StatusCoordinator(DataUpdateCoordinator[BabyStatus]):
    """Polls the current baby status."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: CradlewiseApi,
        interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} status",
            update_interval=timedelta(seconds=interval),
        )
        self.api = api

    async def _async_update_data(self) -> BabyStatus:
        try:
            raw = await self.api.get_status()
        except CradlewiseError as err:
            _on_error(err)
        raw = raw if isinstance(raw, dict) else {}
        status = raw.get("status")
        if status not in BABY_STATUSES:
            if status is not None:
                _LOGGER.debug("Unknown baby status %r", status)
            status = None
        mode = raw.get("crib_mode")
        mode = mode if isinstance(mode, dict) else {}

        def on_off(key: str) -> bool | None:
            value = mode.get(key)
            return None if value is None else str(value).lower() == "on"

        in_crib = raw.get("is_in_crib")
        return BabyStatus(
            status=status,
            since=parse_api_datetime(raw.get("since")),
            is_in_crib=in_crib if isinstance(in_crib, bool) else None,
            bounce=on_off("bounce"),
            music=on_off("music"),
        )


def parse_day_metrics(raw: Any, now: datetime) -> dict[str, Any]:
    """Pick the current day out of a day-metrics response."""
    metrics = raw.get("metrics") if isinstance(raw, dict) else None
    if not isinstance(metrics, list):
        return {}
    dated: list[tuple[datetime, dict[str, Any]]] = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        day = parse_api_datetime(item.get("date"))
        if day is not None:
            dated.append((day, item))
    if not dated:
        return {}
    dated.sort(key=lambda pair: pair[0])
    started = [pair for pair in dated if pair[0] <= now]
    day, entry = (started or dated)[-1]

    banners: dict[str, dict[str, Any]] = {}
    for banner in entry.get("banners") or []:
        if isinstance(banner, dict) and isinstance(banner.get("header"), str):
            data = banner.get("data")
            banners[banner["header"].strip().upper()] = (
                data if isinstance(data, dict) else {}
            )

    def value(header: str) -> Any:
        return banners.get(header, {}).get("value")

    naps = banners.get("NAPS", {}).get("naps")
    return {
        "day": day,
        "soothes": _number(value("SOOTHES")),
        "naps": _number(value("NAPS")),
        "nap_details": naps if isinstance(naps, list) else [],
        "longest_stretch_seconds": _number(value("LONGEST STRETCH")),
        "time_in_bed_minutes": _number(value("TIME IN BED")),
        "awake_in_bed_seconds": _number(value("AWAKE IN BED")),
        "rise_time": parse_api_datetime(value("RISE TIME")),
        "bedtime": parse_api_datetime(value("BEDTIME")),
    }


def parse_weekly_metrics(raw: Any) -> dict[str, Any]:
    """Pull the averages out of a weekly-sleep-metrics response."""
    raw = raw if isinstance(raw, dict) else {}
    graph = raw.get("sleep_graph_metrics")
    planner = raw.get("nap_planner_metrics")
    graph = graph if isinstance(graph, dict) else {}
    planner = planner if isinstance(planner, dict) else {}
    return {
        "avg_sleep_minutes": _number(graph.get("avg_sleep_in_mins")),
        "avg_day_sleep_minutes": _number(graph.get("avg_day_sleep_in_mins")),
        "avg_night_sleep_minutes": _number(graph.get("avg_night_sleep_in_mins")),
        "avg_nap_duration_minutes": _number(planner.get("avg_nap_duration_in_mins")),
        "avg_naps_per_day": _number(planner.get("avg_naps_per_day")),
    }


class SleepCoordinator(DataUpdateCoordinator[SleepData]):
    """Polls the (rate-limited) sleep metric endpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: CradlewiseApi,
        interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} sleep",
            update_interval=timedelta(minutes=interval),
        )
        self.api = api

    async def _async_update_data(self) -> SleepData:
        now = dt_util.utcnow()
        try:
            day_raw = await self.api.get_day_metrics(now - DAY_METRICS_WINDOW, now)
            weekly_raw = await self.api.get_weekly_metrics(now - WEEKLY_WINDOW, now)
        except CradlewiseError as err:
            _on_error(err)
        return SleepData(**parse_day_metrics(day_raw, now), **parse_weekly_metrics(weekly_raw))
