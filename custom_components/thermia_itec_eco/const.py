"""Constants for the Thermia iTec Eco integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "thermia_itec_eco"
CONF_PORT: Final = "port"

# Serial parameters from the specification: 9600 baud, 8 data bits, even parity, 1 stop bit.
BAUDRATE: Final = 9600

READ_TIMEOUT: Final = 0.05        # seconds per read call in the reader thread
IDLE_FLUSH_SECONDS: Final = 0.2   # silence after which a partial frame is discarded
RECONNECT_SECONDS: Final = 30     # retry interval if the port is unavailable

# Options (config entry)
CONF_ROOM_SENSOR: Final = "room_sensor_entity"
CONF_WATCHDOG_MINUTES: Final = "watchdog_minutes"
DEFAULT_WATCHDOG_MINUTES: Final = 30

# Transmit timing (seconds), taken from the repo's ESPHome profiles.
# The FTDI chip switches the transceiver direction itself (TXDEN), so no software direction control is needed.
ROOM_TX_PRE_DELAY_S: Final = 0.0038  # 0x0A response: wait 3800 us before sending
ACK_TX_PRE_DELAY_S: Final = 0.0050   # 0x0F ACK and 0x0708 reply: wait 5000 us before sending
TX_HOLD_S: Final = 0.0012            # hold after flush until the last stop bit has left the wire

STATUS_STARTING: Final = "STARTING"
STATUS_PASSIVE: Final = "PASSIVE_LISTENING"
STATUS_UNAVAILABLE: Final = "TRANSPORT_UNAVAILABLE"
STATUS_STOPPED: Final = "STOPPED"
