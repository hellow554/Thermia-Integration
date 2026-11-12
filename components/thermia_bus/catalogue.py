"""Single source of truth for all Thermia iTec Eco register fields.

Adressen, Skalierung, Gültigkeitsgrenzen und Standardwerte stammen aus
ryckema/Thermia_itec, Ordner "Write (Beta)/iTec Eco" (Raumsensor-Profil und 0f_ack-Profil).

Genutzt von:
  tools/gen.py                 -> C++-Tabelle, docs/REGISTERS.md, config/entities/*.yaml
  components/thermia_bus/*.py  -> Konfigurationsprüfung und Einheiten
"""
from __future__ import annotations

from dataclasses import dataclass

R = "r"  # value seen in a read response
W = "w"  # value seen in a controller write

CEL = "°C"
TEMP = "temperature"
MEAS = "measurement"

# Modbus slaves and the device they are grouped into (repo: protocol overview table).
SLAVE_DEVICES = {
    "0x02": "controller",
    "0x06": "accessory",
    "0x0A": "room",
    "0x0F": "dcm",
    "0x1E": "outdoor",
}
DEVICE_LABELS = {
    "controller": "Regler (0x02)",
    "accessory": "Zubehör (0x06)",
    "room": "Raumregler (0x0A)",
    "dcm": "DCM Online-Modul (0x0F)",  # no "/": ESPHome reserves it in entity names
    "outdoor": "Außeneinheit (0x1E)",
}

OUTDOOR_STATES = ((16, "Idle"), (20, "Fan / autonomous sequence"), (24, "Water flow"),
                  (25, "Water flow + compressor"), (28, "Water flow + fan"),
                  (29, "Water flow + fan + compressor"))
MODE_REQUEST = ((1, "Heating"), (2, "DHW / high temperature"), (3, "Cooling"))
DHW_MODES = ((0, "Comfort"), (1, "Eco"), (2, "Super-Eco"))
OPERATION_MODES = ((0, "Off"), (1, "Auto"), (2, "Compressor"), (3, "Auxiliary Heater"), (4, "Hot Water"))

KIND_NUM, KIND_BIT, KIND_NONZERO, KIND_SWITCH, KIND_EQ, KIND_ENUM, KIND_DERIVED = (
    "NUM", "BIT", "NONZERO", "SWITCH", "EQ", "ENUM", "DERIVED")


@dataclass(frozen=True)
class Spec:
    kind: str
    slave: int = 0
    space: str = R
    addr: int = 0
    div: float = 1.0
    unsigned: bool = False
    valid: tuple | None = None
    sentinel: int | None = None
    mask: int = 0
    eq: int = 0
    enums: tuple = ()
    enum_default: str = "Unknown"
    derived: str = ""


def num(slave, space, addr, *, div=1.0, unsigned=False, valid=None, sentinel=None):
    return Spec(KIND_NUM, slave, space, addr, div, unsigned, valid, sentinel)


def bit(slave, space, addr, mask):
    return Spec(KIND_BIT, slave, space, addr, mask=mask)


def nonzero(slave, space, addr):
    return Spec(KIND_NONZERO, slave, space, addr)


def switch(slave, space, addr):
    return Spec(KIND_SWITCH, slave, space, addr)


def eq(slave, space, addr, value):
    return Spec(KIND_EQ, slave, space, addr, eq=value)


def enum(slave, space, addr, mapping, default="Unknown"):
    return Spec(KIND_ENUM, slave, space, addr, enums=tuple(mapping), enum_default=default)


def derived(name):
    return Spec(KIND_DERIVED, derived=name)


@dataclass(frozen=True)
class Field:
    key: str
    kind: str          # "sensor" | "text" | "binary"
    name_de: str
    name_en: str
    spec: Spec
    source: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    diagnostic: bool = False
    candidate: bool = False

    @property
    def device(self) -> str:
        return SLAVE_DEVICES[self.source.split()[0]]

    @property
    def enabled_default(self) -> bool:
        return not (self.diagnostic or self.candidate)


