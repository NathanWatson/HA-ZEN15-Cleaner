from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Dict

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.helpers import entity_platform
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    CONF_FORWARD_THRESHOLD_KWH,
    CONF_BACKWARD_THRESHOLD_KWH,
    CONF_PER_DEVICE_THRESHOLDS,
    DEFAULT_FORWARD_THRESHOLD_KWH,
    DEFAULT_BACKWARD_THRESHOLD_KWH,
    CONF_REJECT_RUN_LIMIT,
    DEFAULT_REJECT_RUN_LIMIT,
)


def _slug(text: str) -> str:
    return (
        text.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )


@dataclass
class Zen15EnergySource:
    """Represents the raw ZEN15 kWh sensor we wrap."""
    device_id: str
    device_name: str | None
    manufacturer: str | None
    model: str | None
    raw_entity_id: str


# ---------------------------------------------------------
# PLATFORM SETUP
# ---------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZEN15 virtual filtered energy sensors."""

    data = entry.data
    opts = entry.options

    global_forward = float(
        opts.get(
            CONF_FORWARD_THRESHOLD_KWH,
            data.get(CONF_FORWARD_THRESHOLD_KWH, DEFAULT_FORWARD_THRESHOLD_KWH),
        )
    )
    global_backward = float(
        opts.get(
            CONF_BACKWARD_THRESHOLD_KWH,
            data.get(CONF_BACKWARD_THRESHOLD_KWH, DEFAULT_BACKWARD_THRESHOLD_KWH),
        )
    )

    # kept only for compatibility
    global_reject_run_limit = int(
        opts.get(
            CONF_REJECT_RUN_LIMIT,
            data.get(CONF_REJECT_RUN_LIMIT, DEFAULT_REJECT_RUN_LIMIT),
        )
    )

    per_device: Dict[str, float] = opts.get(
        CONF_PER_DEVICE_THRESHOLDS,
        data.get(CONF_PER_DEVICE_THRESHOLDS, {}),
    ) or {}

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    zen15_sources: List[Zen15EnergySource] = []

    # Discovery: find every Zooz ZEN15 and its ORIGINAL energy sensor.
    for device in device_reg.devices.values():
        manufacturer = (device.manufacturer or "").strip()
        model = (device.model or "").strip()

        if manufacturer.lower() != "zooz":
            continue
        if "zen15" not in model.lower():
            continue

        candidates: list[str] = []

        # Collect ONLY non-integration sensors (the original ZEN15 energy sensors)
        for ent in er.async_entries_for_device(
            entity_reg,
            device.id,
            include_disabled_entities=False,
        ):
            if ent.domain != "sensor":
                continue

            # IMPORTANT: Prevent wrapping our own sensors → avoids infinite filter chains
            if ent.platform == DOMAIN:
                continue

            candidates.append(ent.entity_id)

        raw_entity_id = await _find_energy_entity_for_device(hass, candidates)
        if not raw_entity_id:
            continue

        zen15_sources.append(
            Zen15EnergySource(
                device_id=device.id,
                device_name=device.name or device.name_by_user,
                manufacturer=manufacturer,
                model=model,
                raw_entity_id=raw_entity_id,
            )
        )

    # Build expected filtered sensors BEFORE entity creation
    expected_sensor_uids = {
        f"{src.device_id}_energy_filtered" for src in zen15_sources
    }

    # AUTO-CLEANUP: Remove stale duplicate filtered sensors
    for ent in list(entity_reg.entities.values()):
        if ent.platform != DOMAIN:
            continue
        if ent.config_entry_id != entry.entry_id:
            continue
        if ent.domain != "sensor":
            continue

        if ent.unique_id not in expected_sensor_uids:
            # _2, _3, _4, filters-of-filters – nuke them
            entity_reg.async_remove(ent.entity_id)

    # Clean up old / empty zen15_cleaner devices from earlier versions
    for device in list(device_reg.devices.values()):
        # Only touch devices that belong to this config entry
        if entry.entry_id not in device.config_entries:
            continue

        # Only touch devices owned by our integration
        if not any(iden[0] == DOMAIN for iden in device.identifiers):
            continue

        # Does this device still have any zen15_cleaner entities?
        ents = er.async_entries_for_device(
            entity_reg,
            device.id,
            include_disabled_entities=True,
        )
        has_our_entities = any(ent.platform == DOMAIN for ent in ents)

        if not has_our_entities:
            # No more entities for this zen15_cleaner device → safe to delete
            device_reg.async_remove_device(device.id)

    # Create the real filtered sensor entities
    entities: List[SensorEntity] = []

    for src in zen15_sources:
        base_name = src.device_name or src.raw_entity_id.split(".")[-1]

        forward = per_device.get(src.device_id, global_forward)
        backward = global_backward

        name = f"{base_name} Energy Filtered"
        unique_id = f"{src.device_id}_energy_filtered"  # stable forever

        entities.append(
            Zen15CleanedEnergySensor(
                hass=hass,
                source=src,
                name=name,
                unique_id=unique_id,
                forward_threshold_kwh=forward,
                backward_threshold_kwh=backward,
                reject_run_limit=global_reject_run_limit,
            )
        )

    if entities:
        async_add_entities(entities)

    # Register our public entity service
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "reset_filtered",
        {},
        "async_reset_filtered",
    )


