"""Room sensor (0x0A) and Online/DCM ACK (0x0F) emulation.

Pure Python: no Home Assistant, no I/O. Methods return frames or None. The caller
decides whether a frame is transmitted and passes `transmit` to say whether
transmission is currently released. Constants and behaviour follow
ryckema/Thermia_itec, "Write (Beta)/iTec Eco" (room sensor profile and 0f_ack profile).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

from .const import ACK_TX_PRE_DELAY_S, ROOM_TX_PRE_DELAY_S
from .modbus_rtu import append_crc

ROOM_SLAVE = 0x0A
ACK_SLAVE = 0x0F

POLL_READ_START = 0xB3B0
POLL_WRITE_START = 0xB3C4
POLL_COUNT = 3
SETPOINT_ADDR = 0xB3C5       # controller confirms the room setpoint here
TOPUP_STATUS_ADDR = 0xB3C6   # 2 = hot-water top-up active

ACK_IDLE_START = 0x0708
ACK_IDLE_COUNT = 6

TEMP_MIN, TEMP_MAX = 5.0, 35.0
SETPOINT_MIN, SETPOINT_MAX = 10, 30
DEFAULT_TARGET = 20
MAX_SETPOINT_RETRIES = 5
OWN_RESPONSE_WINDOW_S = 0.5   # a 0x0A response this soon after our own is our echo
OWN_ECHO_WINDOW_0F_S = 0.15   # same for 0x0F

# Idle reply to FC03 0x0708 x6, as captured in the repo (12 data bytes, CRC 9D 76).
IDLE_0708_REPLY = append_crc(bytes([ACK_SLAVE, 0x03, 0x0C]) + bytes(11) + bytes([0x06]))


def tx_pre_delay(frame: bytes) -> float:
    """Repo timing before a reply: 3.8 ms for the room sensor (0x0A), 5 ms for 0x0F."""
    return ROOM_TX_PRE_DELAY_S if frame[0] == ROOM_SLAVE else ACK_TX_PRE_DELAY_S


class RoomStatus(str, Enum):
    DISABLED = "DISABLED"
    WAITING = "WAITING"
    ACTIVE = "ACTIVE"
    TIMEOUT = "TIMEOUT"
    BLOCKED = "BLOCKED_BY_EXTERNAL_SENSOR"


class AckStatus(str, Enum):
    DISABLED = "DISABLED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED_BY_EXTERNAL_RESPONDER"


# ---------------------------------------------------------------------------
# Frame recognition and builders
# ---------------------------------------------------------------------------

def is_room_poll(frame: bytes) -> bool:
    """Controller poll of slave 0x0A: FC17, read 0xB3B0 x3, write 0xB3C4 x3."""
    if len(frame) != 19 or frame[0] != ROOM_SLAVE or frame[1] != 0x17:
        return False
    rs, rc, ws, wc = struct.unpack(">HHHH", frame[2:10])
    return (rs, rc, ws, wc) == (POLL_READ_START, POLL_COUNT, POLL_WRITE_START, POLL_COUNT)


def is_room_response(frame: bytes) -> bool:
    return len(frame) == 11 and frame[0] == ROOM_SLAVE and frame[1] == 0x17 and frame[2] == 0x06


def parse_fc10_request(frame: bytes) -> tuple[int, int] | None:
    """(start, count) of a controller FC10 write, or None."""
    if len(frame) < 9 or frame[1] != 0x10 or len(frame) != 9 + frame[6]:
        return None
    start, count = struct.unpack(">HH", frame[2:6])
    return (start, count) if frame[6] == count * 2 else None


def parse_fc03_request(frame: bytes) -> tuple[int, int] | None:
    """(start, count) of an 8-byte FC03 request, or None."""
    if len(frame) != 8 or frame[1] != 0x03:
        return None
    return struct.unpack(">HH", frame[2:6])


def room_poll_response(temperature: float, setpoint_request: int, topup: int) -> bytes:
    """11-byte FC17 reply: 0A 17 06 <temp*10> <setpoint request> <top-up trigger> CRC."""
    raw = int(round(temperature * 10))
    return append_crc(bytes([ROOM_SLAVE, 0x17, 0x06]) + struct.pack(">hhh", raw, setpoint_request, topup))


def ack_fc10_response(start: int, count: int) -> bytes:
    """8-byte FC10 write acknowledgement: 0F 10 <start> <count> CRC."""
    return append_crc(bytes([ACK_SLAVE, 0x10]) + struct.pack(">HH", start, count))


# ---------------------------------------------------------------------------
# Room sensor emulation
# ---------------------------------------------------------------------------

@dataclass
class RoomSensorEmulator:
    watchdog_seconds: float = 30 * 60
    enabled: bool = False
    temperature: float | None = None
    temperature_at: float | None = None
    target: int = DEFAULT_TARGET        # setpoint requested in Home Assistant
    setpoint_request: int = 0           # pending request sent on the bus (0 = none)
    setpoint_retries: int = 0
    bus_setpoint: int | None = None     # value the controller confirms on 0xB3C5
    topup_pending: bool = False
    topup_active: bool = False
    responses_sent: int = 0
    last_tx: float | None = None
    peer_detected: bool = False

    def status(self, now: float) -> RoomStatus:
        if self.peer_detected:
            return RoomStatus.BLOCKED
        if not self.enabled:
            return RoomStatus.DISABLED
        if self.temperature is None or self.temperature_at is None:
            return RoomStatus.WAITING
        if self.watchdog_seconds > 0 and now - self.temperature_at > self.watchdog_seconds:
            return RoomStatus.TIMEOUT
        return RoomStatus.ACTIVE

    def set_temperature(self, value: float, now: float) -> bool:
        """Accept a room temperature inside the repo's plausibility range."""
        if not TEMP_MIN <= value <= TEMP_MAX:
            return False
        self.temperature = value
        self.temperature_at = now
        return True

    def clear_temperature(self) -> None:
        self.temperature = None
        self.temperature_at = None

    def request_setpoint(self, value: float) -> int:
        target = max(SETPOINT_MIN, min(SETPOINT_MAX, int(round(value))))
        self.target = target
        if self.bus_setpoint == target:
            self.setpoint_request = 0
        else:
            self.setpoint_request = target
        self.setpoint_retries = 0
        return target

    def request_topup(self) -> None:
        self.topup_pending = True

    def on_controller_poll(self, now: float, transmit: bool) -> bytes | None:
        """Answer one controller poll. Returns the frame, or None if no answer is due."""
        if not transmit or self.status(now) is not RoomStatus.ACTIVE:
            return None
        req = 0
        if self.setpoint_request > 0:
            req = self.setpoint_request
            self.setpoint_retries += 1
            if self.setpoint_retries > MAX_SETPOINT_RETRIES:
                self.setpoint_request = 0
                self.setpoint_retries = 0
        topup = 0
        if self.topup_pending:
            topup = 1  # one-shot: sent in exactly one cycle
            self.topup_pending = False
        self.last_tx = now
        self.responses_sent += 1
        return room_poll_response(self.temperature, req, topup)

    def on_bus_room_response(self, now: float) -> None:
        """A 0x0A response was seen on the bus. Not our own echo means a physical sensor."""
        if self.last_tx is None or now - self.last_tx > OWN_RESPONSE_WINDOW_S:
            self.peer_detected = True

    def on_bus_setpoint(self, value: int) -> None:
        self.bus_setpoint = value
        if self.setpoint_request > 0:
            if value == self.setpoint_request:
                self.setpoint_request = 0
                self.setpoint_retries = 0
        elif SETPOINT_MIN <= value <= SETPOINT_MAX:
            self.target = value  # panel dial changed: follow the controller

    def on_bus_topup(self, value: int) -> None:
        self.topup_active = value == 2


