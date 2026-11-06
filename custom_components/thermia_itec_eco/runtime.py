"""Runtime for one config entry: transport, parser, passive decoder and emulators."""
from __future__ import annotations

import logging
import time
from collections.abc import Mapping

import serial

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import (
    CONF_ROOM_SENSOR,
    CONF_WATCHDOG_MINUTES,
    DEFAULT_WATCHDOG_MINUTES,
    DOMAIN,
    RECONNECT_SECONDS,
    STATUS_PASSIVE,
    STATUS_STARTING,
    STATUS_STOPPED,
    STATUS_UNAVAILABLE,
)
from .emulation import (
    ACK_SLAVE,
    ROOM_SLAVE,
    SETPOINT_ADDR,
    TOPUP_STATUS_ADDR,
    AckEmulator,
    RoomSensorEmulator,
    RoomStatus,
    is_room_poll,
    is_room_response,
    parse_fc03_request,
    parse_fc10_request,
    tx_pre_delay,
)
from .modbus_rtu import WRITE, FrameParser, PassiveDecoder
from .transport import SerialTransport, TransportClosedError

_LOGGER = logging.getLogger(__name__)


class ThermiaRuntime:
    def __init__(self, hass: HomeAssistant, entry_id: str, port: str, options: Mapping) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.port = port
        self.status = STATUS_STARTING
        self.parser = FrameParser()
        self.decoder = PassiveDecoder()
        self.room = RoomSensorEmulator(
            watchdog_seconds=float(options.get(CONF_WATCHDOG_MINUTES, DEFAULT_WATCHDOG_MINUTES)) * 60
        )
        # Repo: the 0x0F ACK switch starts ON (RESTORE_DEFAULT_ON). It only sends once transmit is released.
        self.ack = AckEmulator(enabled=True)
        self.room_source: str | None = options.get(CONF_ROOM_SENSOR) or None
        self._transport = SerialTransport(
            hass.loop,
            port,
            on_data=self._on_data,
            on_idle=self._on_idle,
            on_error=self._on_error,
        )
        self._reconnect_unsub = None
        self._source_unsubs: list = []
        self._stopping = False

    # ------------------------------------------------------------------ state

    @property
    def signal(self) -> str:
        return f"{DOMAIN}_update_{self.entry_id}"

    def room_status_text(self) -> str:
        return self.room.status(time.monotonic()).value

    def ack_status_text(self) -> str:
        return self.ack.status().value

    @callback
    def notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def _set_status(self, status: str) -> None:
        self.status = status
        self.notify()

    # --------------------------------------------------------------- commands

    async def async_set_room_emulation(self, on: bool) -> None:
        if on and self.room.peer_detected:
            raise HomeAssistantError("Ein externer Raumsensor antwortet bereits auf dem Bus.")
        self.room.enabled = on
        self.notify()

    async def async_set_ack_emulation(self, on: bool) -> None:
        if on and self.ack.peer_detected:
            raise HomeAssistantError("Ein externer 0x0F-Teilnehmer antwortet bereits auf dem Bus.")
        self.ack.enabled = on
        self.notify()

    async def async_request_topup(self) -> None:
        # Repo: the trigger is staged and sent in the next 0x0A response, if the emulation is active.
        self.room.request_topup()
        self.notify()

    async def async_set_target(self, value: float) -> None:
        self.room.request_setpoint(value)
        self.notify()

    # ------------------------------------------------------------- lifecycle

    async def async_start(self) -> None:
        self._stopping = False
        await self._async_open()
        await self._async_track_room_source()

    async def _async_open(self, _now=None) -> None:
        self._reconnect_unsub = None
        if self._stopping:
            return
        try:
            await self.hass.async_add_executor_job(self._transport.open)
        except (serial.SerialException, OSError) as err:
            _LOGGER.warning(
                "Serieller Port %s nicht verfügbar (%s), neuer Versuch in %s s",
                self.port, err, RECONNECT_SECONDS,
            )
            self._set_status(STATUS_UNAVAILABLE)
            self._schedule_reconnect()
            return
        _LOGGER.info("Verbindung zu %s hergestellt", self.port)
        self._set_status(STATUS_PASSIVE)

    def _schedule_reconnect(self) -> None:
        if self._reconnect_unsub is None and not self._stopping:
            self._reconnect_unsub = async_call_later(self.hass, RECONNECT_SECONDS, self._async_open)

    async def async_stop(self) -> None:
        self._stopping = True
        for unsub in self._source_unsubs:
            unsub()
        self._source_unsubs = []
        if self._reconnect_unsub is not None:
            self._reconnect_unsub()
            self._reconnect_unsub = None
        self.room.enabled = False
        self.ack.enabled = False
        await self.hass.async_add_executor_job(self._transport.close)
        self._set_status(STATUS_STOPPED)

    # ------------------------------------------------------ room temperature

    async def _async_track_room_source(self) -> None:
        for unsub in self._source_unsubs:
            unsub()
        self._source_unsubs = []
        if not self.room_source:
            self.room.clear_temperature()
            return
        self._source_unsubs.append(
            async_track_state_change_event(self.hass, [self.room_source], self._source_changed)
        )
        self._apply_source(self.hass.states.get(self.room_source))

    @callback
    def _source_changed(self, event: Event) -> None:
        self._apply_source(event.data.get("new_state"))
        self.notify()

    @callback
    def _apply_source(self, state: State | None) -> None:
        value: float | None = None
        if state is not None and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                value = float(state.state)
            except ValueError:
                value = None
        if value is None or not self.room.set_temperature(value, time.monotonic()):
            self.room.clear_temperature()

    # ---------------------------------------------------------------- bus rx

    @callback
    def _on_data(self, data: bytes) -> None:
        now = time.monotonic()
        for frame in self.parser.feed(data):
            self.decoder.handle_frame(frame, now)
            self._handle_frame(frame, now)
        self._sync_bus_values(now)
        self.notify()

    @callback
    def _on_idle(self) -> None:
        self.parser.flush()
        self.notify()

    @callback
    def _on_error(self, err: Exception) -> None:
        _LOGGER.warning("Lesefehler auf %s: %s", self.port, err)
        self.hass.async_create_task(self._async_handle_error())

    async def _async_handle_error(self) -> None:
        await self.hass.async_add_executor_job(self._transport.close)
        self._set_status(STATUS_UNAVAILABLE)
        self._schedule_reconnect()

    @callback
    def _handle_frame(self, frame: bytes, now: float) -> None:
        self.ack.observe_frame(frame, now)
        if frame[0] == ROOM_SLAVE and is_room_response(frame):
            self.room.on_bus_room_response(now)
        if is_room_poll(frame):
            self._transmit(self.room.on_controller_poll(now, transmit=True))
        if frame[0] == ACK_SLAVE:
            fc10 = parse_fc10_request(frame)
            if fc10 is not None:
                start, count = fc10
                self._transmit(self.ack.on_fc10_request(ACK_SLAVE, start, count, now, transmit=True))
            fc03 = parse_fc03_request(frame)
            if fc03 is not None:
                start, count = fc03
                self._transmit(self.ack.on_fc03_request(ACK_SLAVE, start, count, now, transmit=True))

    def _sync_bus_values(self, now: float) -> None:
        setpoint = self.decoder.fresh(ROOM_SLAVE, WRITE, SETPOINT_ADDR, now)
        if setpoint is not None:
            self.room.on_bus_setpoint(setpoint)
        topup = self.decoder.fresh(ROOM_SLAVE, WRITE, TOPUP_STATUS_ADDR, now)
        if topup is not None:
            self.room.on_bus_topup(topup)

    # ----------------------------------------------------------------- tx

    @callback
    def _transmit(self, frame: bytes | None) -> None:
        if frame is None:
            return
        self.hass.async_create_task(self._async_transmit(frame))

    async def _async_transmit(self, frame: bytes) -> None:
        try:
            await self.hass.async_add_executor_job(self._transport.write, frame, tx_pre_delay(frame))
        except (TransportClosedError, serial.SerialException, OSError) as err:
            _LOGGER.warning("Senden fehlgeschlagen: %s", err)
