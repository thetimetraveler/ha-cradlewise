"""Base entity for Cradlewise."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN


class CradlewiseEntity[CoordinatorT: DataUpdateCoordinator](CoordinatorEntity[CoordinatorT]):
    """Common base: one device per config entry (one baby per token)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CoordinatorT, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Cradlewise crib",
            manufacturer="Cradlewise",
        )
