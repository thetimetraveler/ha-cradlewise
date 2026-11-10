"""Tests for the Cradlewise integration (HTTP is mocked)."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cradlewise.const import CONF_TOKEN, DOMAIN

BASE = "https://integrations.cradlewise.com/api/v1"
TOKEN = "cw_" + "a" * 40

STATUS = {
    "status": "sleeping",
    "since": "2026-03-17T03:12:45.123456Z",
    "is_in_crib": True,
    "crib_mode": {"bounce": "on", "music": "off"},
    "timestamp": "2026-03-17T03:30:00Z",
}


def _banner(type_, header, value, display="", **extra):
    return {"type": type_, "header": header, "data": {"value": value, "display_value": display, **extra}}


def _day(date):
    return {
        "date": date,
        "banners": [
            _banner("soothes", "SOOTHES", 2),
            _banner("info", "RISE TIME", "2026-03-16 15:05:00.000000"),
            _banner("info", "BEDTIME", "2026-03-17 02:10:00.000000"),
            _banner("naps", "NAPS", 3, naps=[{"start_time": "x", "end_time": "y", "duration_in_mins": 40}]),
            _banner("info", "LONGEST STRETCH", 14400),
            _banner("info", "TIME IN BED", 600),
            _banner("info", "AWAKE IN BED", 1800),
        ],
    }


DAY_METRICS = {
    "header": "KEY METRICS",
    "timezone": "America/Los_Angeles",
    "metrics": [_day("2026-03-15 15:00:00.000000"), _day("2026-03-16 15:00:00.000000"), _day("2999-01-01 15:00:00.000000")],
}
WEEKLY = {
    "sleep_graph_metrics": {
        "avg_sleep_in_mins": 840,
        "avg_day_sleep_in_mins": 300,
        "avg_night_sleep_in_mins": 540,
        "plot_values": [],
    },
    "nap_planner_metrics": {"avg_nap_duration_in_mins": 55, "avg_naps_per_day": 3.5, "plot_values": []},
}


def _mock_api(mock: AiohttpClientMocker) -> None:
    mock.get(f"{BASE}/baby/status", json=STATUS)
    mock.get(f"{BASE}/sleep/day-metrics", json=DAY_METRICS)
    mock.get(f"{BASE}/sleep/weekly-sleep-metrics", json=WEEKLY)


async def test_config_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    _mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: "nope"})
    assert result["errors"] == {"base": "invalid_token_format"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: TOKEN})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TOKEN: TOKEN}
    # token is sent as a bearer header
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {TOKEN}"


async def test_config_flow_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    for status, key in ((401, "invalid_auth"), (403, "no_subscription"), (429, "rate_limited")):
        aioclient_mock.clear_requests()
        aioclient_mock.get(f"{BASE}/baby/status", status=status, json={"detail": "x"})
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: TOKEN})
        assert result["errors"] == {"base": key}


async def test_entities(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    _mock_api(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TOKEN: TOKEN})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.cradlewise_crib_status").state == "sleeping"
    assert hass.states.get("binary_sensor.cradlewise_crib_in_crib").state == "on"
    assert hass.states.get("binary_sensor.cradlewise_crib_bounce").state == "on"
    assert hass.states.get("binary_sensor.cradlewise_crib_music").state == "off"
    assert hass.states.get("sensor.cradlewise_crib_soothes_today").state == "2"
    naps = hass.states.get("sensor.cradlewise_crib_naps_today")
    assert naps.state == "3" and naps.attributes["naps"][0]["duration_in_mins"] == 40
    assert float(hass.states.get("sensor.cradlewise_crib_longest_stretch").state) == 4.0
    assert float(hass.states.get("sensor.cradlewise_crib_average_sleep_7_days").state) == 14.0
    assert hass.states.get("sensor.cradlewise_crib_bedtime").state == "2026-03-17T02:10:00+00:00"


async def test_auth_failure_starts_reauth(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{BASE}/baby/status", status=401, json={"detail": "Token expired"})
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TOKEN: TOKEN})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())
