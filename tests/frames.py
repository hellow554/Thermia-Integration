"""Frame builders for tests. Frames are built exactly as a Modbus RTU bus would carry them."""
import struct

import _loader  # noqa: F401
from thermia_pure.modbus_rtu import append_crc


def pack(values):
    return b"".join(struct.pack(">h", v) for v in values)


def read_request(slave, fc, start, count):
    return append_crc(bytes([slave, fc]) + struct.pack(">HH", start, count))


def read_response(slave, fc, values):
    data = pack(values)
    return append_crc(bytes([slave, fc, len(data)]) + data)


def fc17_request(slave, read_start, read_count, write_start, write_values):
    wdata = pack(write_values)
    return append_crc(
        bytes([slave, 0x17])
        + struct.pack(">HHHH", read_start, read_count, write_start, len(write_values))
        + bytes([len(wdata)])
        + wdata
    )


def fc10_request(slave, start, values):
    data = pack(values)
    return append_crc(bytes([slave, 0x10]) + struct.pack(">HHB", start, len(values), len(data)) + data)
