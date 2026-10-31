DOMAIN = "marstek_venus"
MANUFACTURER = "Marstek"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TIMEOUT = "timeout"
CONF_SCAN_INTERVAL = "scan_interval"
# "ver" from Marstek.GetDevice; missing on entries created before Rev 3.1 support
# and whenever the unicast discovery call failed.
CONF_VER = "ver"

# Controls are opt-in: by default the integration only reads from the device.
CONF_ENABLE_MODE = "enable_mode_control"
CONF_ENABLE_DOD = "enable_dod_control"
CONF_ENABLE_LED = "enable_led_control"

DEFAULT_PORT = 30000
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10  # Bat.GetStatus braucht ~8-9 s auf Firmware 148
DEFAULT_ENABLE_CONTROLS = False

# Option keys of versions that stored the last DOD / LED value in the config
# entry. Only read, as a display fallback; the current entities restore their
# state from Home Assistant instead.
LEGACY_OPT_DOD = "dod"
LEGACY_OPT_LED = "led"

# unique_id suffixes (<entry_id>_<suffix>) of the control entities
UID_MODE = "operating_mode"
UID_DOD = "dod"
UID_LED = "led"

# option key -> (platform domain, unique_id suffix)
CONTROLS: dict[str, tuple[str, str]] = {
    CONF_ENABLE_MODE: ("select", UID_MODE),
    CONF_ENABLE_DOD: ("number", UID_DOD),
    CONF_ENABLE_LED: ("switch", UID_LED),
}

# Modes that can be set with a single "enable" flag. Manual (needs time slots)
# and Passive (needs target power + countdown) are deliberately not offered:
# sending them without proper parameters misconfigures the device.
MODES = ["Auto", "AI", "UPS"]
