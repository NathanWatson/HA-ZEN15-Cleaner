# ZEN15 Cleaner

![ZEN15 Cleaner Logo](https://raw.githubusercontent.com/NathanWatson/HA-ZEN15-Cleaner/main/icons/logo_dark.png)

---

## Description

**ZEN15 Cleaner** is a Home Assistant custom integration that replaces noisy Zooz ZEN15 and ZEN04 power readings with a **clean, spike-free, virtual kWh counter** that is safe for the Energy Dashboard.

Many ZEN15 and ZEN04 devices occasionally report huge bogus jumps in kWh, which create ridiculous spikes and break statistics.  
ZEN15 Cleaner fixes that by:

- Tracking the original ZEN15/ZEN04 kWh sensor
- Computing only valid positive deltas
- Ignoring spikes, negative jumps, and rollovers
- Maintaining a zero-based virtual counter that only increases

Each ZEN15 or ZEN04 gets its own `*_energy_filtered` sensor plus a **Reset Energy Filtered** button.

---

## Features

- Auto-discovers all Zooz ZEN15 and ZEN04 devices
- Creates a virtual `*_energy_filtered` sensor per plug
- Adds a per-device **Reset Energy Filtered** button
- Filters spikes and negative jumps
- Detects meter resets / rollovers
- Self-heals around permanent behavior changes
- Automatically cleans up duplicate entities and empty devices
- Fully compatible with Home Assistant Energy (`state_class: total_increasing`)

---

## Installation

### Using HACS (recommended)

1. In HACS, go to **Integrations → Custom repositories**.
2. Add: `https://github.com/NathanWatson/HA-ZEN15-Cleaner`
3. Category: **Integration**
4. Install the integration and restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration → ZEN15 Cleaner**.

### Manual

1. Copy the `custom_components/zen15_cleaner` directory into your Home Assistant `config/custom_components` folder.
2. Restart Home Assistant.
3. Add the **ZEN15 Cleaner** integration from **Settings → Devices & Services**.

---

## Configuration

All configuration is done via the UI.

For each ZEN15 you can:

- Use global spike thresholds, or
- Override forward spike thresholds per device.

The integration will then expose:

- `sensor.<name>_energy_filtered`
- `button.<name>_reset_energy_filtered`

Use the filtered sensor in the **Energy Dashboard**.

---

## Documentation

Full documentation, examples, and migration notes are available in the main repository:

<https://github.com/NathanWatson/HA-ZEN15-Cleaner>
