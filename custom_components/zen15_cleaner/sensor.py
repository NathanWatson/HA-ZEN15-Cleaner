from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

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
from homeassistant.util.slugify import slugify
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    DEFAULT_THRESHOLD_KWH,
    CONF_THRESHOLD_KWH,
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

    threshold_kwh = float(
        entry.options.get(
            CONF_THRESHOLD_KWH,
            entry.data.get(CONF_THRESHOLD_KWH, DEFAULT_THRESHOLD_KWH),
        )
    )


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
        for ent in er.async_entries_for_device(entity_reg, device.id, include_disabled_entities=False):
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

    entities: list[SensorEntity] = []

    for src in zen15_sources:
        base_name = src.device_name or src.raw_entity_id.split(".")[-1]
        slug = slugify(base_name or src.raw_entity_id)

        name = f"{base_name} Energy Filtered"
        unique_id = f"{src.device_id}_energy_filtered"

        entities.append(
            Zen15CleanedEnergySensor(
                hass=hass,
                source=src,
                name=name,
                unique_id=unique_id,
                slug=slug,
                threshold_kwh=threshold_kwh,
            )
        )

    if entities:
        async_add_entities(entities)


async def _find_energy_entity_for_device(hass: HomeAssistant, entity_ids: list[str]) -> str | None:
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
    """Filtered energy sensor for a ZEN15 device."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        hass: HomeAssistant,
        source: Zen15EnergySource,
        name: str,
        unique_id: str,
        slug: str,
        threshold_kwh: float,
    ) -> None:
        self.hass = hass
        self._source = source
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._slug = slug
        self._threshold_kwh = float(threshold_kwh)

        self._raw_entity_id = source.raw_entity_id
        self._native_value: float | None = None
        self._last_good_value: float | None = None
        self._spike_ignored_count: int = 0
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
            "last_good_value": self._last_good_value,
            "threshold_kwh": self._threshold_kwh,
            "spike_ignored_count": self._spike_ignored_count,
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()

        # Restore last state
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
            "",
        ):
            try:
                val = float(last_state.state)
                self._native_value = val
                self._last_good_value = val
            except (TypeError, ValueError):
                pass

            # Restore spike count if present
            if "spike_ignored_count" in last_state.attributes:
                try:
                    self._spike_ignored_count = int(
                        last_state.attributes["spike_ignored_count"]
                    )
                except (TypeError, ValueError):
                    self._spike_ignored_count = 0

        # Also try current raw state once at startup
        self._apply_raw_state(self.hass.states.get(self._raw_entity_id))

        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            self._apply_raw_state(new_state)

        # Subscribe to raw entity state changes
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
    def _apply_raw_state(self, state) -> None:
        """Apply logic to a new raw state."""
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None, ""):
            return

        try:
            raw_value = float(state.state)
        except (TypeError, ValueError):
            return

        # First valid value
        if self._native_value is None or self._last_good_value is None:
            self._native_value = raw_value
            self._last_good_value = raw_value
            self.async_write_ha_state()
            return

        last = self._last_good_value

        # Downward jump: treat as glitch/reset, ignore
        if raw_value < last:
            self._spike_ignored_count += 1
            self.async_write_ha_state()
            return

        # Huge forward jump
        if (raw_value - last) > self._threshold_kwh:
            self._spike_ignored_count += 1
            self.async_write_ha_state()
            return

        # Normal update
        self._native_value = raw_value
        self._last_good_value = raw_value
        self.async_write_ha_state()