# ---------------------------------------------------------
# RAW SENSOR PICKER
# ---------------------------------------------------------

async def _find_energy_entity_for_device(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> str | None:
    """Pick the best candidate raw kWh energy sensor."""
    best = None

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if not state:
            continue

        attrs = state.attributes

        if attrs.get("unit_of_measurement", "").lower() not in ("kwh", "kw·h", "kw/h"):
            continue
        if attrs.get("device_class") != SensorDeviceClass.ENERGY:
            continue

        if attrs.get("state_class") == SensorStateClass.TOTAL_INCREASING:
            return entity_id

        if best is None:
            best = entity_id

    return best


# ---------------------------------------------------------
# FILTERED VIRTUAL ENERGY SENSOR
# ---------------------------------------------------------

class Zen15CleanedEnergySensor(RestoreEntity, SensorEntity):
    """Zero-based, spike-filtered virtual energy sensor for a ZEN15."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        hass: HomeAssistant,
        source: Zen15EnergySource,
        name: str,
        unique_id: str,
        forward_threshold_kwh: float,
        backward_threshold_kwh: float,
        reject_run_limit: int = DEFAULT_REJECT_RUN_LIMIT,
    ) -> None:
        self.hass = hass
        self._source = source
        self._attr_name = name
        self._attr_unique_id = unique_id

        self._forward_threshold_kwh = float(forward_threshold_kwh)
        self._backward_threshold_kwh = float(backward_threshold_kwh)

        self._reject_run_limit = reject_run_limit  # kept for compatibility
        self._reject_run_count = 0

        self._raw_entity_id = source.raw_entity_id

        self._virtual_total = 0.0
        self._last_raw_value: float | None = None
        self._last_delta_kwh: float | None = None

        self._reset_detected = False
        self._spike_ignored = False

        self._native_value: float | None = None
        self._unsub_state = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, source.device_id)},
            manufacturer=source.manufacturer,
            model=source.model,
            name=source.device_name,
        )

    @property
    def native_value(self) -> float | None:
        return self._native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "raw_entity_id": self._raw_entity_id,
            "virtual_total_kwh": self._virtual_total,
            "last_raw_value": self._last_raw_value,
            "last_delta_kwh": self._last_delta_kwh,
            "forward_threshold_kwh": self._forward_threshold_kwh,
            "backward_threshold_kwh": self._backward_threshold_kwh,
            "reset_detected": self._reset_detected,
            "spike_ignored": self._spike_ignored,
            "reject_run_count": self._reject_run_count,
            "reject_run_limit": self._reject_run_limit,
        }

    # ---------------------------------------------------------
    # ENTITY LIFECYCLE
    # ---------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore last virtual total
        last = await self.async_get_last_state()
        if last and last.state not in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                val = float(last.state)
                self._virtual_total = val
                self._native_value = val
            except Exception:
                pass

            # restore last_raw_value if present
            lr = last.attributes.get("last_raw_value")
            if lr is not None:
                try:
                    self._last_raw_value = float(lr)
                except Exception:
                    pass

        # Prime with current raw reading
        self._apply_raw_state(self.hass.states.get(self._raw_entity_id), initial=True)

        @callback
        def _listener(event):
            self._apply_raw_state(event.data.get("new_state"))

        self._unsub_state = async_track_state_change_event(
            self.hass,
            [self._raw_entity_id],
            _listener,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None

    # ---------------------------------------------------------
    # FILTER LOGIC
    # ---------------------------------------------------------

    @callback
    def _apply_raw_state(self, state, initial: bool = False) -> None:
        if not state or state.state in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            raw = float(state.state)
        except Exception:
            return

        self._reset_detected = False
        self._spike_ignored = False

        if self._last_raw_value is None:
            self._last_raw_value = raw
            self._last_delta_kwh = 0.0
            self._native_value = self._virtual_total
            self.async_write_ha_state()
            return

        delta = raw - self._last_raw_value
        self._last_delta_kwh = delta
        delta_clean = 0.0

        # Big negative jump = reset
        if delta < -self._backward_threshold_kwh:
            self._reset_detected = True
        # Big positive jump = spike
        elif delta > self._forward_threshold_kwh:
            self._spike_ignored = True
        else:
            if delta > 0:
                delta_clean = delta

        if delta_clean > 0:
            self._virtual_total += delta_clean

        self._native_value = self._virtual_total
        self._last_raw_value = raw
        self.async_write_ha_state()

    # ---------------------------------------------------------
    # SERVICE: reset_filtered
    # ---------------------------------------------------------

    async def async_reset_filtered(self) -> None:
        self._virtual_total = 0.0
        self._native_value = 0.0
        self._reject_run_count = 0
        self.async_write_ha_state()
