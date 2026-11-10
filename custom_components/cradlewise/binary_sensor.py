"""Cradlewise binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BabyStatus, CradlewiseConfigEntry, StatusCoordinator
from .entity import CradlewiseEntity


@dataclass(frozen=True, kw_only=True)
class CradlewiseBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor fed by /baby/status."""

    value_fn: Callable[[BabyStatus], bool | None]


BINARY_SENSORS: tuple[CradlewiseBinarySensorDescription, ...] = (
    CradlewiseBinarySensorDescription(
        key="in_crib",
        translation_key="in_crib",
        value_fn=lambda d: d.is_in_crib,
    ),
    CradlewiseBinarySensorDescription(
        key="bounce",
        translation_key="bounce",
        value_fn=lambda d: d.bounce,
    ),
    CradlewiseBinarySensorDescription(
        key="music",
        translation_key="music",
        value_fn=lambda d: d.music,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CradlewiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cradlewise binary sensors."""
    coordinator = entry.runtime_data.status
    async_add_entities(
        CradlewiseBinarySensor(coordinator, entry, d) for d in BINARY_SENSORS
    )


class CradlewiseBinarySensor(CradlewiseEntity[StatusCoordinator], BinarySensorEntity):
    """Binary sensor from the status endpoint."""

    entity_description: CradlewiseBinarySensorDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
