from __future__ import annotations

from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    CONF_FORWARD_THRESHOLD_KWH,
    CONF_BACKWARD_THRESHOLD_KWH,
    CONF_PER_DEVICE_THRESHOLDS,
    DEFAULT_FORWARD_THRESHOLD_KWH,
    DEFAULT_BACKWARD_THRESHOLD_KWH,
)


def _find_zen15_devices(hass):
    """Return list of (device, display_name) for Zooz ZEN15 devices."""
    dev_reg = dr.async_get(hass)
    devices: list[tuple[Any, str]] = []

    for dev in dev_reg.devices.values():
        manufacturer = (dev.manufacturer or "").strip()
        model = (dev.model or "").strip()

        if manufacturer.lower() != "zooz":
            continue
        if "zen15" not in model.lower():
            continue

        name = dev.name or dev.name_by_user or "ZEN15"
        devices.append((dev, name))

    return devices


def _get_default_options(
    hass, config_entry: config_entries.ConfigEntry | None
) -> dict:
    """Return defaults + any stored options/data."""
    if config_entry is None:
        return {
            CONF_FORWARD_THRESHOLD_KWH: DEFAULT_FORWARD_THRESHOLD_KWH,
            CONF_BACKWARD_THRESHOLD_KWH: DEFAULT_BACKWARD_THRESHOLD_KWH,
            CONF_PER_DEVICE_THRESHOLDS: {},  # device_id -> kwh
        }

    data = config_entry.data
    opts = config_entry.options

    per_device = opts.get(
        CONF_PER_DEVICE_THRESHOLDS,
        data.get(CONF_PER_DEVICE_THRESHOLDS, {}),
    ) or {}

    return {
        CONF_FORWARD_THRESHOLD_KWH: opts.get(
            CONF_FORWARD_THRESHOLD_KWH,
            data.get(CONF_FORWARD_THRESHOLD_KWH, DEFAULT_FORWARD_THRESHOLD_KWH),
        ),
        CONF_BACKWARD_THRESHOLD_KWH: opts.get(
            CONF_BACKWARD_THRESHOLD_KWH,
            data.get(CONF_BACKWARD_THRESHOLD_KWH, DEFAULT_BACKWARD_THRESHOLD_KWH),
        ),
        CONF_PER_DEVICE_THRESHOLDS: per_device,
    }


class Zen15CleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ZEN15 Cleaner."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow handler."""
        return Zen15CleanerOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initial setup step."""
        # Single instance only
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # User submitted form
        if user_input is not None:
            per_device: Dict[str, float] = {}
            field_map: Dict[str, str] = self._device_field_map

            for field_key, value in list(user_input.items()):
                if field_key in field_map:
                    try:
                        per_device[field_map[field_key]] = float(value)
                    except (TypeError, ValueError):
                        continue

            data = {
                CONF_FORWARD_THRESHOLD_KWH: float(
                    user_input.get(
                        CONF_FORWARD_THRESHOLD_KWH,
                        DEFAULT_FORWARD_THRESHOLD_KWH,
                    )
                ),
                CONF_BACKWARD_THRESHOLD_KWH: float(
                    user_input.get(
                        CONF_BACKWARD_THRESHOLD_KWH,
                        DEFAULT_BACKWARD_THRESHOLD_KWH,
                    )
                ),
                CONF_PER_DEVICE_THRESHOLDS: per_device,
            }

            return self.async_create_entry(
                title="ZEN15 Cleaner",
                data=data,
            )

        # First time: build form
        defaults = _get_default_options(self.hass, None)
        devices = _find_zen15_devices(self.hass)

        self._device_field_map: Dict[str, str] = {}
        schema_dict: Dict[Any, Any] = {}

        # Global thresholds
        schema_dict[
            vol.Optional(
                CONF_FORWARD_THRESHOLD_KWH,
                default=defaults[CONF_FORWARD_THRESHOLD_KWH],
            )
        ] = vol.All(cv.positive_float)

        schema_dict[
            vol.Optional(
                CONF_BACKWARD_THRESHOLD_KWH,
                default=defaults[CONF_BACKWARD_THRESHOLD_KWH],
            )
        ] = vol.All(cv.positive_float)

        # Per-device thresholds
        per_device_defaults: Dict[str, float] = defaults[CONF_PER_DEVICE_THRESHOLDS]

        for dev, display_name in devices:
            field_key = f"{display_name} threshold_kwh"
            self._device_field_map[field_key] = dev.id
            default_val = per_device_defaults.get(
                dev.id, defaults[CONF_FORWARD_THRESHOLD_KWH]
            )
            schema_dict[
                vol.Optional(field_key, default=default_val)
            ] = vol.All(cv.positive_float)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_dict),
        )


class Zen15CleanerOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow (after install)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._device_field_map: Dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure options."""
        if user_input is not None:
            per_device: Dict[str, float] = {}
            field_map: Dict[str, str] = self._device_field_map

            for field_key, value in list(user_input.items()):
                if field_key in field_map:
                    try:
                        per_device[field_map[field_key]] = float(value)
                    except (TypeError, ValueError):
                        continue

            opts = {
                CONF_FORWARD_THRESHOLD_KWH: float(
                    user_input.get(
                        CONF_FORWARD_THRESHOLD_KWH,
                        DEFAULT_FORWARD_THRESHOLD_KWH,
                    )
                ),
                CONF_BACKWARD_THRESHOLD_KWH: float(
                    user_input.get(
                        CONF_BACKWARD_THRESHOLD_KWH,
                        DEFAULT_BACKWARD_THRESHOLD_KWH,
                    )
                ),
                CONF_PER_DEVICE_THRESHOLDS: per_device,
            }

            return self.async_create_entry(title="", data=opts)

        defaults = _get_default_options(self.hass, self.config_entry)
        devices = _find_zen15_devices(self.hass)

        self._device_field_map = {}
        schema_dict: Dict[Any, Any] = {}

        # Global thresholds
        schema_dict[
            vol.Optional(
                CONF_FORWARD_THRESHOLD_KWH,
                default=defaults[CONF_FORWARD_THRESHOLD_KWH],
            )
        ] = vol.All(cv.positive_float)

        schema_dict[
            vol.Optional(
                CONF_BACKWARD_THRESHOLD_KWH,
                default=defaults[CONF_BACKWARD_THRESHOLD_KWH],
            )
        ] = vol.All(cv.positive_float)

        # Per-device thresholds
        per_device_defaults: Dict[str, float] = defaults[CONF_PER_DEVICE_THRESHOLDS]

        for dev, display_name in devices:
            field_key = f"{display_name} threshold_kwh"
            self._device_field_map[field_key] = dev.id
            default_val = per_device_defaults.get(
                dev.id, defaults[CONF_FORWARD_THRESHOLD_KWH]
            )
            schema_dict[
                vol.Optional(field_key, default=default_val)
            ] = vol.All(cv.positive_float)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
