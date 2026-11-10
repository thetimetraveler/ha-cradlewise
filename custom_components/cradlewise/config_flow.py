"""Config flow for Cradlewise."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    CradlewiseApi,
    CradlewiseAuthError,
    CradlewiseConnectionError,
    CradlewiseError,
    CradlewiseRateLimitError,
    CradlewiseSubscriptionError,
)
from .const import (
    CONF_SLEEP_INTERVAL,
    CONF_STATUS_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SLEEP_INTERVAL,
    DEFAULT_STATUS_INTERVAL,
    DOMAIN,
    MAX_SLEEP_INTERVAL,
    MAX_STATUS_INTERVAL,
    MIN_SLEEP_INTERVAL,
    MIN_STATUS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class CradlewiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cradlewise."""

    VERSION = 1

    async def _validate(self, token: str) -> str | None:
        """Return an error key if the token does not work, else None."""
        if not token.startswith("cw_"):
            return "invalid_token_format"
        api = CradlewiseApi(async_get_clientsession(self.hass), token)
        try:
            await api.get_status()
        except CradlewiseAuthError:
            return "invalid_auth"
        except CradlewiseSubscriptionError:
            return "no_subscription"
        except CradlewiseRateLimitError:
            return "rate_limited"
        except CradlewiseConnectionError:
            return "cannot_connect"
        except CradlewiseError:
            _LOGGER.exception("Unexpected Cradlewise API error")
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            if any(e.data.get(CONF_TOKEN) == token for e in self._async_current_entries()):
                return self.async_abort(reason="already_configured")
            if error := await self._validate(token):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Cradlewise", data={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="user", data_schema=TOKEN_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the token expires (tokens last 60 days)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            if error := await self._validate(token):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=TOKEN_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CradlewiseOptionsFlow:
        """Return the options flow."""
        return CradlewiseOptionsFlow()


class CradlewiseOptionsFlow(OptionsFlowWithReload):
    """Polling interval options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage polling intervals."""
        if user_input is not None:
            return self.async_create_entry(
                data={k: int(v) for k, v in user_input.items()}
            )
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATUS_INTERVAL,
                    default=options.get(CONF_STATUS_INTERVAL, DEFAULT_STATUS_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_STATUS_INTERVAL,
                        max=MAX_STATUS_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_SLEEP_INTERVAL,
                    default=options.get(CONF_SLEEP_INTERVAL, DEFAULT_SLEEP_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SLEEP_INTERVAL,
                        max=MAX_SLEEP_INTERVAL,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
