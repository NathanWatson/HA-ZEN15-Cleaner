from __future__ import annotations

from dataclasses import dataclass
from typing import List

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .sensor import (
    _find_energy_entity_for_device,
    _slug,
)


@dataclass
class Zen15ResetTarget:
    """Represents the reset button target (the filtered sensor) for a ZEN15."""

    device_id: str
    device_name: str | None
    manufacturer: str | None
    model: str | None
    raw_entity_id: str
    filtered_entity_id: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up reset buttons for ZEN15 Cleaner."""

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    targets: List[Zen15ResetTarget] = []

    # Discover all ZEN15 devices (same as in sensor.py)
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

        # Derive the filtered sensor entity_id from the same naming scheme used in sensor.py
        base_name = device.name or device.name_by_user or raw_entity_id.split(".")[-1]
        slug = _slug(base_name or raw_entity_id)
        # Your filtered sensor entity_id will normally be:
        #   sensor.<slug>_energy_filtered
        filtered_entity_id = f"sensor.{slug}_energy_filtered"

        # Only create a button if that filtered entity actually exists
        if entity_reg.async_get(filtered_entity_id) is None:
            continue

        targets.append(
            Zen15ResetTarget(
                device_id=device.id,
                device_name=device.name or device.name_by_user,
                manufacturer=manufacturer,
                model=model,
                raw_entity_id=raw_entity_id,
                filtered_entity_id=filtered_entity_id,
            )
        )

    if not targets:
        return

    buttons: list[ButtonEntity] = []

    for tgt in targets:
        buttons.append(
            Zen15ResetButton(
                hass=hass,
                target=tgt,
                entry_id=entry.entry_id,
            )
        )

    async_add_entities(buttons)


class Zen15ResetButton(ButtonEntity):
    """Button to reset the ZEN15 Cleaner virtual energy counter."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        target: Zen15ResetTarget,
        entry_id: str,
    ) -> None:
        self.hass = hass
        self._target = target

        base_name = target.device_name or target.filtered_entity_id.split(".")[-1]
        self._attr_name = f"{base_name} Reset Energy Filtered"

        self._attr_unique_id = f"{entry_id}_{target.device_id}_reset_energy_filtered"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, target.device_id)},
            manufacturer=target.manufacturer,
            model=target.model,
            name=target.device_name,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        # Call the sensor.reset_filtered service for the corresponding filtered sensor
        await self.hass.services.async_call(
            "sensor",
            "reset_filtered",
            {"entity_id": self._target.filtered_entity_id},
            blocking=True,
        )
