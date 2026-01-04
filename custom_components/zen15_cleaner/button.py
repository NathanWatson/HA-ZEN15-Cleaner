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


@dataclass
class Zen15ResetTarget:
    """Represents the reset button target (the filtered sensor) for a ZEN15/ZEN04."""

    zooz_device_id: str           # original Zooz device.id (same as in sensor.py)
    device_name: str | None
    manufacturer: str | None
    model: str | None
    filtered_entity_id: str       # actual entity_id of the Energy Filtered sensor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up reset buttons for ZEN15/ZEN04 Cleaner."""

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    targets: List[Zen15ResetTarget] = []

    # Discover all Zooz ZEN15/ZEN04 devices
    for device in device_reg.devices.values():
        manufacturer = (device.manufacturer or "").strip()
        model = (device.model or "").strip()

        if manufacturer.lower() != "zooz":
            continue
        if "zen15" not in model.lower() and "zen04" not in model.lower():
            continue

        # Our filtered sensor unique_id in sensor.py:
        #   unique_id = f"{device.id}_energy_filtered"
        sensor_uid = f"{device.id}_energy_filtered"

        filtered_entity_id = entity_reg.async_get_entity_id(
            "sensor",   # domain
            DOMAIN,     # platform
            sensor_uid, # unique_id
        )
        if not filtered_entity_id:
            # Filtered sensor for this device not found (maybe not created yet)
            continue

        targets.append(
            Zen15ResetTarget(
                zooz_device_id=device.id,
                device_name=device.name or device.name_by_user,
                manufacturer=manufacturer,
                model=model,
                filtered_entity_id=filtered_entity_id,
            )
        )

    # Build the set of button unique_ids we actually expect
    expected_button_uids = {
        f"{entry.entry_id}_{t.zooz_device_id}_reset_energy_filtered"
        for t in targets
    }

    # Clean up old / duplicate button entities from this integration
    for ent in list(entity_reg.entities.values()):
        if ent.platform != DOMAIN:
            continue
        if ent.config_entry_id != entry.entry_id:
            continue
        if ent.domain != "button":
            continue

        if ent.unique_id not in expected_button_uids:
            # Stale / duplicate reset button – remove it
            entity_reg.async_remove(ent.entity_id)

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

        # One button per Zooz device
        self._attr_unique_id = (
            f"{entry_id}_{target.zooz_device_id}_reset_energy_filtered"
        )

        # IMPORTANT: identifiers match sensor.py: (DOMAIN, zooz_device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, target.zooz_device_id)},
            manufacturer=target.manufacturer,
            model=target.model,
            name=target.device_name,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        # Call our integration's entity service for this filtered sensor
        await self.hass.services.async_call(
            DOMAIN,
            "reset_filtered",
            {"entity_id": self._target.filtered_entity_id},
            blocking=True,
        )