def F(key, kind, name_de, name_en, spec, source, unit=None, dclass=None, sclass=None,
      diagnostic=False, candidate=False):
    return Field(key, kind, name_de, name_en, spec, source, unit, dclass, sclass, diagnostic, candidate)


FIELDS: tuple[Field, ...] = (
    # --- Regler 0x02 (Lesen: Block A7F8..A806) ---
    F("supply_temperature", "sensor", "Vorlauftemperatur", "Supply temperature",
      num(0x02, R, 0xA7F8, valid=(-50, 150), sentinel=-1000), "0x02 read A7F8", CEL, TEMP, MEAS),
    F("dhw_upper_temperature", "sensor", "Warmwassertemperatur oben", "DHW upper temperature",
      num(0x02, R, 0xA7FB, valid=(0, 100), sentinel=-1000), "0x02 read A7FB", CEL, TEMP, MEAS),
    F("dhw_temperature", "sensor", "Warmwassertemperatur", "DHW temperature",
      num(0x02, R, 0xA7FC, valid=(0, 100), sentinel=-1000), "0x02 read A7FC", CEL, TEMP, MEAS),
    F("outdoor_temperature", "sensor", "Außentemperatur", "Outdoor temperature",
      num(0x02, R, 0xA802, valid=(-50, 70), sentinel=-1000), "0x02 read A802", CEL, TEMP, MEAS),
    F("sg_mode", "text", "SG-Modus", "SG mode", derived("SG_MODE"), "0x02 read A7FD + A803"),
    F("condenser_pump_speed", "sensor", "Kondensatorpumpe Drehzahl", "Condenser pump speed",
      num(0x02, W, 0xA80F, unsigned=True), "0x02 write A80F", "%", None, MEAS),
    F("controller_output_bits_a80c", "sensor", "Reglerausgänge A80C", "Controller output bits A80C",
      num(0x02, W, 0xA80C, unsigned=True), "0x02 write A80C", diagnostic=True),
    F("controller_context", "text", "Reglerkontext", "Controller context",
      derived("CONTROLLER_CONTEXT"), "0x02 write A80C", diagnostic=True),
    F("controller_accessory_status_a80e", "sensor", "Reglerzubehör A80E", "Controller accessory status A80E",
      num(0x02, W, 0xA80E, unsigned=True), "0x02 write A80E", diagnostic=True),
    F("controller_flag_a80c_0x10", "binary", "Reglerflag A80C 0x10", "Controller flag A80C 0x10",
      bit(0x02, W, 0xA80C, 0x10), "0x02 write A80C", diagnostic=True),
    F("controller_flag_a80c_0x20", "binary", "Reglerflag A80C 0x20", "Controller flag A80C 0x20",
      bit(0x02, W, 0xA80C, 0x20), "0x02 write A80C", diagnostic=True),
    F("controller_flag_a80e_0x08", "binary", "Reglerflag A80E 0x08", "Controller flag A80E 0x08",
      bit(0x02, W, 0xA80E, 0x08), "0x02 write A80E", diagnostic=True),
    F("controller_flag_a80e_0x20", "binary", "Reglerflag A80E 0x20", "Controller flag A80E 0x20",
      bit(0x02, W, 0xA80E, 0x20), "0x02 write A80E", diagnostic=True),

    # --- Zubehör 0x06 ---
    F("accessory_context_raw", "sensor", "Zubehör Kontext Rohwert AFDC", "Accessory context raw AFDC",
      num(0x06, W, 0xAFDC), "0x06 write AFDC", diagnostic=True),
    F("accessory_outdoor_temperature", "sensor", "Außentemperatur (Zubehör)", "Accessory outdoor temperature",
      num(0x06, W, 0xAFE0), "0x06 write AFE0", CEL, TEMP, MEAS),

    # --- Raumregler 0x0A ---
    F("room_temperature", "sensor", "Raumtemperatur", "Room temperature",
      num(0x0A, R, 0xB3B0, div=10, valid=(-20, 60)), "0x0A read B3B0", CEL, TEMP, MEAS),
    F("room_setpoint", "sensor", "Raum-Sollwert", "Room setpoint",
      num(0x0A, W, 0xB3C5, valid=(5, 40)), "0x0A write B3C5", CEL, TEMP, MEAS),
    F("room_bus_outdoor_temperature", "sensor", "Außentemperatur (Raumbus)", "Outdoor temperature (room bus)",
      num(0x0A, W, 0xB3C4), "0x0A write B3C4", CEL, TEMP, MEAS, diagnostic=True),
    F("dhw_topup_active", "binary", "Warmwasser-Nachheizung aktiv", "Hot water top-up active",
      eq(0x0A, W, 0xB3C6, 2), "0x0A write B3C6 == 2", dclass="running"),
    F("room_control_flag_b3c6", "binary", "Raumsensor-Steuerflag B3C6", "Room sensor control flag B3C6",
      nonzero(0x0A, W, 0xB3C6), "0x0A write B3C6 != 0", diagnostic=True),

    # --- Außeneinheit 0x1E (FC04-Block 0000..0015) ---
    F("condenser_in", "sensor", "Kondensator Eintritt", "Condenser inlet",
      num(0x1E, R, 0x0000, div=10, valid=(-50, 150)), "0x1E read 0000", CEL, TEMP, MEAS, candidate=True),
    F("condenser_out", "sensor", "Kondensator Austritt", "Condenser outlet",
      num(0x1E, R, 0x0001, div=10, valid=(-50, 150)), "0x1E read 0001", CEL, TEMP, MEAS, candidate=True),
    F("condenser_delta", "sensor", "Kondensator Spreizung", "Condenser delta T",
      derived("CONDENSER_DELTA"), "0x1E read 0000 + 0001", CEL, None, MEAS, candidate=True),
    F("refrigerant_temperature_1", "sensor", "Kältemittel Temperatur 1", "Refrigerant temperature 1",
      num(0x1E, R, 0x0002, div=10, valid=(-80, 200)), "0x1E read 0002", CEL, TEMP, MEAS, diagnostic=True),
    F("discharge_gas_temperature", "sensor", "Heißgastemperatur", "Discharge gas temperature",
      num(0x1E, R, 0x0003, div=10, valid=(-80, 250)), "0x1E read 0003", CEL, TEMP, MEAS, diagnostic=True),
    F("refrigerant_temperature_2", "sensor", "Kältemittel Temperatur 2", "Refrigerant temperature 2",
      num(0x1E, R, 0x0004, div=10, valid=(-80, 200)), "0x1E read 0004", CEL, TEMP, MEAS, diagnostic=True),
    F("average_outdoor_temperature", "sensor", "Mittlere Außentemperatur", "Average outdoor temperature",
      num(0x1E, R, 0x0005, div=10, valid=(-80, 100)), "0x1E read 0005", CEL, TEMP, MEAS, diagnostic=True),
    F("compressor_temperature", "sensor", "Verdichtertemperatur", "Compressor temperature",
      num(0x1E, R, 0x0006, div=10, valid=(-80, 200)), "0x1E read 0006", CEL, TEMP, MEAS, diagnostic=True),
    F("high_pressure", "sensor", "Hochdruck", "High pressure",
      num(0x1E, R, 0x0008, div=10, unsigned=True, valid=(0, 100)), "0x1E read 0008", "bar", "pressure", MEAS,
      candidate=True),
    F("outdoor_target_temperature", "sensor", "Zielwert Außeneinheit", "Outdoor unit target temperature",
      num(0x1E, R, 0x000A, div=10, valid=(-50, 150)), "0x1E read 000A", CEL, TEMP, MEAS, candidate=True),
    F("compressor_frequency", "sensor", "Verdichterfrequenz", "Compressor frequency",
      num(0x1E, R, 0x000B, unsigned=True, valid=(0, 200)), "0x1E read 000B", "Hz", "frequency", MEAS),
    F("compressor_max_frequency_ratio", "sensor", "Verdichter max. Frequenzanteil", "Compressor max frequency ratio",
      num(0x1E, R, 0x000C, unsigned=True, valid=(0, 200)), "0x1E read 000C", "%", None, MEAS),
    F("compressor_current", "sensor", "Verdichterstrom", "Compressor current",
      num(0x1E, R, 0x000D, div=10, unsigned=True, valid=(0, 100)), "0x1E read 000D", "A", "current", MEAS),
    F("fan_speed", "sensor", "Ventilatordrehzahl", "Outdoor fan speed",
      num(0x1E, R, 0x000E, unsigned=True, valid=(0, 5000)), "0x1E read 000E", "rpm", None, MEAS),
    F("expansion_valve_steps", "sensor", "Expansionsventil Schritte", "Expansion valve steps",
      num(0x1E, R, 0x0010, unsigned=True, valid=(0, 10000)), "0x1E read 0010", "steps", None, MEAS,
      diagnostic=True),
    F("outdoor_unit_state_bits", "sensor", "Außeneinheit Zustandsbits", "Outdoor unit state bits",
      num(0x1E, R, 0x0014, unsigned=True), "0x1E read 0014", diagnostic=True),
    F("outdoor_unit_state", "text", "Außeneinheit Zustand", "Outdoor unit state",
      enum(0x1E, R, 0x0014, OUTDOOR_STATES, "Other bitfield state"), "0x1E read 0014"),
    F("compressor_running", "binary", "Verdichter läuft", "Compressor running",
      bit(0x1E, R, 0x0014, 0x01), "0x1E read 0014 bit 0x01", dclass="running"),
    F("compressor_starting", "binary", "Verdichter startet", "Compressor starting",
      derived("COMPRESSOR_STARTING"), "0x1E read 0000..000D (heuristic)", dclass="running", diagnostic=True),
    F("outdoor_fan_running", "binary", "Außenventilator läuft", "Outdoor fan running",
      bit(0x1E, R, 0x0014, 0x04), "0x1E read 0014 bit 0x04", dclass="running"),
    F("condenser_pump_running", "binary", "Kondensatorpumpe läuft", "Condenser pump running",
      bit(0x1E, R, 0x0014, 0x08), "0x1E read 0014 bit 0x08", dclass="running"),
    F("outdoor_unit_status_flags", "sensor", "Außeneinheit Statusflags", "Outdoor unit status flags",
      num(0x1E, R, 0x0015, unsigned=True), "0x1E read 0015", diagnostic=True),
    F("run_enable_acknowledged", "binary", "Freigabe bestätigt", "Run enable acknowledged",
      bit(0x1E, R, 0x0015, 0x0200), "0x1E read 0015 bit 0x0200"),
    F("heating_context", "binary", "Heizkontext", "Heating context",
      bit(0x1E, R, 0x0015, 0x0020), "0x1E read 0015 bit 0x0020"),
    F("dhw_context", "binary", "Warmwasserkontext", "Hot water context",
      bit(0x1E, R, 0x0015, 0x0040), "0x1E read 0015 bit 0x0040"),
    F("cooling_context", "binary", "Kühlkontext", "Cooling context",
      bit(0x1E, R, 0x0015, 0x0080), "0x1E read 0015 bit 0x0080", candidate=True),
    F("operating_mode", "text", "Betriebsmodus", "Operating mode",
      derived("OPERATING_MODE"), "0x1E read 0015"),
    F("heating_active", "binary", "Heizen aktiv", "Heating active",
      derived("HEATING_ACTIVE"), "0x1E read 0014/0015 + write 0007/0008", dclass="running"),
    F("dhw_active", "binary", "Warmwasser aktiv", "Hot water active",
      derived("DHW_ACTIVE"), "0x1E read 0014/0015 + write 0007/0008", dclass="running"),
    F("cooling_active", "binary", "Kühlen aktiv", "Cooling active",
      derived("COOLING_ACTIVE"), "0x1E read 0014/0015 + write 0007/0008", dclass="running", candidate=True),

    # --- Vorgaben des Reglers an die Außeneinheit (Schreiben 0x1E) ---
    F("commanded_target_temperature", "sensor", "Vorgegebene Zieltemperatur", "Commanded target temperature",
      num(0x1E, W, 0x0001, div=10, valid=(-50, 150)), "0x1E write 0001", CEL, TEMP, MEAS, diagnostic=True),
    F("mode_request_raw", "sensor", "Betriebsanforderung Rohwert", "Mode request raw",
      num(0x1E, W, 0x0004), "0x1E write 0004", diagnostic=True),
    F("mode_request", "text", "Betriebsanforderung", "Mode request",
      enum(0x1E, W, 0x0004, MODE_REQUEST), "0x1E write 0004", diagnostic=True),
    F("outdoor_unit_cycle_request", "binary", "Außeneinheit Zyklusanforderung", "Outdoor unit cycle request",
      nonzero(0x1E, W, 0x0007), "0x1E write 0007", diagnostic=True),
    F("outdoor_unit_run_enable_command", "binary", "Außeneinheit Freigabebefehl", "Outdoor unit run enable command",
      nonzero(0x1E, W, 0x0008), "0x1E write 0008", diagnostic=True),

    # --- Einstellungsblöcke des Reglers an den DCM-Slot 0x0F (FC10) ---
    F("heating_curve", "sensor", "Heizkurve", "Heating curve",
      num(0x0F, W, 0x03E8), "0x0F write 03E8", None, None, MEAS),
    F("heating_min", "sensor", "Heizen Minimum", "Heating minimum",
      num(0x0F, W, 0x03E9), "0x0F write 03E9", CEL, TEMP, MEAS),
    F("heating_max", "sensor", "Heizen Maximum", "Heating maximum",
      num(0x0F, W, 0x03EA), "0x0F write 03EA", CEL, TEMP, MEAS),
    F("curve_plus5", "sensor", "Heizkurvenkorrektur +5", "Heating curve correction +5",
      num(0x0F, W, 0x03EB), "0x0F write 03EB", CEL, TEMP, MEAS),
    F("curve_zero", "sensor", "Heizkurvenkorrektur 0", "Heating curve correction 0",
      num(0x0F, W, 0x03EC), "0x0F write 03EC", CEL, TEMP, MEAS),
    F("curve_minus5", "sensor", "Heizkurvenkorrektur -5", "Heating curve correction -5",
      num(0x0F, W, 0x03ED), "0x0F write 03ED", CEL, TEMP, MEAS),
    F("heating_stop", "sensor", "Heizgrenze", "Heating stop",
      num(0x0F, W, 0x03EE), "0x0F write 03EE", CEL, TEMP, MEAS),
    F("reduced_temperature", "sensor", "Absenktemperatur", "Reduced temperature",
      num(0x0F, W, 0x03EF), "0x0F write 03EF", CEL, TEMP, MEAS),
    F("room_factor", "sensor", "Raumeinfluss", "Room factor",
      num(0x0F, W, 0x03F0), "0x0F write 03F0", None, None, MEAS),
    F("high_power", "binary", "Hochleistung", "High power",
      switch(0x0F, W, 0x03F3), "0x0F write 03F3"),
    F("room_setpoint_mirror", "sensor", "Raum-Sollwert (Einstellungsseite)", "Room setpoint (settings page)",
      num(0x0F, W, 0x03F4), "0x0F write 03F4", CEL, TEMP, MEAS, diagnostic=True),
    F("dhw_enabled", "binary", "Warmwasser aktiv (Einstellung)", "Hot water enabled",
      switch(0x0F, W, 0x042E), "0x0F write 042E"),
    F("dhw_mode", "text", "Warmwasser-Modus", "Hot water mode",
      enum(0x0F, W, 0x042F, DHW_MODES), "0x0F write 042F"),
    F("startup_ht", "sensor", "Startzeit HT", "Startup HT",
      num(0x0F, W, 0x0433), "0x0F write 0433", "min", None, MEAS, candidate=True),
    F("heating_time", "sensor", "Heizzeit", "Heating time",
      num(0x0F, W, 0x0434), "0x0F write 0434", "min", None, MEAS, candidate=True),
    F("operation_mode_setting", "text", "Betriebsart (Einstellung)", "Operation mode setting",
      enum(0x0F, W, 0x0553, OPERATION_MODES), "0x0F write 0553", candidate=True),
    F("cooling_enabled", "binary", "Kühlung aktiv (Einstellung)", "Cooling enabled",
      switch(0x0F, W, 0x0442), "0x0F write 0442", candidate=True),
    F("cooling_desired_temperature", "sensor", "Kühl-Solltemperatur", "Cooling desired temperature",
      num(0x0F, W, 0x0443, valid=(-20, 80)), "0x0F write 0443", CEL, TEMP, MEAS, candidate=True),
    F("cooling_active_above", "sensor", "Kühlung aktiv ab", "Cooling active above",
      num(0x0F, W, 0x0445, valid=(-20, 80)), "0x0F write 0445", CEL, TEMP, MEAS, candidate=True),
    F("cooling_time", "sensor", "Kühlzeit", "Cooling time",
      num(0x0F, W, 0x0449, valid=(0, 180)), "0x0F write 0449", "min", None, MEAS, candidate=True),
    F("cooling_room_sensor", "binary", "Kühlung Raumsensor", "Cooling room sensor",
      switch(0x0F, W, 0x044C), "0x0F write 044C", candidate=True),
    F("cooling_room_hysteresis_low", "sensor", "Kühlung Raumhysterese niedrig", "Cooling room hysteresis low",
      num(0x0F, W, 0x044D, div=10, valid=(0, 20)), "0x0F write 044D", CEL, None, MEAS, candidate=True),
    F("cooling_room_hysteresis_high", "sensor", "Kühlung Raumhysterese hoch", "Cooling room hysteresis high",
      num(0x0F, W, 0x044E, div=10, valid=(0, 20)), "0x0F write 044E", CEL, None, MEAS, candidate=True),
)

# Diagnose- und Emulationswerte, die nicht aus einem Register stammen. Werden in C++ berechnet.
# (key, kind, name_de, name_en, diagnostic)
DIAG_SENSORS = (
    ("bus_status", "text", "Bus-Status", "Bus status", True),
    ("frames_ok", "sensor", "Gültige Telegramme", "Valid frames", True),
    ("resync_bytes", "sensor", "Verworfene Bytes", "Discarded bytes", True),
    ("unmatched_responses", "sensor", "Ungepaarte Antworten", "Unmatched responses", True),
    ("room_emulation_status", "text", "Raumsensor-Emulation Status", "Room emulation status", True),
    ("ack_emulation_status", "text", "0x0F ACK-Emulation Status", "0x0F ACK emulation status", True),
    ("room_responses_sent", "sensor", "Raum-Antworten gesendet", "Room responses sent", True),
    ("ack_frames_sent", "sensor", "ACK-Telegramme gesendet", "ACK frames sent", True),
)


def field_by_key(key: str) -> Field:
    for f in FIELDS:
        if f.key == key:
            return f
    raise KeyError(key)


def keys_for(kind: str) -> list[str]:
    return [f.key for f in FIELDS if f.kind == kind]
