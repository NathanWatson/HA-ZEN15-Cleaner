from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_FORWARD_THRESHOLD_KWH,
    CONF_BACKWARD_THRESHOLD_KWH,
    CONF_FORWARD_OVERRIDES,
    DEFAULT_FORWARD_THRESHOLD_KWH,
    DEFAULT_BACKWARD_THRESHOLD_KWH,
)


def _get_default_options(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry | None
) -> dict:
    """Return default or existing options."""
    if config_entry is None:
        return {
            CONF_FORWARD_THRESHOLD_KWH: DEFAULT_FORWARD_THRESHOLD_KWH,
            CONF_BACKWARD_THRESHOLD_KWH: DEFAULT_BACKWARD_THRESHOLD_KWH,
            CONF_FORWARD_OVERRIDES: "",
        }

    data = config_entry.data
    opts = config_entry.options

    return {
        CONF_FORWARD_THRESHOLD_KWH: opts.get(
            CONF_FORWARD_THRESHOLD_KWH,
            data.get(CONF_FORWARD_THRESHOLD_KWH, DEFAULT_FORWARD_THRESHOLD_KWH),
        ),
        CONF_BACKWARD_THRESHOLD_KWH: opts.get(
            CONF_BACKWARD_THRESHOLD_KWH,
            data.get(CONF_BACKWARD_THRESHOLD_KWH, DEFAULT_BACKWARD_THRESHOLD_KWH),
        ),
        CONF_FORWARD_OVERRIDES: opts.get(
            CONF_FORWARD_OVERRIDES,
            data.get(CONF_FORWARD_OVERRIDES, ""),
        ),
    }


class Zen15CleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZEN15 Cleaner."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Tell HA that this integration has an options flow."""
        return Zen15CleanerOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # Save initial thresholds & overrides in data
            return self.async_create_entry(
                title="ZEN15 Cleaner",
                data=user_input,
            )

        defaults = _get_default_options(self.hass, None)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_FORWARD_THRESHOLD_KWH,
                    default=defaults[CONF_FORWARD_THRESHOLD_KWH],
                ): vol.All(
                    cv.positive_float
                ),  # Max allowed increase in kWh per update
                vol.Optional(
                    CONF_BACKWARD_THRESHOLD_KWH,
                    default=defaults[CONF_BACKWARD_THRESHOLD_KWH],
                ): vol.All(
                    cv.positive_float
                ),  # Currently informational; decreases are always ignored
                vol.Optional(
                    CONF_FORWARD_OVERRIDES,
                    default=defaults[CONF_FORWARD_OVERRIDES],
                ): cv.string,  # Lines like "Fridge = 50"
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )


class Zen15CleanerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for ZEN15 Cleaner."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = _get_default_options(self.hass, self.config_entry)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_FORWARD_THRESHOLD_KWH,
                    default=defaults[CONF_FORWARD_THRESHOLD_KWH],
                ): vol.All(cv.positive_float),
                vol.Optional(
                    CONF_BACKWARD_THRESHOLD_KWH,
                    default=defaults[CONF_BACKWARD_THRESHOLD_KWH],
                ): vol.All(cv.positive_float),
                vol.Optional(
                    CONF_FORWARD_OVERRIDES,
                    default=defaults[CONF_FORWARD_OVERRIDES],
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
