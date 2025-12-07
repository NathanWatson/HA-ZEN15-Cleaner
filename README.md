# ZEN15 Cleaner – Home Assistant Custom Integration

**Problem:** Zooz ZEN15 plugs occasionally report bogus energy values  
(e.g. huge kWh jumps or resets to 0). Home Assistant's statistics engine
treats those as real consumption, which blows up the Energy Dashboard and
Sankey graphs.

**Solution:** `zen15_cleaner` auto-discovers all ZEN15 devices and exposes
clean, filtered energy sensors that:

- Never go *backwards* (ignore resets / glitches)
- Ignore single-step jumps larger than a configurable kWh threshold
- Are marked correctly as `energy` / `total_increasing` for Energy Dashboard

You then point your Energy Dashboard and energy cards at the **filtered**
sensors instead of the raw ZEN15 kWh sensors.

---

## Features

- 🔍 **Auto-discovery**  
  Finds all devices with `manufacturer = "Zooz"` and `model` containing `ZEN15`
  using the Home Assistant device registry.

- ⚡ **Filtered energy sensor per ZEN15**  
  For each plug, creates `<Device Name> Energy Filtered` that:
  - Listens to the raw kWh entity (e.g. `sensor.fridge_electric_consumption_kwh`)
  - Ignores:
    - Downward jumps (resets / glitches)
    - Single-step increases larger than `threshold_kwh` (default: `10.0`)
  - Reports:
    - `device_class: energy`
    - `state_class: total_increasing`
    - `unit_of_measurement: kWh`

- 🚨 **Spike detection binary sensor**  
  Per ZEN15, creates `<Device Name> Energy Spike`:
  - `on` if any spikes have been detected and ignored
  - `problem` device class
  - Tracks `spike_ignored_count` as an attribute (for automations / debugging)

- ⚙️ **Configurable threshold (UI options)**  
  Change the global `threshold_kwh` (max allowed per-update kWh jump) via
  the integration’s **Options** flow.

- 💾 **State restore**  
  Filtered sensors and spike counters restore state across restarts using
  Home Assistant’s `RestoreEntity`.

---

## How It Works

1. The integration scans the **device registry** for devices where:
   - `manufacturer == "Zooz"`
   - `"ZEN15"` appears in the `model`

2. For each ZEN15 device, it looks at sensors attached to that device and
   picks the one that looks like a cumulative kWh sensor:
   - `device_class == energy`
   - `unit_of_measurement` in `kWh`
   - Prefer `state_class == total_increasing`

3. It then creates:
   - `Sensor`: `<Device Name> Energy Filtered`
   - `Binary sensor`: `<Device Name> Energy Spike`

4. The filtered sensor listens to the raw kWh value:

   - If value is *lower* than the last good value  
     → spike ignored, counter incremented, value not updated.

   - If value jumps up by more than `threshold_kwh` in one step  
     → spike ignored, counter incremented, value not updated.

   - Otherwise  
     → normal update, stored as the new last good value.

5. The Spike binary sensor uses similar logic but only:
   - Tracks whether spikes happened (`on` / `off`)
   - Tracks how many (`spike_ignored_count`)

---

## Installation

1. Locate your Home Assistant config directory (same place as `configuration.yaml`).

2. Inside it, create the custom components folder if it doesn’t exist:

   ```text
   custom_components/
