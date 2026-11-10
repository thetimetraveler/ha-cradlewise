"""The Cradlewise integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CradlewiseApi
from .const import (
    CONF_SLEEP_INTERVAL,
    CONF_STATUS_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SLEEP_INTERVAL,
    DEFAULT_STATUS_INTERVAL,
)
from .coordinator import (
    CradlewiseConfigEntry,
    CradlewiseData,
    SleepCoordinator,
    StatusCoordinator,
)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CradlewiseConfigEntry) -> bool:
    """Set up Cradlewise from a config entry."""
    api = CradlewiseApi(async_get_clientsession(hass), entry.data[CONF_TOKEN])
    status = StatusCoordinator(
        hass, entry, api, entry.options.get(CONF_STATUS_INTERVAL, DEFAULT_STATUS_INTERVAL)
    )
    sleep = SleepCoordinator(
        hass, entry, api, entry.options.get(CONF_SLEEP_INTERVAL, DEFAULT_SLEEP_INTERVAL)
    )
    await status.async_config_entry_first_refresh()
    await sleep.async_config_entry_first_refresh()

    entry.runtime_data = CradlewiseData(status=status, sleep=sleep)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CradlewiseConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
