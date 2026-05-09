DOMAIN = "marstek_venus"
MANUFACTURER = "Marstek"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TIMEOUT = "timeout"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 30000
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10  # Bat.GetStatus braucht ~8-9 s auf Firmware 148

# Persisted option keys for write-only controls (no GET in API)
OPT_DOD = "dod"
OPT_LED = "led"

MODES = ["Auto", "AI", "Manual", "Passive", "UPS"]
