DOMAIN = "zen15_cleaner"

# Global thresholds
CONF_FORWARD_THRESHOLD_KWH = "forward_threshold_kwh"
CONF_BACKWARD_THRESHOLD_KWH = "backward_threshold_kwh"

# Per-device forward thresholds (stored as {device_id: kwh})
CONF_PER_DEVICE_THRESHOLDS = "per_device_forward_thresholds"

DEFAULT_FORWARD_THRESHOLD_KWH = 10.0   # Max allowed kWh increase per update
DEFAULT_BACKWARD_THRESHOLD_KWH = 0.0   # Currently informational; decreases always blocked

# Self-healing reject run limit
CONF_REJECT_RUN_LIMIT = "reject_run_limit"
DEFAULT_REJECT_RUN_LIMIT = 12  # 12 consecutive rejections before we "self-heal"
