<p align="center">
  <img src="logo.png" alt="ZEN15 Cleaner Logo" width="600">
</p>

<p align="center">
  <a href="https://hacs.xyz/">
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS Custom">
  </a>
  <img src="https://img.shields.io/badge/Version-0.7.0-blue.svg" alt="Version 0.7.0">
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.12%2B-brightgreen.svg" alt="HA 2024.12+">
</p>

# 🔌 ZEN15 Cleaner – A Home Assistant Spike-Filtering Integration

ZEN15 Cleaner is a Home Assistant custom integration that fixes noisy, spike-prone energy readings from Zooz ZEN15 Power Switches.  
It keeps your Energy Dashboard clean by filtering out bogus kWh spikes while leaving valid consumption data intact.

## 🚀 Features

- Filters unrealistic kWh spikes from Zooz ZEN15 plugs  
- Per-device spike thresholds with a global default  
- Home Assistant native config flow + options flow  
- `sensor.reset_filtered` service to realign filtered values  
- Energy Dashboard safe (`device_class: energy`, `state_class: total_increasing`)  
- Diagnostic attributes to help tune thresholds and debug behavior  

## 📦 Installation

1. Copy this repository into your Home Assistant configuration directory under:

   ```text
   custom_components/zen15_cleaner/
   ```

2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **ZEN15 Cleaner**.

## 🔧 Configuration

During initial setup and later via **Configure**, you can:

- Set a **global forward threshold** (max allowed kWh increase per update).  
- Set a **global backward threshold** (informational; decreases are always blocked).  
- Set **per-device thresholds** for each ZEN15 (Fridge, Dishwasher, Furnace, etc.).

## ⚙️ Filtering Logic

Let:

- `raw` = raw ZEN15 kWh sensor value  
- `filtered` = value from ZEN15 Cleaner  
- `delta = raw - last_good_value`  

Rules:

- If `delta < 0` → ignored (never decrease filtered energy).  
- If `delta > threshold_kwh` → ignored (treated as a spike).  
- Otherwise → accepted and `filtered` is updated.

## 🧪 Reset Filtered Service

If a ZEN15 resets or you need to re-sync:

```yaml
service: sensor.reset_filtered
target:
  entity_id: sensor.fridge_energy_filtered
```

This aligns the filtered value with the current raw kWh reading while preserving Energy Dashboard statistics.

## 📊 Attributes

Each `*_energy_filtered` sensor exposes:

- `raw_entity_id`  
- `last_good_value`  
- `last_delta_kwh`  
- `forward_threshold_kwh`  
- `backward_threshold_kwh`  

## 📝 Example Lovelace Card

```yaml
type: entities
title: Cleaned ZEN15 Sensors
entities:
  - sensor.fridge_energy_filtered
  - sensor.dishwasher_energy_filtered
  - sensor.washing_machine_energy_filtered
  - sensor.furnace_energy_filtered
```

## 🐛 Troubleshooting

- If a filtered sensor remains flat:
  - Check `last_delta_kwh` in the attributes.
  - Increase the per-device forward threshold in the options UI.  

- If a device does not appear in the options:
  - Ensure the device manufacturer is **Zooz** and the model string contains **ZEN15**.