# ---------------------------------------------------------------------------
# 0x0F Online/DCM ACK emulation
# ---------------------------------------------------------------------------

@dataclass
class AckEmulator:
    enabled: bool = False
    peer_detected: bool = False
    last_tx: float | None = None
    acks_sent: int = 0
    idle_replies_sent: int = 0

    def status(self) -> AckStatus:
        if self.peer_detected:
            return AckStatus.BLOCKED
        return AckStatus.ACTIVE if self.enabled else AckStatus.DISABLED

    def observe_frame(self, frame: bytes, now: float) -> None:
        """Any 0x0F response that is not our own echo means an external responder."""
        if len(frame) < 2 or frame[0] != ACK_SLAVE or self.peer_detected:
            return
        if self.last_tx is not None and now - self.last_tx < OWN_ECHO_WINDOW_0F_S:
            return
        fc10_ack = frame[1] == 0x10 and len(frame) == 8
        fc03_reply = frame[1] == 0x03 and len(frame) != 8
        if fc10_ack or fc03_reply:
            self.peer_detected = True

    def on_fc10_request(self, slave: int, start: int, count: int, now: float,
                        transmit: bool) -> bytes | None:
        if slave != ACK_SLAVE or not transmit or self.status() is not AckStatus.ACTIVE:
            return None
        self.last_tx = now
        self.acks_sent += 1
        return ack_fc10_response(start, count)

    def on_fc03_request(self, slave: int, start: int, count: int, now: float,
                        transmit: bool) -> bytes | None:
        if (slave != ACK_SLAVE or start != ACK_IDLE_START or count != ACK_IDLE_COUNT
                or not transmit or self.status() is not AckStatus.ACTIVE):
            return None
        self.last_tx = now
        self.idle_replies_sent += 1
        return IDLE_0708_REPLY
