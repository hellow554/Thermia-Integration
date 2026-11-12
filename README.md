# Thermia iTec Eco für ESPHome (Waveshare ESP32-S3-Relay-1CH)

Lokale ESPHome-Komponente, die die Thermia iTec Eco über den internen RS485-Bus ausliest und Raumsteuerung,
Warmwasser-Nachheizung, ein 0x0F-ACK und eine Umwälzpumpe bereitstellt. Ersetzt die frühere Home-Assistant-Integration.

> **Status:** Komponente und Tests sind geschrieben. Die ESPHome-Kompilierung läuft in der CI, der Prüfstand ist offen.
> **Vor dem Anschluss an die Wärmepumpe `docs/SAFETY.md` lesen.**

## Was drin ist

- Alle Werte der Repo-Konfiguration für die Eco, aufgeteilt nach Modbus-Slave (Regler 0x02, Zubehör 0x06, Raumregler 0x0A,
  DCM 0x0F, Außeneinheit 0x1E). Vollständige Liste in `docs/REGISTERS.md`.
- Raumsensor-Emulation (0x0A) mit Watchdog und Sollwert-Anforderung.
- 0x0F ACK-Emulation mit 0x0708-Antwort.
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
    esphome compile config/thermia-relay.yaml  # ESPHome 2026.10.1
    esphome run config/thermia-relay.yaml      # erstes Flashen per USB

Danach den Prüfstand in `docs/BENCH_TEST.md` durchgehen, bevor das Board an den Bus kommt.

## Dokumentation

- `docs/SAFETY.md`: Sicherheit, Boot-Zustand des Enable-Pins, Pumpe, Netzspannung
- `docs/BENCH_TEST.md`: Prüfstand in Schritten mit Abbruchkriterien
- `docs/DECISIONS.md`: alle Entscheidungen mit Quelle
- `docs/PLAN_ESPHOME_2026_10.md`: Plan und Stand
- `docs/REGISTERS.md`: alle Register (erzeugt)
- `AGENTS.md`: Regeln für Mitarbeit und KI-Agenten

## Lizenz und Danksagung

MIT, siehe `LICENSE`. Register, Zeiten und Abläufe stammen aus [ryckema/Thermia_itec](https://github.com/ryckema/Thermia_itec)
(MIT). Die Protokollforschung von Piotr Romanowski ist dort ebenfalls genannt. Details in `NOTICE.md`.
