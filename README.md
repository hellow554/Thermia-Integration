# Thermia iTec Eco für ESPHome (Waveshare ESP32-S3-Relay-1CH)

Lokale ESPHome-Komponente, die die Thermia iTec Eco über den internen RS485-Bus ausliest und Raumsteuerung,
Warmwasser-Nachheizung, ein 0x0F-ACK und eine Umwälzpumpe bereitstellt. Ersetzt die frühere Home-Assistant-Integration.

> **Status:** Komponente und Tests sind geschrieben. Die ESPHome-Kompilierung läuft in der CI, der Prüfstand ist offen.
> **Vor dem Anschluss an die Wärmepumpe `docs/SAFETY.md` lesen.**

## Was drin ist

- Alle Werte der Repo-Konfiguration für die Eco, aufgeteilt nach Modbus-Slave (Regler 0x02, Zubehör 0x06, Raumregler 0x0A,
  DCM 0x0F, Außeneinheit 0x1E). Vollständige Liste in `docs/REGISTERS.md`.
- Konfigurierbare Raumsensor-Emulation (0x0A) mit Watchdog und Sollwert-Anforderung.
- Konfigurierbare 0x0F ACK-Emulation mit 0x0708-Antwort.
- Raumthermostat (climate), Warmwasser-Nachheizung (button), Umwälzpumpe (switch, Relais GPIO47).

## Hardware

| Pin | Funktion |
|---|---|
| GPIO17 | RS485 TX |
| GPIO18 | RS485 RX |
| GPIO21 | RS485 Freigabe (DE/RE) |
| GPIO47 | Relais (Umwälzpumpe) |

Verdrahtung: RJ45 Pin 1 oder 2 → A, Pin 3 oder 4 → B, Pin 5 oder 6 → GND. **Pins 7 und 8 (+12 V) nicht anschließen.**

## Schnellstart

    python3 tools/gen.py                      # erzeugt Register-Header, Doku und Entitäten
    bash tests/run_tests.sh                   # C++-Host-Tests
    cp config/secrets.yaml.example config/secrets.yaml   # ausfüllen, api_key mit: openssl rand -base64 32
    esphome compile config/thermia-relay.yaml  # ESPHome 2026.10.2
    esphome run config/thermia-relay.yaml      # erstes Flashen per USB

Danach den Prüfstand in `docs/BENCH_TEST.md` durchgehen, bevor das Board an den Bus kommt.

## Emulation konfigurieren

Die Optionen stehen direkt unter `thermia_bus:`. Beispiel:

```yaml
thermia_bus:
  id: thermia
  uart_id: thermia_uart
  de_pin: GPIO21
  dcm:
    "0x0f_emulation": true
  room_temperature:
    # enable ist optional: Sensorreferenz vorhanden => automatisch aktiv.
    # enable: true
    room_temperature_sensor: room_temperature_source
    # enable: false  # optionaler Override: deaktiviert die Emulation trotz Sensorreferenz
  register_stale_after: 0  # Sekunden; 0 deaktiviert automatische Invalidierung

sensor:
  - platform: homeassistant
    id: room_temperature_source
    entity_id: sensor.wohnzimmer_temperatur
```

`room_temperature.room_temperature_sensor` ist eine ESPHome-Sensor-ID, keine Home-Assistant-Entity-ID.
Die HA-Entity wird im separaten `platform: homeassistant`-Sensor ausgewählt. Wird `enable` weggelassen, aktiviert
sich die Raumemulation automatisch bei vorhandener, gültiger Sensorreferenz. `enable: false` schaltet sie explizit
aus; `enable: true` ohne Sensor wird bereits bei der YAML-Validierung abgelehnt. Die Emulation ist nach dem Start
logisch aktiv, sendet aber erst nach Empfang eines gültigen Temperaturwerts. Ohne Sensorreferenz und ohne
explizites `enable: true` findet keine Raumthermostat-Emulation statt.

`dcm.0x0f_emulation` ist standardmäßig `false` und muss explizit auf `true` gesetzt werden. `register_stale_after`
ist optional: Ein positiver Wert invalidiert einzelne Registerdaten nach der angegebenen Zahl Sekunden. Der
Diagnosewert `oldest_register_age_seconds` zeigt das Alter des ältesten gespeicherten Werts; der Binärsensor
`register_data_stale` meldet veraltete Daten (bei `register_stale_after: 0` ist er unavailable). `tx_dropped` zählt
Sendeaufträge, die der Scheduler wegen eines bereits laufenden Auftrags nicht übernehmen konnte.

## Dokumentation

- `docs/SAFETY.md`: Sicherheit, Boot-Zustand des Enable-Pins, Pumpe, Netzspannung
- `docs/BENCH_TEST.md`: Prüfstand in Schritten mit Abbruchkriterien
- `docs/DECISIONS.md`: alle Entscheidungen mit Quelle
- `docs/PLAN_ESPHOME_2026_10.md`: Plan und Stand
- `docs/TODO.md`: offene Firmware-, Timing- und Prüfstandaufgaben
- `docs/REGISTERS.md`: alle Register (erzeugt)
- `AGENTS.md`: Regeln für Mitarbeit und KI-Agenten

## Lizenz und Danksagung

MIT, siehe `LICENSE`. Register, Zeiten und Abläufe stammen aus [ryckema/Thermia_itec](https://github.com/ryckema/Thermia_itec)
(MIT). Die Protokollforschung von Piotr Romanowski ist dort ebenfalls genannt. Details in `NOTICE.md`.


## Home Assistant 2026.11 setup wizard

The optional room-temperature source is selected when adding the ESPHome device in
Home Assistant 2026.11 or newer. The remote package
`config/packages/home_assistant_wizard.yaml` declares a linked
`platform: homeassistant` sensor without a fixed `entity_id`, and the API wizard
asks the user to select a Home Assistant temperature sensor. Keep the
`room_temperature.room_temperature_sensor` reference in `thermia_bus:` pointing
to that ESPHome sensor ID (`room_temperature_source`).

The wizard selection is stored by Home Assistant and sent to the ESP32 whenever
the API connects; it is not persisted on the ESP32. After a reboot, room
emulation remains configured/enabled, but it will not send a room-temperature
reply until Home Assistant reconnects, supplies the selected entity ID, and a
valid fresh temperature state arrives. If the wizard input is not selected,
the emulation safely waits for a source.
