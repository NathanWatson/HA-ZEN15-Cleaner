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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZEN15 cleaned energy sensors from a config entry."""

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
    # Kept for compatibility, but not used in the new model for self-heal runs.
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

    # Collect all ZEN15 devices
    for device in device_reg.devices.values():
        manufacturer = (device.manufacturer or "").strip()
        model = (device.model or "").strip()

        if manufacturer.lower() != "zooz":
            continue

        if "zen15" not in model.lower():
            continue

        # Find candidate sensor entities for this device
        candidates: list[str] = []
        for ent in er.async_entries_for_device(
            entity_reg,
            device.id,
            include_disabled_entities=False,
        ):
            if ent.domain != "sensor":
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

    entities: List[SensorEntity] = []

    for src in zen15_sources:
        base_name = src.device_name or src.raw_entity_id.split(".")[-1]
        slug = _slug(base_name or src.raw_entity_id)

        forward = per_device.get(src.device_id, global_forward)
        backward = global_backward

        name = f"{base_name} Energy Filtered"
        unique_id = f"{src.device_id}_energy_filtered_{slug}"

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

    if not entities:
        return

    async_add_entities(entities)

    # Register an entity service so you can call:
    #   service: sensor.reset_filtered
    #   target:  entity_id: sensor.<name>_energy_filtered
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "reset_filtered",
        {},
        "async_reset_filtered",
    )


async def _find_energy_entity_for_device(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> str | None:
    """Pick the best candidate raw kWh energy sensor among entity_ids."""
    best_candidate: str | None = None

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            continue

        attrs = state.attributes
        dev_class = attrs.get("device_class")
        unit = attrs.get("unit_of_measurement")
        state_class = attrs.get("state_class")

        # Must be in kWh
        if str(unit).lower() not in ("kwh", "kw·h", "kw/h"):
            continue

        # Must be energy
        if dev_class != SensorDeviceClass.ENERGY:
            continue

        # Prefer total_increasing
        if state_class == SensorStateClass.TOTAL_INCREASING:
            return entity_id

        if best_candidate is None:
            best_candidate = entity_id

    return best_candidate


class Zen15CleanedEnergySensor(RestoreEntity, SensorEntity):
    """
    Zero-based, spike-filtered virtual energy sensor for a ZEN15 device.

    - Starts at 0 on first install.
    - Only adds sane, positive deltas from the raw ZEN15 kWh sensor.
    - Ignores negative jumps (resets/rollovers) and big spikes beyond thresholds.
    """

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

        # Thresholds are per-step delta limits
        self._forward_threshold_kwh = float(forward_threshold_kwh)
        self._backward_threshold_kwh = float(backward_threshold_kwh)

        # Kept for schema compatibility; not used in delta logic anymore
        self._reject_run_limit = int(reject_run_limit)
        self._reject_run_count: int = 0

        self._raw_entity_id = source.raw_entity_id

        # Virtual counter & raw tracking
        self._virtual_total: float = 0.0  # our zero-based total
        self._last_raw_value: float | None = None
        self._last_delta_kwh: float | None = None

        # Diagnostics
        self._reset_detected: bool = False
        self._spike_ignored: bool = False

        self._unsub_state = None

        # What HA sees as the sensor state
        self._native_value: float | None = None

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
            # kept for backwards compatibility / visibility
            "reject_run_count": self._reject_run_count,
            "reject_run_limit": self._reject_run_limit,
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()

        # Restore our virtual total from last state if available
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
            "",
        ):
            try:
                val = float(last_state.state)
                self._virtual_total = val
                self._native_value = val
            except (TypeError, ValueError):
                pass

            # Restore last_raw_value from attributes if present
            last_raw = last_state.attributes.get("last_raw_value")
            if last_raw is not None:
                try:
                    self._last_raw_value = float(last_raw)
                except (TypeError, ValueError):
                    pass

        # Apply current raw state once on startup
        self._apply_raw_state(self.hass.states.get(self._raw_entity_id), initial=True)

        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            self._apply_raw_state(new_state)

        self._unsub_state = async_track_state_change_event(
            self.hass,
            [self._raw_entity_id],
            _state_listener,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None

    @callback
    def _apply_raw_state(self, state, initial: bool = False) -> None:
        """
        Handle a new raw state from the ZEN15 kWh entity.

        We do NOT mirror the raw value. Instead we:
        - Track the last raw reading.
        - Compute delta = raw_now - last_raw.
        - If delta is a sane, positive value within thresholds → add to our virtual total.
        - If delta is negative beyond backward_threshold → treat as reset and add nothing.
        - If delta is positive but above forward_threshold → treat as spike and add nothing.
        """
        if state is None or state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
            "",
        ):
            return

        try:
            raw_value = float(state.state)
        except (TypeError, ValueError):
            return

        # Reset diagnostics each cycle
        self._reset_detected = False
        self._spike_ignored = False

        # First valid raw value: just store it, do NOT change the virtual total.
        if self._last_raw_value is None:
            self._last_raw_value = raw_value
            self._last_delta_kwh = 0.0
            # For a brand-new install, _virtual_total starts at 0.
            # For restored entities, _virtual_total is whatever we restored.
            self._native_value = self._virtual_total
            self.async_write_ha_state()
            return

        # Compute raw delta
        delta = raw_value - self._last_raw_value
        self._last_delta_kwh = delta

        # Decide what to do with this delta
        delta_clean = 0.0

        # 1) Big negative jump -> treat as reset/rollover; don't add anything
        if delta < -self._backward_threshold_kwh:
            self._reset_detected = True
            delta_clean = 0.0

        # 2) Big positive jump -> treat as spike; don't add anything
        elif delta > self._forward_threshold_kwh:
            self._spike_ignored = True
            delta_clean = 0.0

        # 3) Delta within thresholds:
        else:
            # Don't subtract on small negative deltas; just treat as 0 usage
            if delta > 0:
                delta_clean = delta
            else:
                delta_clean = 0.0

        # Apply clean delta to our virtual total
        if delta_clean > 0:
            self._virtual_total += delta_clean

        # Expose our virtual total as the sensor state
        self._native_value = self._virtual_total

        # Update raw tracker and push state
        self._last_raw_value = raw_value
        self.async_write_ha_state()

    async def async_reset_filtered(self) -> None:
        """
        Reset our virtual total to 0 for this entity.

        IMPORTANT:
        - We do NOT reset _last_raw_value, so the next delta will be computed
          from the current raw reading forward (no replay of historical usage).
        - You probably want to pair this with a statistics purge for the
          corresponding entity in HA's Energy DB if you care about history.
        """
        self._virtual_total = 0.0
        self._native_value = 0.0
        self._reject_run_count = 0
        self.async_write_ha_state()
