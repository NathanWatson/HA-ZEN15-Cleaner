
# 🔌 ZEN15/ZEN04 Cleaner – A Home Assistant Spike‑Filtering, Virtual Counter & Self‑Healing Integration

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

**ZEN15 Cleaner** is a Home Assistant integration that fixes noisy, spike‑prone kWh readings from **Zooz ZEN15 Power Switches** and **ZEN04 Smart Plugs**, replacing them with a **clean, stable, virtual kWh counter** that is safe for the **Home Assistant Energy Dashboard**.

Older ZEN15 and ZEN04 units often report huge bogus jumps—sometimes thousands of watts or kWh—in a single update. These bad readings pollute energy statistics and produce ridiculous spikes.

The **new v0.8.0 engine** creates a virtual `*_energy_filtered` sensor that:

- Uses a **zero‑based virtual counter**  
- Adds only *valid, positive* measured deltas  
- Filters out spikes and rollovers  
- Never adopts bad raw readings  
- Automatically self‑heals around ZEN15 resets or shifts  
- Is fully compatible with the Energy Dashboard  
- Offers per‑device thresholds  
- Includes a built‑in **Reset Energy Filtered** button  

---

# 🚀 Features

### ✔ Zero‑based Virtual Energy Counter  
Never mirrors the ZEN15’s lifetime kWh value.  
Only adds clean, valid usage increments.

### ✔ Spike & Rollover Filtering  
Rejects:  
- Massive positive jumps  
- Large negative jumps  
- Temporary glitches  
- Small negative deltas (treated as zero usage)

### ✔ Self‑Healing  
If the plug permanently shifts (e.g., firmware update, Z‑Wave ID reset), the integration recognizes the pattern and stabilizes automatically.

### ✔ Reset Button  
Each device gets:

```
Reset Energy Filtered
```

Useful for fresh starts, meter changes, or Energy graph resets.

### ✔ No More Duplicate Devices  
v0.8.0 includes automatic cleanup of:  
- `*_energy_filtered_2`, `_3`, `_4` entities  
- orphaned ZEN15 Cleaner devices  

### ✔ Energy Dashboard Safe  
The output sensor always increases monotonically and never spikes.

---

# 📦 Installation

### Via HACS (recommended)

1. Open **HACS → Integrations → Custom repositories**
2. Add: `https://github.com/NathanWatson/HA-ZEN15-Cleaner`
3. Category: **Integration**
4. Install and restart Home Assistant.

### Manual Installation

Copy this folder:

```
custom_components/zen15_cleaner/
```

Then restart Home Assistant.

---

# 🔧 Configuration

Go to:

**Settings → Devices & Services → ZEN15 Cleaner → Configure**

### Available Options

#### **Global Forward Threshold (kWh)**
Max allowed increase per update before considered a spike.

#### **Global Backward Threshold (kWh)**
Displayed for diagnostics; filtered energy never decreases.

#### **Per‑Device Threshold Overrides**
Each discovered ZEN15 shows up with a friendly device name.

Example:

> Dishwasher ZEN15  
> Fridge ZEN15  
> Furnace ZEN15

You may override forward spike thresholds individually.

---

# 🧠 How the Virtual Counter Works

Let:

- `raw` = Zooz kWh reading  
- `virt` = virtual filtered reading  
- `last_raw` = previous raw reading  
- `delta = raw - last_raw`  

### 1. First raw reading  
The integration stores it but **does not** add anything to the virtual total.

### 2. Valid Positive Deltas  
If `0 < delta ≤ threshold` → added to virtual total.

### 3. Negative Deltas  
Ignored, unless part of a detected ZEN15 meter reset.

### 4. Spikes  
If `delta > forward_threshold` → ignored, but logged in attributes.

### 5. Self‑Healing  
If Home Assistant sees many consecutive "spikes":

```
reject_run_count >= reject_run_limit
```

→ The new raw reading becomes the new baseline (but does NOT jump virtual energy).

### 6. Meter Reset Detection  
If the ZEN15 drops near zero and stays there, the virtual counter resets its baseline silently.

---

# 🧪 Reset Function

Call the built‑in service:

```yaml
service: zen15_cleaner.reset_filtered
target:
  entity_id: sensor.<device>_energy_filtered
```

Equivalent to pressing the reset button under the device card.

This sets:

- `virtual_total = 0`
- next delta starts fresh from the current ZEN15 raw reading

---

# 📊 Sensor Attributes

| Attribute | Meaning |
|----------|---------|
| `raw_entity_id` | Source ZEN15 kWh sensor |
| `virtual_total_kwh` | Current virtual usage total |
| `last_raw_value` | Last raw reading observed |
| `last_delta_kwh` | Difference from last raw reading |
| `reset_detected` | True if a rollover/reset occurred |
| `spike_ignored` | True if this reading was a spike |
| `forward_threshold_kwh` | Allowed positive jump |
| `backward_threshold_kwh` | Allowed negative jump (usually 0) |
| `reject_run_count` | Spike rejections since last heal |
| `reject_run_limit` | Rejections required before adopting a new baseline |

---

# 🧭 Example Lovelace Card

```yaml
type: entities
title: Cleaned ZEN15 Sensors
entities:
  - sensor.fridge_energy_filtered
  - sensor.dishwasher_energy_filtered
  - sensor.furnace_energy_filtered
```

---

# 🔄 Migration: v0.7.6 → v0.8.0

### 🆕 New Virtual Counter  
The old behavior mirrored the ZEN15’s lifetime kWh and filtered spikes.  
The new version **no longer follows raw values at all**.

### 🧹 Automatic Cleanup  
v0.8.0 auto‑removes all:  
- stale filtered sensors  
- `_2`, `_3`, `_4` duplicates  
- orphan devices in the registry  

### 🔘 Buttons Added  
Each ZEN15 now gets a reset button paired with the filtered sensor.

### 🤝 Energy Dashboard Safe  
No more megawatt spikes or broken graphs.

---

# 🐛 Troubleshooting

### Filtered sensor not increasing?
Check attributes:  
- `spike_ignored: true`  
- `last_delta_kwh` huge  
→ It's filtering correctly.

### Virtual counter too low?
Press **Reset Energy Filtered** to restart at zero.

### Device missing?
Ensure the ZEN15 appears under Z‑Wave with manufacturer `"Zooz"` and model containing `"ZEN15"`.

---

# ❤️ Contributing

Pull requests welcome!  
https://github.com/NathanWatson/HA-ZEN15-Cleaner
