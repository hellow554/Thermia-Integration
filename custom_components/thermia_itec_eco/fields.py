"""Field catalogue for the Thermia iTec Eco (passive, read-only).

Addresses, scaling and validity checks come from the iTec Eco room-sensor YAML
in the ryckema/Thermia_itec repository ("Write (Beta)/iTec Eco"). Each field
lists where its value is seen on the bus. Nothing here transmits.

Pure Python without Home Assistant imports, so it can be unit-tested directly.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .modbus_rtu import READ, WRITE, PassiveDecoder

Getter = Callable[[PassiveDecoder, float], Any]

SENTINEL_NONE = -1000  # the controller uses -1000 for "no value"

C = "°C"
TEMP = "temperature"
MEAS = "measurement"


@dataclass(frozen=True)
class FieldDef:
    key: str
    name_en: str
    name_de: str
    kind: str                 # "sensor" | "text" | "binary"
    getter: Getter
    source: str               # where the value is seen on the bus
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    diagnostic: bool = False  # entity category diagnostic, disabled by default
    candidate: bool = False   # not confirmed in the repo, disabled by default
    blocked: bool = False     # known conflict, entity is not created

    @property
    def enabled_default(self) -> bool:
        return not (self.diagnostic or self.candidate or self.blocked)


# ---------------------------------------------------------------------------
# Getter factories
# ---------------------------------------------------------------------------

def _raw(d: PassiveDecoder, now: float, slave: int, space: str, address: int) -> int | None:
    return d.fresh(slave, space, address, now)


def num(slave: int, space: str, address: int, *, div: float = 1.0, unsigned: bool = False,
        valid: tuple[float, float] | None = None, sentinel: int | None = None) -> Getter:
    def get(d: PassiveDecoder, now: float) -> float | None:
        raw = _raw(d, now, slave, space, address)
        if raw is None or (sentinel is not None and raw == sentinel):
            return None
        if unsigned:
            raw &= 0xFFFF
        value = raw / div
        if valid is not None and not (valid[0] <= value <= valid[1]):
            return None
        return value
    return get


def bit(slave: int, space: str, address: int, mask: int) -> Getter:
    def get(d: PassiveDecoder, now: float) -> bool | None:
        raw = _raw(d, now, slave, space, address)
        return None if raw is None else bool(raw & mask)
    return get


def nonzero(slave: int, space: str, address: int) -> Getter:
    def get(d: PassiveDecoder, now: float) -> bool | None:
        raw = _raw(d, now, slave, space, address)
        return None if raw is None else raw != 0
    return get


def switch(slave: int, space: str, address: int) -> Getter:
    """Boolean stored as 0 or 1. Other values are rejected."""
    def get(d: PassiveDecoder, now: float) -> bool | None:
        raw = _raw(d, now, slave, space, address)
        return bool(raw) if raw in (0, 1) else None
    return get


def word_equals(slave: int, space: str, address: int, value: int) -> Getter:
    def get(d: PassiveDecoder, now: float) -> bool | None:
        raw = _raw(d, now, slave, space, address)
        return None if raw is None else raw == value
    return get


def enum(slave: int, space: str, address: int, mapping: dict[int, str],
         default: str = "Unknown") -> Getter:
    def get(d: PassiveDecoder, now: float) -> str | None:
        raw = _raw(d, now, slave, space, address)
        if raw is None:
            return None
        return mapping.get(raw & 0xFFFF, default)
    return get


# ---------------------------------------------------------------------------
# Derived values (combine several registers)
# ---------------------------------------------------------------------------

_OUT_COND_IN = num(0x1E, READ, 0x0000, div=10, valid=(-50, 150))
_OUT_COND_OUT = num(0x1E, READ, 0x0001, div=10, valid=(-50, 150))
_OUT_COMP_FREQ = num(0x1E, READ, 0x000B, unsigned=True, valid=(0, 200))
_OUT_COMP_CURRENT = num(0x1E, READ, 0x000D, div=10, unsigned=True, valid=(0, 100))
_OUT_COMPRESSOR_RUNNING = bit(0x1E, READ, 0x0014, 0x01)
_OUT_CYCLE_REQUEST = nonzero(0x1E, WRITE, 0x0007)
_OUT_RUN_ENABLE = nonzero(0x1E, WRITE, 0x0008)
_CONTEXT_HEATING = bit(0x1E, READ, 0x0015, 0x0020)
_CONTEXT_DHW = bit(0x1E, READ, 0x0015, 0x0040)
_CONTEXT_COOLING = bit(0x1E, READ, 0x0015, 0x0080)


def _condenser_delta(d: PassiveDecoder, now: float) -> float | None:
    cin = _OUT_COND_IN(d, now)
    cout = _OUT_COND_OUT(d, now)
    if cin is None or cout is None:
        return None
    return round(cout - cin, 2)


def _compressor_starting(d: PassiveDecoder, now: float) -> bool | None:
    # Heuristic from the repo: frequency rises before the current register leaves 0 A.
    freq = _OUT_COMP_FREQ(d, now)
    current = _OUT_COMP_CURRENT(d, now)
    if freq is None or current is None:
        return None
    return freq > 0 and current < 0.2


def _operating_mode(d: PassiveDecoder, now: float) -> str | None:
    flags = _raw(d, now, 0x1E, READ, 0x0015)
    if flags is None:
        return None
    if flags & 0x0080:
        return "Cooling"
    if flags & 0x0040:
        return "DHW / high temperature"
    if flags & 0x0020:
        return "Heating"
    return "Unknown"


def _active(context: Getter) -> Getter:
    """Mode is active only with matching context, compressor running and both command bits set."""
    def get(d: PassiveDecoder, now: float) -> bool | None:
        ctx = context(d, now)
        if ctx is None:
            return None
        return bool(ctx and _OUT_COMPRESSOR_RUNNING(d, now)
                    and _OUT_CYCLE_REQUEST(d, now) and _OUT_RUN_ENABLE(d, now))
    return get


def _controller_context(d: PassiveDecoder, now: float) -> str | None:
    a80c = _raw(d, now, 0x02, WRITE, 0xA80C)
    if a80c is None:
        return None
    a80c &= 0xFFFF
    active = bool(a80c & 0x0040)
    dhw_valve = bool(a80c & 0x0001)
    if active and dhw_valve:
        return "Active / DHW valve"
    if active:
        return "Active / non-DHW"
    if dhw_valve:
        return "DHW valve / controller inactive"
    return "Controller inactive"


_SG_MODES = {
    (-1000, 224): "Normal (0-0)",
    (-1000, 232): "Blocked (1-0)",
    (1000, 224): "Enhanced (0-1)",
    (1000, 232): "Peak (1-1)",
}


def _sg_mode(d: PassiveDecoder, now: float) -> str | None:
    # Transitional combinations return None. The repo holds the last valid state here.
    a = _raw(d, now, 0x02, READ, 0xA7FD)
    b = _raw(d, now, 0x02, READ, 0xA803)
    if a is None or b is None:
        return None
    return _SG_MODES.get((a, b))


_UNIT_STATES = {
    16: "Idle",
    20: "Fan / autonomous sequence",
    24: "Water flow",
    25: "Water flow + compressor",
    28: "Water flow + fan",
    29: "Water flow + fan + compressor",
}

_MODE_REQUEST = {1: "Heating", 2: "DHW / high temperature", 3: "Cooling"}
_DHW_MODES = {0: "Comfort", 1: "Eco", 2: "Super-Eco"}
_OPERATION_MODES = {0: "Off", 1: "Auto", 2: "Compressor", 3: "Auxiliary Heater", 4: "Hot Water"}


# ---------------------------------------------------------------------------
# Field catalogue
# ---------------------------------------------------------------------------

FIELDS: tuple[FieldDef, ...] = (
    # --- Heating system: controller read block 0xA7F8..0xA806 on slave 0x02 ---
    FieldDef("supply_temperature", "Supply temperature", "Vorlauftemperatur", "sensor",
             num(0x02, READ, 0xA7F8, valid=(-50, 150), sentinel=SENTINEL_NONE),
             "0x02 read A7F8", unit=C, device_class=TEMP, state_class=MEAS),
    FieldDef("dhw_upper_temperature", "DHW upper temperature", "Warmwassertemperatur oben", "sensor",
             num(0x02, READ, 0xA7FB, valid=(0, 100), sentinel=SENTINEL_NONE),
             "0x02 read A7FB", unit=C, device_class=TEMP, state_class=MEAS),
    FieldDef("dhw_temperature", "DHW temperature", "Warmwassertemperatur", "sensor",
             num(0x02, READ, 0xA7FC, valid=(0, 100), sentinel=SENTINEL_NONE),
             "0x02 read A7FC (DHW main, repo)", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("outdoor_temperature", "Outdoor temperature", "Außentemperatur", "sensor",
             num(0x02, READ, 0xA802, valid=(-50, 70), sentinel=SENTINEL_NONE),
             "0x02 read A802", unit=C, device_class=TEMP, state_class=MEAS),
    FieldDef("sg_mode", "SG mode", "SG-Modus", "text", _sg_mode, "0x02 read A7FD + A803"),

    # --- Controller outputs written to slave 0x02 ---
    FieldDef("condenser_pump_speed", "Condenser pump speed", "Kondensatorpumpe Drehzahl", "sensor",
             num(0x02, WRITE, 0xA80F, unsigned=True), "0x02 write A80F",
             unit="%", state_class=MEAS),
    FieldDef("controller_output_bits_a80c", "Controller output bits A80C", "Reglerausgänge A80C",
             "sensor", num(0x02, WRITE, 0xA80C, unsigned=True), "0x02 write A80C", diagnostic=True),
    FieldDef("controller_context", "Controller context", "Reglerkontext", "text",
             _controller_context, "0x02 write A80C", diagnostic=True),
    FieldDef("controller_accessory_status_a80e", "Controller accessory status A80E",
             "Reglerzubehör A80E", "sensor", num(0x02, WRITE, 0xA80E, unsigned=True),
             "0x02 write A80E", diagnostic=True),
    FieldDef("controller_flag_a80c_0x10", "Controller flag A80C 0x10", "Reglerflag A80C 0x10",
             "binary", bit(0x02, WRITE, 0xA80C, 0x0010), "0x02 write A80C", diagnostic=True),
    FieldDef("controller_flag_a80c_0x20", "Controller flag A80C 0x20", "Reglerflag A80C 0x20",
             "binary", bit(0x02, WRITE, 0xA80C, 0x0020), "0x02 write A80C", diagnostic=True),
    FieldDef("controller_flag_a80e_0x08", "Controller flag A80E 0x08", "Reglerflag A80E 0x08",
             "binary", bit(0x02, WRITE, 0xA80E, 0x0008), "0x02 write A80E", diagnostic=True),
    FieldDef("controller_flag_a80e_0x20", "Controller flag A80E 0x20", "Reglerflag A80E 0x20",
             "binary", bit(0x02, WRITE, 0xA80E, 0x0020), "0x02 write A80E", diagnostic=True),

    # --- Room sensor slot 0x0A (controller traffic) ---
    FieldDef("room_temperature", "Room temperature", "Raumtemperatur", "sensor",
             num(0x0A, READ, 0xB3B0, div=10, valid=(-20, 60)), "0x0A read B3B0",
             unit=C, device_class=TEMP, state_class=MEAS),
    FieldDef("room_setpoint", "Room setpoint", "Raum-Sollwert", "sensor",
             num(0x0A, WRITE, 0xB3C5, valid=(5, 40)), "0x0A write B3C5 (confirmed setpoint)",
             unit=C, device_class=TEMP, state_class=MEAS),
    FieldDef("room_bus_outdoor_temperature", "Outdoor temperature (room bus)",
             "Außentemperatur (Raumbus)", "sensor", num(0x0A, WRITE, 0xB3C4),
             "0x0A write B3C4", unit=C, device_class=TEMP, state_class=MEAS, diagnostic=True),
    FieldDef("dhw_topup_active", "Hot water top-up active", "Warmwasser-Nachheizung aktiv", "binary",
             word_equals(0x0A, WRITE, 0xB3C6, 2), "0x0A write B3C6 == 2", device_class="running"),
    FieldDef("room_control_flag_b3c6", "Room sensor control flag B3C6",
             "Raumsensor-Steuerflag B3C6", "binary", nonzero(0x0A, WRITE, 0xB3C6),
             "0x0A write B3C6 != 0", diagnostic=True),

    # --- Outdoor unit: FC04 read block 0x0000..0x0015 on slave 0x1E ---
    FieldDef("condenser_in", "Condenser inlet", "Kondensator Eintritt", "sensor",
             _OUT_COND_IN, "0x1E read 0000", unit=C, device_class=TEMP, state_class=MEAS,
             candidate=True),
    FieldDef("condenser_out", "Condenser outlet", "Kondensator Austritt", "sensor",
             _OUT_COND_OUT, "0x1E read 0001", unit=C, device_class=TEMP, state_class=MEAS,
             candidate=True),
    FieldDef("condenser_delta", "Condenser delta T", "Kondensator Spreizung", "sensor",
             _condenser_delta, "0x1E read 0000 + 0001", unit=C, state_class=MEAS, candidate=True),
    FieldDef("refrigerant_temperature_1", "Refrigerant temperature 1", "Kältemittel Temperatur 1",
             "sensor", num(0x1E, READ, 0x0002, div=10, valid=(-80, 200)), "0x1E read 0002",
             unit=C, device_class=TEMP, state_class=MEAS, diagnostic=True),
    FieldDef("discharge_gas_temperature", "Discharge gas temperature", "Heißgastemperatur",
             "sensor", num(0x1E, READ, 0x0003, div=10, valid=(-80, 250)), "0x1E read 0003",
             unit=C, device_class=TEMP, state_class=MEAS, diagnostic=True),
    FieldDef("refrigerant_temperature_2", "Refrigerant temperature 2", "Kältemittel Temperatur 2",
             "sensor", num(0x1E, READ, 0x0004, div=10, valid=(-80, 200)), "0x1E read 0004",
             unit=C, device_class=TEMP, state_class=MEAS, diagnostic=True),
    FieldDef("average_outdoor_temperature", "Average outdoor temperature",
             "Mittlere Außentemperatur", "sensor",
             num(0x1E, READ, 0x0005, div=10, valid=(-80, 100)), "0x1E read 0005",
             unit=C, device_class=TEMP, state_class=MEAS, diagnostic=True),
    FieldDef("compressor_temperature", "Compressor temperature", "Verdichtertemperatur", "sensor",
             num(0x1E, READ, 0x0006, div=10, valid=(-80, 200)), "0x1E read 0006",
             unit=C, device_class=TEMP, state_class=MEAS, diagnostic=True),
    FieldDef("high_pressure", "High pressure", "Hochdruck", "sensor",
             num(0x1E, READ, 0x0008, div=10, unsigned=True, valid=(0, 100)), "0x1E read 0008",
             unit="bar", device_class="pressure", state_class=MEAS, candidate=True),
    FieldDef("outdoor_target_temperature", "Outdoor unit target temperature",
             "Zielwert Außeneinheit", "sensor",
             num(0x1E, READ, 0x000A, div=10, valid=(-50, 150)), "0x1E read 000A",
             unit=C, device_class=TEMP, state_class=MEAS, candidate=True),
    FieldDef("compressor_frequency", "Compressor frequency", "Verdichterfrequenz", "sensor",
             _OUT_COMP_FREQ, "0x1E read 000B", unit="Hz", device_class="frequency",
             state_class=MEAS),
    FieldDef("compressor_max_frequency_ratio", "Compressor max frequency ratio",
             "Verdichter max. Frequenzanteil", "sensor",
             num(0x1E, READ, 0x000C, unsigned=True, valid=(0, 200)), "0x1E read 000C",
             unit="%", state_class=MEAS),
    FieldDef("compressor_current", "Compressor current", "Verdichterstrom", "sensor",
             _OUT_COMP_CURRENT, "0x1E read 000D", unit="A", device_class="current",
             state_class=MEAS),
    FieldDef("fan_speed", "Outdoor fan speed", "Ventilatordrehzahl", "sensor",
             num(0x1E, READ, 0x000E, unsigned=True, valid=(0, 5000)), "0x1E read 000E",
             unit="rpm", state_class=MEAS),
    FieldDef("expansion_valve_steps", "Expansion valve steps", "Expansionsventil Schritte",
             "sensor", num(0x1E, READ, 0x0010, unsigned=True, valid=(0, 10000)), "0x1E read 0010",
             unit="steps", state_class=MEAS, diagnostic=True),
    FieldDef("outdoor_unit_state_bits", "Outdoor unit state bits", "Außeneinheit Zustandsbits",
             "sensor", num(0x1E, READ, 0x0014, unsigned=True), "0x1E read 0014", diagnostic=True),
    FieldDef("outdoor_unit_state", "Outdoor unit state", "Außeneinheit Zustand", "text",
             enum(0x1E, READ, 0x0014, _UNIT_STATES, default="Other bitfield state"),
             "0x1E read 0014"),
    FieldDef("compressor_running", "Compressor running", "Verdichter läuft", "binary",
             _OUT_COMPRESSOR_RUNNING, "0x1E read 0014 bit 0x01", device_class="running"),
    FieldDef("compressor_starting", "Compressor starting", "Verdichter startet", "binary",
             _compressor_starting, "0x1E read 0000..000D (heuristic)", device_class="running",
             diagnostic=True),
    FieldDef("outdoor_fan_running", "Outdoor fan running", "Außenventilator läuft", "binary",
             bit(0x1E, READ, 0x0014, 0x04), "0x1E read 0014 bit 0x04", device_class="running"),
    FieldDef("condenser_pump_running", "Condenser pump running", "Kondensatorpumpe läuft",
             "binary", bit(0x1E, READ, 0x0014, 0x08), "0x1E read 0014 bit 0x08",
             device_class="running"),
    FieldDef("outdoor_unit_status_flags", "Outdoor unit status flags", "Außeneinheit Statusflags",
             "sensor", num(0x1E, READ, 0x0015, unsigned=True), "0x1E read 0015", diagnostic=True),
    FieldDef("run_enable_acknowledged", "Run enable acknowledged", "Freigabe bestätigt", "binary",
             bit(0x1E, READ, 0x0015, 0x0200), "0x1E read 0015 bit 0x0200"),
    FieldDef("heating_context", "Heating context", "Heizkontext", "binary",
             _CONTEXT_HEATING, "0x1E read 0015 bit 0x0020"),
    FieldDef("dhw_context", "Hot water context", "Warmwasserkontext", "binary",
             _CONTEXT_DHW, "0x1E read 0015 bit 0x0040"),
    FieldDef("cooling_context", "Cooling context", "Kühlkontext", "binary",
             _CONTEXT_COOLING, "0x1E read 0015 bit 0x0080", candidate=True),
    FieldDef("operating_mode", "Operating mode", "Betriebsmodus", "text",
             _operating_mode, "0x1E read 0015"),
    FieldDef("heating_active", "Heating active", "Heizen aktiv", "binary",
             _active(_CONTEXT_HEATING), "0x1E read 0014/0015 + write 0007/0008",
             device_class="running"),
    FieldDef("dhw_active", "Hot water active", "Warmwasser aktiv", "binary",
             _active(_CONTEXT_DHW), "0x1E read 0014/0015 + write 0007/0008",
             device_class="running"),
    FieldDef("cooling_active", "Cooling active", "Kühlen aktiv", "binary",
             _active(_CONTEXT_COOLING), "0x1E read 0014/0015 + write 0007/0008",
             device_class="running", candidate=True),

    # --- Controller commands to outdoor unit 0x1E (FC10 writes) ---
    FieldDef("commanded_target_temperature", "Commanded target temperature",
             "Vorgegebene Zieltemperatur", "sensor",
             num(0x1E, WRITE, 0x0001, div=10, valid=(-50, 150)), "0x1E write 0001",
             unit=C, device_class=TEMP, state_class=MEAS, diagnostic=True),
    FieldDef("mode_request_raw", "Mode request raw", "Betriebsanforderung Rohwert", "sensor",
             num(0x1E, WRITE, 0x0004), "0x1E write 0004", diagnostic=True),
    FieldDef("mode_request", "Mode request", "Betriebsanforderung", "text",
             enum(0x1E, WRITE, 0x0004, _MODE_REQUEST), "0x1E write 0004", diagnostic=True),
    FieldDef("outdoor_unit_cycle_request", "Outdoor unit cycle request",
             "Außeneinheit Zyklusanforderung", "binary", nonzero(0x1E, WRITE, 0x0007),
             "0x1E write 0007", diagnostic=True),
    FieldDef("outdoor_unit_run_enable_command", "Outdoor unit run enable command",
             "Außeneinheit Freigabebefehl", "binary", nonzero(0x1E, WRITE, 0x0008),
             "0x1E write 0008", diagnostic=True),

    # --- Settings blocks written by the controller to slave 0x0F (FC10) ---
    FieldDef("heating_curve", "Heating curve", "Heizkurve", "sensor",
             num(0x0F, WRITE, 0x03E8), "0x0F write 03E8", state_class=MEAS),
    FieldDef("heating_min", "Heating minimum", "Heizen Minimum", "sensor",
             num(0x0F, WRITE, 0x03E9), "0x0F write 03E9", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("heating_max", "Heating maximum", "Heizen Maximum", "sensor",
             num(0x0F, WRITE, 0x03EA), "0x0F write 03EA", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("curve_plus5", "Heating curve correction +5", "Heizkurvenkorrektur +5", "sensor",
             num(0x0F, WRITE, 0x03EB), "0x0F write 03EB", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("curve_zero", "Heating curve correction 0", "Heizkurvenkorrektur 0", "sensor",
             num(0x0F, WRITE, 0x03EC), "0x0F write 03EC", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("curve_minus5", "Heating curve correction -5", "Heizkurvenkorrektur -5", "sensor",
             num(0x0F, WRITE, 0x03ED), "0x0F write 03ED", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("heating_stop", "Heating stop", "Heizgrenze", "sensor",
             num(0x0F, WRITE, 0x03EE), "0x0F write 03EE", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("reduced_temperature", "Reduced temperature", "Absenktemperatur", "sensor",
             num(0x0F, WRITE, 0x03EF), "0x0F write 03EF", unit=C, device_class=TEMP,
             state_class=MEAS),
    FieldDef("room_factor", "Room factor", "Raumeinfluss", "sensor",
             num(0x0F, WRITE, 0x03F0), "0x0F write 03F0", state_class=MEAS),
    FieldDef("high_power", "High power", "Hochleistung", "binary",
             switch(0x0F, WRITE, 0x03F3), "0x0F write 03F3"),
    FieldDef("room_setpoint_mirror", "Room setpoint (settings page)",
             "Raum-Sollwert (Einstellungsseite)", "sensor",
             num(0x0F, WRITE, 0x03F4), "0x0F write 03F4", unit=C, device_class=TEMP,
             state_class=MEAS, diagnostic=True),
    FieldDef("dhw_enabled", "Hot water enabled", "Warmwasser aktiv (Einstellung)", "binary",
             switch(0x0F, WRITE, 0x042E), "0x0F write 042E"),
    FieldDef("dhw_mode", "Hot water mode", "Warmwasser-Modus", "text",
             enum(0x0F, WRITE, 0x042F, _DHW_MODES), "0x0F write 042F"),
    FieldDef("startup_ht", "Startup HT", "Startzeit HT", "sensor",
             num(0x0F, WRITE, 0x0433), "0x0F write 0433", unit="min", state_class=MEAS,
             candidate=True),
    FieldDef("heating_time", "Heating time", "Heizzeit", "sensor",
             num(0x0F, WRITE, 0x0434), "0x0F write 0434", unit="min", state_class=MEAS,
             candidate=True),
    FieldDef("operation_mode_setting", "Operation mode setting", "Betriebsart (Einstellung)",
             "text", enum(0x0F, WRITE, 0x0553, _OPERATION_MODES), "0x0F write 0553",
             candidate=True),
    FieldDef("cooling_enabled", "Cooling enabled", "Kühlung aktiv (Einstellung)", "binary",
             switch(0x0F, WRITE, 0x0442), "0x0F write 0442", candidate=True),
    FieldDef("cooling_desired_temperature", "Cooling desired temperature",
             "Kühl-Solltemperatur", "sensor",
             num(0x0F, WRITE, 0x0443, valid=(-20, 80)), "0x0F write 0443", unit=C,
             device_class=TEMP, state_class=MEAS, candidate=True),
    FieldDef("cooling_active_above", "Cooling active above", "Kühlung aktiv ab", "sensor",
             num(0x0F, WRITE, 0x0445, valid=(-20, 80)), "0x0F write 0445", unit=C,
             device_class=TEMP, state_class=MEAS, candidate=True),
    FieldDef("cooling_time", "Cooling time", "Kühlzeit", "sensor",
             num(0x0F, WRITE, 0x0449, valid=(0, 180)), "0x0F write 0449", unit="min",
             state_class=MEAS, candidate=True),
    FieldDef("cooling_room_sensor", "Cooling room sensor", "Kühlung Raumsensor", "binary",
             switch(0x0F, WRITE, 0x044C), "0x0F write 044C", candidate=True),
    FieldDef("cooling_room_hysteresis_low", "Cooling room hysteresis low",
             "Kühlung Raumhysterese niedrig", "sensor",
             num(0x0F, WRITE, 0x044D, div=10, valid=(0, 20)), "0x0F write 044D", unit=C,
             state_class=MEAS, candidate=True),
    FieldDef("cooling_room_hysteresis_high", "Cooling room hysteresis high",
             "Kühlung Raumhysterese hoch", "sensor",
             num(0x0F, WRITE, 0x044E, div=10, valid=(0, 20)), "0x0F write 044E", unit=C,
             state_class=MEAS, candidate=True),
    # --- Accessory / expansion interface 0x06 (repo: AFDC context, AFE0 propagated outdoor) ---
    FieldDef("accessory_context_raw", "Accessory context raw AFDC", "Zubehör Kontext Rohwert AFDC",
             "sensor", num(0x06, WRITE, 0xAFDC), "0x06 write AFDC", diagnostic=True),
    FieldDef("accessory_outdoor_temperature", "Accessory propagated outdoor temperature",
             "Außentemperatur (Zubehör-Schnittstelle)", "sensor", num(0x06, WRITE, 0xAFE0),
             "0x06 write AFE0", unit=C, device_class=TEMP, state_class=MEAS),
)

# Which device a field belongs to. The source string always starts with the Modbus slave address.
# 0x04, 0x14, 0xA4 and 0xA5 are not documented in the repo, so they get no device.
SLAVE_DEVICES: dict[str, str] = {
    "0x02": "controller",  # main controller
    "0x06": "accessory",   # expansion / accessory interface
    "0x0A": "room",        # room sensor slot, room thermostat
    "0x0F": "dcm",         # DCM / online module, controller settings blocks
    "0x1E": "outdoor",     # outdoor unit
}


def device_of(fdef: FieldDef) -> str:
    return SLAVE_DEVICES[fdef.source.split()[0]]


# Names for the bus diagnostics created in sensor.py (not register based).
BUS_ENTITY_NAMES: dict[str, tuple[str, str]] = {
    "bus_status": ("Bus status", "Bus-Status"),
    "frames_ok": ("Valid frames", "Gültige Telegramme"),
    "resync_bytes": ("Discarded bytes", "Verworfene Bytes"),
    "unmatched_responses": ("Unmatched responses", "Ungepaarte Antworten"),
    "room_emulation_status": ("Room emulation status", "Raumsensor-Emulation Status"),
    "ack_emulation_status": ("0x0F ACK emulation status", "0x0F ACK-Emulation Status"),
    "room_responses_sent": ("Room responses sent", "Raum-Antworten gesendet"),
    "ack_frames_sent": ("ACK frames sent", "ACK-Telegramme gesendet"),
}

# Names for entities on other platforms: platform -> key -> (en, de).
PLATFORM_ENTITY_NAMES: dict[str, dict[str, tuple[str, str]]] = {
    "climate": {
        "room_thermostat": ("Room thermostat", "Raumthermostat"),
    },
    "button": {
        "dhw_topup": ("Hot water top-up", "Warmwasser-Nachheizung starten"),
    },
    "switch": {
        "ack_emulation_0f": ("0x0F ACK emulation", "0x0F ACK-Emulation"),
    },
}
