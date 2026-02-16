# ZEN15 Cleaner – Changelog

## 0.8.4 - Added Zen04 Support

## 0.8.0 — Virtual Counter & Self-Healing Release

### Added
- New zero-based **virtual energy counter** per ZEN15 device.
- Automatic **self-healing** around ZEN15 resets and spikes.
- New **Reset Energy Filtered** button per ZEN15.
- Auto-cleanup of duplicate `_energy_filtered_2`, `_3`, `_4` sensors.
- Strict avoidance of wrapping filtered sensors to prevent infinite recursion.
- Stronger stability guarantees for Home Assistant Energy.

### Changed
- Filtered energy sensors no longer follow the ZEN15 lifetime kWh value.
- Internal state restored on restart for a persistent virtual counter.

### Removed
- Old spike-recovery adoption logic (no longer needed).
- Duplicate entity accumulation on reload.

## 0.7.6 and earlier
- Original threshold-based smoothing model.
- Could generate large jumps and Energy Dashboard spikes.
- Possible duplicate filtered sensors on reload.

## v0.7.0

- Added config flow and options flow with global thresholds.
- Added per-device forward threshold controls for each ZEN15.
- Implemented filtered energy sensor per device using kWh sensors.
- Added `sensor.reset_filtered` entity service to realign filtered sensors.
- Ensured compatibility with Energy Dashboard (energy / total_increasing).
