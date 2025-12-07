DOMAIN = "zen15_cleaner"

# Global forward / backward thresholds
CONF_FORWARD_THRESHOLD_KWH = "forward_threshold_kwh"
CONF_BACKWARD_THRESHOLD_KWH = "backward_threshold_kwh"

# Per-device forward overrides (text field, one "Name = value" per line)
CONF_FORWARD_OVERRIDES = "forward_overrides"

DEFAULT_FORWARD_THRESHOLD_KWH = 10.0   # max allowed increase per update
DEFAULT_BACKWARD_THRESHOLD_KWH = 0.0   # reserved; we still block all decreases
