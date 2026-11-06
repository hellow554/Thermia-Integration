"""Pure Modbus RTU helpers for passive monitoring.

No Home Assistant imports, so this module is unit-testable on its own.
Nothing here writes to the bus.

Values are keyed by (slave, space, address):
    space "r": value seen in a read response (FC03, FC04, FC17 read part)
    space "w": value seen in a controller write (FC10, FC17 write part)
Read and write values can share an address on the same slave (for example
0x1E address 0x0001 is the condenser outlet when read and the commanded
target when written), so they must be kept apart.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

FC_READ_HOLDING = 0x03
FC_READ_INPUT = 0x04
FC_WRITE_MULTIPLE = 0x10
FC_READ_WRITE_MULTIPLE = 0x17

READ = "r"
WRITE = "w"

STALE_SECONDS = 1800  # default watchdog value from the specification


def crc16(data: bytes) -> int:
    """Modbus CRC16 (polynomial 0xA001, initial value 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 0x0001 else crc >> 1
    return crc


def append_crc(payload: bytes) -> bytes:
    """Return payload with its CRC16 appended, low byte first."""
    crc = crc16(payload)
    return payload + bytes((crc & 0xFF, crc >> 8))


def has_valid_crc(frame: bytes) -> bool:
    if len(frame) < 4:
        return False
    received = frame[-2] | (frame[-1] << 8)
    return crc16(frame[:-2]) == received


def candidate_lengths(buf: bytes) -> list[int] | None:
    """Possible total lengths of a frame that starts at buf[0].

    Returns None while the header needed to decide is not yet received.
    Returns an empty list for unknown function codes, which makes the caller resync.
    Request and response lengths are both listed, because passive capture cannot
    tell the direction from the bytes alone. The CRC decides.
    """
    if len(buf) < 2:
        return None
    fc = buf[1]
    if fc & 0x80:  # exception response
        return [5]
    if fc in (FC_READ_HOLDING, FC_READ_INPUT):  # request 8, response 5 + byte count
        if len(buf) < 3:
            return None
        return [8, 5 + buf[2]]
    if fc == FC_WRITE_MULTIPLE:  # request 9 + byte count, response 8
        if len(buf) < 7:
            return None
        return [8, 9 + buf[6]]
    if fc == FC_READ_WRITE_MULTIPLE:  # request 13 + byte count, response 5 + byte count
        if len(buf) < 3:
            return None
        if len(buf) < 11:
            # Response length is known from buf[2] already; the request form needs buf[10].
            return [5 + buf[2]]
        return [5 + buf[2], 13 + buf[10]]
    return []


class FrameParser:
    """Extracts CRC-valid RTU frames from an arbitrary byte stream.

    Works across any chunk boundaries. Bytes that do not form a valid frame
    are discarded one at a time until the stream resynchronises.
    """

    MAX_BUFFER = 512

    def __init__(self) -> None:
        self._buf = bytearray()
        self.frames_ok = 0
        self.resync_bytes = 0

    def feed(self, data: bytes) -> list[bytes]:
        self._buf.extend(data)
        frames: list[bytes] = []
        while self._buf:
            cands = candidate_lengths(bytes(self._buf))
            if cands is None:
                break  # header incomplete, wait for more bytes
            for length in cands:
                if len(self._buf) >= length and has_valid_crc(bytes(self._buf[:length])):
                    frames.append(bytes(self._buf[:length]))
                    del self._buf[:length]
                    self.frames_ok += 1
                    break
            else:
                if all(len(self._buf) >= n for n in cands):
                    del self._buf[0]  # nothing valid here, resync by one byte
                    self.resync_bytes += 1
                else:
                    break  # a longer candidate may still complete
        if len(self._buf) > self.MAX_BUFFER:
            drop = len(self._buf) - self.MAX_BUFFER
            del self._buf[:drop]
            self.resync_bytes += drop
        return frames

    def flush(self) -> None:
        """Discard a partial frame after a silence on the bus."""
        if self._buf:
            self.resync_bytes += len(self._buf)
            self._buf.clear()


@dataclass(frozen=True)
class RegisterReading:
    value: int        # signed 16-bit raw value as received
    slave: int        # address byte of the slave involved
    timestamp: float  # time.monotonic() at reception


class PassiveDecoder:
    """Pairs observed read requests with their responses and stores register values."""

    def __init__(self) -> None:
        self._pending: dict[tuple[int, int], tuple[int, int]] = {}  # (slave, fc) -> (start, count)
        self.registers: dict[tuple[int, str, int], RegisterReading] = {}
        self.unmatched_responses = 0

    def handle_frame(self, frame: bytes, now: float) -> None:
        slave, fc = frame[0], frame[1]
        if fc & 0x80:
            self._pending.pop((slave, fc & 0x7F), None)
            return
        if fc in (FC_READ_HOLDING, FC_READ_INPUT):
            if len(frame) == 8:  # request
                self._pending[(slave, fc)] = struct.unpack(">HH", frame[2:6])
            elif len(frame) == 5 + frame[2]:  # response
                self._read_response(slave, fc, frame, now)
            return
        if fc == FC_WRITE_MULTIPLE:
            if len(frame) >= 9 and len(frame) == 9 + frame[6]:
                start, count = struct.unpack(">HH", frame[2:6])
                if frame[6] == count * 2:
                    self._store(slave, WRITE, start, frame[7:7 + frame[6]], now)
            return
        if fc == FC_READ_WRITE_MULTIPLE:
            if len(frame) >= 11 and len(frame) == 13 + frame[10]:  # request
                rstart, rcount, wstart, wcount = struct.unpack(">HHHH", frame[2:10])
                bc = frame[10]
                if bc == wcount * 2:
                    self._store(slave, WRITE, wstart, frame[11:11 + bc], now)
                self._pending[(slave, fc)] = (rstart, rcount)
            elif len(frame) == 5 + frame[2]:  # response
                self._read_response(slave, fc, frame, now)
            return

    def _read_response(self, slave: int, fc: int, frame: bytes, now: float) -> None:
        pending = self._pending.pop((slave, fc), None)
        byte_count = frame[2]
        if pending is None or byte_count != pending[1] * 2:
            self.unmatched_responses += 1
            return
        self._store(slave, READ, pending[0], frame[3:3 + byte_count], now)

    def _store(self, slave: int, space: str, start: int, data: bytes, now: float) -> None:
        for i in range(len(data) // 2):
            (value,) = struct.unpack(">h", data[2 * i : 2 * i + 2])
            self.registers[(slave, space, start + i)] = RegisterReading(value, slave, now)

    def fresh(self, slave: int, space: str, address: int, now: float,
              max_age: float | None = None) -> int | None:
        """Latest raw value of a register, or None if never seen.

        Like the repo, values are kept until the controller reports a new one.
        Pass max_age to expire them explicitly.
        """
        reading = self.registers.get((slave, space, address))
        if reading is None:
            return None
        if max_age is not None and now - reading.timestamp > max_age:
            return None
        return reading.value
