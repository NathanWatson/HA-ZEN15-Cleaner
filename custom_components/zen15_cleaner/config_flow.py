from __future__ import annotations

from typing import Any, Dict, List

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    CONF_FORWARD_THRESHOLD_KWH,
    CONF_BACKWARD_THRESHOLD_KWH,
    CONF_PER_DEVICE_THRESHOLDS,
    CONF_REJECT_RUN_LIMIT,
    DEFAULT_FORWARD_THRESHOLD_KWH,
    DEFAULT_BACKWARD_THRESHOLD_KWH,
    DEFAULT_REJECT_RUN_LIMIT,
)


def _is_zen15_device(device: dr.DeviceEntry) -> bool:
    """Return True if this device looks like a Zooz ZEN15."""
    manufacturer = (device.manufacturer or "").strip().lower()
    model = (device.model or "").strip().lower()
    return manufacturer == "zooz" and "zen15" in model


class Zen15CleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZEN15 Cleaner."""

    VERSION = 1

    async def async_step_user(self, user_input: Dict[str, Any] | None = None):
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Create a single config entry; we store global defaults in data.
            return self.async_create_entry(
                title="ZEN15 Cleaner",
                data={
                    CONF_FORWARD_THRESHOLD_KWH: user_input.get(
                        CONF_FORWARD_THRESHOLD_KWH, DEFAULT_FORWARD_THRESHOLD_KWH
                    ),
                    CONF_BACKWARD_THRESHOLD_KWH: user_input.get(
                        CONF_BACKWARD_THRESHOLD_KWH, DEFAULT_BACKWARD_THRESHOLD_KWH
                    ),
                    CONF_REJECT_RUN_LIMIT: user_input.get(
                        CONF_REJECT_RUN_LIMIT, DEFAULT_REJECT_RUN_LIMIT
                    ),
                    # per-device thresholds start empty; options flow will fill them
                    CONF_PER_DEVICE_THRESHOLDS: {},
                },
            )

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_FORWARD_THRESHOLD_KWH,
                    default=DEFAULT_FORWARD_THRESHOLD_KWH,
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_BACKWARD_THRESHOLD_KWH,
                    default=DEFAULT_BACKWARD_THRESHOLD_KWH,
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_REJECT_RUN_LIMIT,
                    default=DEFAULT_REJECT_RUN_LIMIT,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return Zen15CleanerOptionsFlowHandler(config_entry)


class Zen15CleanerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for ZEN15 Cleaner."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        errors: Dict[str, str] = {}
        entry = self.config_entry
        hass: HomeAssistant = self.hass  # type: ignore[assignment]

        # ----- Current values / defaults -----
        forward_default = entry.options.get(
            CONF_FORWARD_THRESHOLD_KWH,
            entry.data.get(CONF_FORWARD_THRESHOLD_KWH, DEFAULT_FORWARD_THRESHOLD_KWH),
        )
        backward_default = entry.options.get(
            CONF_BACKWARD_THRESHOLD_KWH,
            entry.data.get(
                CONF_BACKWARD_THRESHOLD_KWH, DEFAULT_BACKWARD_THRESHOLD_KWH
            ),
        )
        reject_default = entry.options.get(
            CONF_REJECT_RUN_LIMIT,
            entry.data.get(CONF_REJECT_RUN_LIMIT, DEFAULT_REJECT_RUN_LIMIT),
        )

        per_device_existing: Dict[str, float] = entry.options.get(
            CONF_PER_DEVICE_THRESHOLDS,
            entry.data.get(CONF_PER_DEVICE_THRESHOLDS, {}),
        )

        # Discover current ZEN15 devices so we can build per-device fields
        device_reg = dr.async_get(hass)
        zen15_devices: List[dr.DeviceEntry] = [
            dev for dev in device_reg.devices.values() if _is_zen15_device(dev)
        ]

        if user_input is not None:
            # ---- Build per-device overrides from submitted form ----
            per_device_new: Dict[str, float] = {}

            for device in zen15_devices:
