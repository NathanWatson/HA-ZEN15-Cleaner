from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, DEFAULT_THRESHOLD_KWH, CONF_THRESHOLD_KWH


def _get_default_options(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry | None
) -> dict:
    """Return default or existing options."""
    if config_entry is None:
        # No entry yet: just return defaults
        return {CONF_THRESHOLD_KWH: DEFAULT_THRESHOLD_KWH}

    # Prefer options; fall back to data; then default
    return {
        CONF_THRESHOLD_KWH: config_entry.options.get(
            CONF_THRESHOLD_KWH,
            config_entry.data.get(CONF_THRESHOLD_KWH, DEFAULT_THRESHOLD_KWH),
        )
    }


class Zen15CleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZEN15 Cleaner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Only one instance allowed
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # Store initial threshold in data; options can override later
            threshold = float(
                user_input.get(CONF_THRESHOLD_KWH, DEFAULT_THRESHOLD_KWH)
            )
            return self.async_create_entry(
                title="ZEN15 Cleaner",
                data={CONF_THRESHOLD_KWH: threshold},
            )

        # Show initial form with threshold field
        options = _get_default_options(self.hass, None)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_THRESHOLD_KWH,
                    default=options[CONF_THRESHOLD_KWH],
                ): vol.All(cv.positive_float),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )


class Zen15CleanerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for ZEN15 Cleaner."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Save new options; integration will reload via update_listener
            return self.async_create_entry(title="", data=user_input)

        options = _get_default_options(self.hass, self.config_entry)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_THRESHOLD_KWH,
                    default=options[CONF_THRESHOLD_KWH],
                ): vol.All(cv.positive_float),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )


async def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> Zen15CleanerOptionsFlowHandler:
    """Get the options flow."""
    return Zen15CleanerOptionsFlowHandler(config_entry)
