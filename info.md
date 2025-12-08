## ZEN15 Cleaner

<p align="center">
  <img src="https://raw.githubusercontent.com/NathanWatson/HA-ZEN15-Cleaner/main/icons/logo_dark.png" alt="ZEN15 Cleaner Logo" width="600">
</p>

<p align="center">
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS Custom"></a>
  <img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FNathanWatson%2FHA-ZEN15-Cleaner%2Frefs%2Fheads%2Fmain%2Fcustom_components%2Fzen15_cleaner%2Fmanifest.json&query=version&label=Manifest" alt="Manifest badge">
  <a href="https://github.com/NathanWatson/HA-ZEN15-Cleaner/releases"><img src="https://img.shields.io/github/v/release/NathanWatson/HA-ZEN15-Cleaner?logo=github&color=8A2BE2" alt="Release Badge"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.12%2B-brightgreen.svg" alt="HA 2024.12+">
</p>

## ZEN15 Cleaner

**ZEN15 Cleaner** is a custom integration for Home Assistant that cleans up energy readings from Zooz ZEN15 smart plugs by filtering out unrealistic kWh spikes.

### Highlights

- Smooth, reliable kWh readings for the Energy Dashboard  
- Per-device spike thresholds and global defaults  
- Options UI for tuning thresholds after install  
- `sensor.reset_filtered` service to resync filtered values  
- Extra attributes to help diagnose behavior  

### Installation

1. Copy `custom_components/zen15_cleaner` into your Home Assistant config.  
2. Restart Home Assistant.  
3. Add the **ZEN15 Cleaner** integration from **Settings → Devices & Services**.

For full documentation and examples, see the main `README.md` in this repository.
