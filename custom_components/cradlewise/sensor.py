"""Cradlewise sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BABY_STATUSES
from .coordinator import (
    BabyStatus,
    CradlewiseConfigEntry,
    SleepCoordinator,
    SleepData,
    StatusCoordinator,
)
from .entity import CradlewiseEntity


@dataclass(frozen=True, kw_only=True)
class StatusSensorDescription(SensorEntityDescription):
    """Sensor fed by /baby/status."""

    value_fn: Callable[[BabyStatus], str | datetime | None]


@dataclass(frozen=True, kw_only=True)
class SleepSensorDescription(SensorEntityDescription):
    """Sensor fed by the sleep metric endpoints."""

    value_fn: Callable[[SleepData], float | datetime | None]


STATUS_SENSORS: tuple[StatusSensorDescription, ...] = (
    StatusSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=BABY_STATUSES,
        value_fn=lambda d: d.status,
    ),
    StatusSensorDescription(
        key="status_since",
        translation_key="status_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.since,
    ),
)


def _duration(
    key: str,
    native: UnitOfTime,
    suggested: UnitOfTime,
    fn: Callable[[SleepData], float | None],
) -> SleepSensorDescription:
    return SleepSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=native,
        suggested_unit_of_measurement=suggested,
        suggested_display_precision=1 if suggested == UnitOfTime.HOURS else 0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=fn,
    )


SLEEP_SENSORS: tuple[SleepSensorDescription, ...] = (
    SleepSensorDescription(
        key="soothes",
        translation_key="soothes",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.soothes,
    ),
    SleepSensorDescription(
        key="naps",
        translation_key="naps",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.naps,
    ),
    _duration(
        "longest_stretch", UnitOfTime.SECONDS, UnitOfTime.HOURS,
        lambda d: d.longest_stretch_seconds,
    ),
    _duration(
        "time_in_bed", UnitOfTime.MINUTES, UnitOfTime.HOURS,
        lambda d: d.time_in_bed_minutes,
    ),
    _duration(
        "awake_in_bed", UnitOfTime.SECONDS, UnitOfTime.MINUTES,
        lambda d: d.awake_in_bed_seconds,
    ),
    SleepSensorDescription(
        key="rise_time",
        translation_key="rise_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.rise_time,
    ),
    SleepSensorDescription(
        key="bedtime",
        translation_key="bedtime",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.bedtime,
    ),
    _duration(
        "avg_sleep", UnitOfTime.MINUTES, UnitOfTime.HOURS, lambda d: d.avg_sleep_minutes
    ),
    _duration(
        "avg_day_sleep", UnitOfTime.MINUTES, UnitOfTime.HOURS,
        lambda d: d.avg_day_sleep_minutes,
    ),
    _duration(
        "avg_night_sleep", UnitOfTime.MINUTES, UnitOfTime.HOURS,
        lambda d: d.avg_night_sleep_minutes,
    ),
    _duration(
        "avg_nap_duration", UnitOfTime.MINUTES, UnitOfTime.MINUTES,
        lambda d: d.avg_nap_duration_minutes,
    ),
    SleepSensorDescription(
        key="avg_naps_per_day",
        translation_key="avg_naps_per_day",
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.avg_naps_per_day,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CradlewiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cradlewise sensors."""
    data = entry.runtime_data
    async_add_entities(
        [CradlewiseStatusSensor(data.status, entry, d) for d in STATUS_SENSORS]
        + [CradlewiseSleepSensor(data.sleep, entry, d) for d in SLEEP_SENSORS]
    )


class CradlewiseStatusSensor(CradlewiseEntity[StatusCoordinator], SensorEntity):
    """Sensor from the status endpoint."""

    entity_description: StatusSensorDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)


class CradlewiseSleepSensor(CradlewiseEntity[SleepCoordinator], SensorEntity):
    """Sensor from the sleep metric endpoints."""

    entity_description: SleepSensorDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        # Individual naps (start/end/duration) are exposed on the naps sensor.
        if self.entity_description.key == "naps":
            return {"naps": self.coordinator.data.nap_details}
        return None
