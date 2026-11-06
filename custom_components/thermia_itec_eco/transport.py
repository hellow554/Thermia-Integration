"""Serial transport for the RS485 bus.

The FTDI chip switches the transceiver direction automatically (TXDEN), so a
plain UART write transmits.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import serial

from .const import BAUDRATE, IDLE_FLUSH_SECONDS, READ_TIMEOUT, TX_HOLD_S

_LOGGER = logging.getLogger(__name__)
READ_CHUNK = 256


class TransportClosedError(RuntimeError):
    """The serial port is not open, so nothing can be transmitted."""


def open_serial(port: str, timeout: float) -> serial.Serial:
    """Open the port exclusively with 9600 8E1."""
    return serial.Serial(
        port=port,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_EVEN,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
        exclusive=True,
    )


class SerialTransport:
    """Reads the bus in a worker thread and hands the bytes to the event loop."""

    def __init__(
        self,
        loop,
        port: str,
        *,
        on_data: Callable[[bytes], None],
        on_idle: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._loop = loop
        self._port = port
        self._on_data = on_data
        self._on_idle = on_idle
        self._on_error = on_error
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._tx_lock = threading.Lock()

    def open(self) -> None:
        """Blocking. Call from an executor job."""
        ser = open_serial(self._port, READ_TIMEOUT)
        self._serial = ser
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._reader, args=(ser,), name="thermia_itec_eco_rx", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        """Blocking. Call from an executor job."""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        self._thread = None
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def _reader(self, ser: serial.Serial) -> None:
        last_data = time.monotonic()
        idle_reported = True
        while not self._stop.is_set():
            try:
                data = ser.read(READ_CHUNK)
            except (serial.SerialException, OSError) as err:
                if not self._stop.is_set():
                    self._loop.call_soon_threadsafe(self._on_error, err)
                return
            if data:
                last_data = time.monotonic()
                idle_reported = False
                self._loop.call_soon_threadsafe(self._on_data, data)
            elif not idle_reported and time.monotonic() - last_data >= IDLE_FLUSH_SECONDS:
                idle_reported = True
                self._loop.call_soon_threadsafe(self._on_idle)

    def write(self, payload: bytes, pre_delay: float) -> None:
        """Blocking. Call from an executor job."""
        ser = self._serial
        if ser is None:
            raise TransportClosedError("Der serielle Port ist nicht geöffnet.")
        with self._tx_lock:
            time.sleep(pre_delay)  # repo timing before the reply
            ser.write(payload)
            ser.flush()
            time.sleep(TX_HOLD_S)  # let the last stop bit leave the wire
