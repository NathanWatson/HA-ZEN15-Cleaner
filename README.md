# 🔌 ZEN15 Cleaner – A Home Assistant Spike-Filtering & Self-Healing Integration

<p align="center">
  <img src="https://raw.githubusercontent.com/NathanWatson/HA-ZEN15-Cleaner/main/icons/logo_dark.png" alt="ZEN15 Cleaner Logo" width="600">
</p>

<p align="center">
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS Custom"></a>
  <img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FNathanWatson%2FHA-ZEN15-Cleaner%2Frefs%2Fheads%2Fmain%2Fcustom_components%2Fzen15_cleaner%2Fmanifest.json&query=version&label=Manifest" alt="Manifest badge">
  <a href="https://github.com/NathanWatson/HA-ZEN15-Cleaner/releases"><img src="https://img.shields.io/github/v/release/NathanWatson/HA-ZEN15-Cleaner?logo=github&color=8A2BE2" alt="Release Badge"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.12%2B-brightgreen.svg" alt="HA 2024.12+">
</p>

# Overview

**ZEN15 Cleaner** is a Home Assistant custom integration that repairs noisy, spike-prone kWh readings from **ZOOZ ZEN15 Power Switches**.

Many ZEN15 devices occasionally report massive bogus jumps—often thousands of kWh in one update. These spikes pollute the Energy Dashboard and break daily/weekly/monthly statistics.

This integration creates a *filtered* kWh sensor that:

- Removes bogus spikes  
- **Self-heals** when a device’s readings shift permanently  
- Handles meter resets gracefully  
- Is Energy Dashboard–compatible (`state_class: total_increasing`)  
- Lets you fine-tune thresholds per device  

---

# 🚀 Features

### ✔ Filters out unrealistic kWh jumps  
Prevents bad ZEN15 readings from appearing in the Energy Dashboard.

### ✔ Self-healing algorithm  
If a spike keeps repeating (e.g., after a device firmware reset or behavior change), the sensor eventually accepts the new value as the correct baseline.

### ✔ Per-device tuning  
Each ZEN15 gets its own configurable spike threshold—handy for devices with unusual power profiles.

### ✔ Global + per-device configuration flow  
All settings are configurable in **Settings → Devices & Services → ZEN15 Cleaner → Configure**.

### ✔ Debug visibility  
Every filtered sensor exposes attributes you can use to diagnose spikes, behavior, self-healing progress, and thresholds.

### ✔ Reset service  
`sensor.reset_filtered` force-aligns filtered kWh with current raw readings.

---

# 📦 Installation

1. Place the integration here:

```
custom_components/zen15_cleaner/
```

2. Restart Home Assistant  
3. Go to **Settings → Devices & Services → Add Integration → ZEN15 Cleaner**

---

# 🔧 Configuration

During setup and in the Options flow, you can configure:

### **Global Forward Threshold (kWh)**
Maximum allowed increase per update before a reading is considered a spike.

### **Global Backward Threshold (kWh)**
Displayed for debugging; filtered energy never decreases.

### **Reject Run Limit (Self-Heal Timer)**
How many *consecutive rejected spikes* must occur before the filter decides:

> “This isn’t a spike anymore — this is the new baseline.”

Example:  
If set to 12, and readings keep jumping by +2400 kWh each time, after 12 rejections the filter **auto-adopts** the new value.

### **Per-Device Forward Threshold Overrides**
Each detected ZEN15 appears with a friendly name like:

> Furnace ZEN15 (device_id)

You can specify a threshold just for that device.

---

# ⚙️ Filtering & Self-Healing Logic

Let:

- `raw` = incoming ZEN15 kWh value  
- `filtered` = output of ZEN15 Cleaner  
- `last_good_value` = most recently accepted reading  
- `delta = raw - last_good_value`  

### 🛑 1. Reject backward movement
Energy never decreases. Any negative deltas are ignored unless part of a meter reset.

### ⚠️ 2. Reject spikes  
If `delta > forward_threshold_kwh`, the value is ignored *temporarily*.

### 🔄 3. Self-healing  
If the *same type of spike* happens repeatedly, and the number of rejections reaches `reject_run_limit`:

→ The filter **accepts the raw value as the new baseline**  
→ `reject_run_count` resets to 0  

This prevents the sensor from becoming “stuck” forever after a large permanent shift.

### 🔁 4. Meter Reset Detection  
If kWh suddenly drops near zero and stays there, the filter assumes the meter reset and adopts the new baseline immediately.

---

# 🧪 Reset Filtered Service

If a ZEN15 resets or you want to realign filtered output:

```yaml
service: sensor.reset_filtered
target:
  entity_id: sensor.furnace_energy_filtered
```

This updates the filtered value without breaking long-term statistics.

---

# 📊 Sensor Attributes

Each `*_energy_filtered` sensor exposes:

| Attribute | Description |
|----------|-------------|
| `raw_entity_id` | The source ZEN15 kWh sensor |
| `last_good_value` | Most recently accepted (filtered) kWh value |
| `last_delta_kwh` | Difference between raw and last good value |
| `forward_threshold_kwh` | Current threshold for this device |
| `backward_threshold_kwh` | Backward delta block threshold |
| `reject_run_count` | How many spike rejections have occurred in a row |
| `reject_run_limit` | How many rejections must occur before auto-heal |

Useful for diagnosing stuck readings, tuning thresholds, and verifying self-healing.

---

# 📝 Example Lovelace Card

```yaml
type: entities
title: Cleaned ZEN15 Sensors
entities:
  - sensor.fridge_energy_filtered
  - sensor.dishwasher_energy_filtered
  - sensor.furnace_energy_filtered
  - sensor.washing_machine_energy_filtered
```

---

# 🐛 Troubleshooting

### Filtered sensor stuck at one value?
Check attributes:

- `last_delta_kwh` might be huge  
- `reject_run_count` increments each update  

Once `reject_run_count == reject_run_limit`, the sensor will auto-heal.

### Device missing from Options?
Ensure the ZEN15 shows in:
**Integrations → ZWave**  
Manufacturer must be `"ZOOZ"` and model must include `"ZEN15"`.

### Need to force a reset?
Use:

```yaml
service: sensor.reset_filtered
```
