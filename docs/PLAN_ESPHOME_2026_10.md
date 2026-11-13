# Plan: ESPHome 2026.10 mit eigener Komponente

Ziel-Version: ESPHome 2026.10.1 (im CI fest gepinnt).

## Stand

| Phase | Inhalt | Stand |
|---|---|---|
| 0 | Repo-Gerüst, Registerkatalog als einzige Quelle, Generator | erledigt |
| 1 | C++-Kern: Framing, passiver Dekoder, Feldauswertung | erledigt; Host-Tests grün |
| 2 | Emulation: Raumsensor (0x0A), 0x0F ACK, TX-Zeitplan | implementiert; Host-Tests grün |
| 3 | ESPHome-Glue und YAML-Konfiguration | überarbeitet; ESPHome-Firmwarebuild noch ausstehend |
| 4 | Dry-Run-Schalter (Protokoll läuft, kein Senden am Bus) | offen |
| 5 | Elektrische und funktionale Prüfstandstests | offen; Schritt 1 ausdrücklich zurückgestellt, aber weiterhin vor Busanschluss erforderlich |
| 6 | Erster Anschluss an den Bus | offen, erst nach Safety-/Dry-Run-Prüfung |

## Neue Konfigurationsschnittstelle

- `dcm.0x0f_emulation`: bool, Standard `false`.
- `room_temperature.enable`: optional bool. Fehlt es, aktiviert eine vorhandene, valide Sensorreferenz automatisch.
- `room_temperature.room_temperature_sensor`: ESPHome-Sensor-ID; bei üblicher Nutzung zeigt ein `platform: homeassistant`-Sensor auf die HA-Entity.
- `register_stale_after`: Sekunden, Standard `0` (keine automatische Invalidierung). Positive Werte machen Registerwerte nach Ablauf ungültig.
- Raumemulation wird bei Start logisch aktiviert, sofern konfiguriert. Antwortversuche bleiben bis zu einem frischen, gültigen HA-Wert aus.

## Architektur

- `components/thermia_bus/thermia_core.*`: reine C++17-Bibliothek ohne ESPHome. Enthält CRC, Frame-Parser mit Resync,
  passiven Dekoder, Feldauswertung, Raumsensor- und ACK-Emulation und die TX-Zustandsmaschine.
- `components/thermia_bus/thermia_bus.*`: ESPHome-Hülle. Liest UART, schreibt Pins und publiziert nur geänderte Werte.
- `components/thermia_bus/catalogue.py`: einzige Quelle für Register und Diagnoseentitäten. `tools/gen.py` erzeugt C++-Tabelle,
  Registerdokumentation und YAML-Entitäten.
- `config/`: Gerätekonfiguration für das Relay-1CH, Entitäten und Raumsteuerung.

## Bekannte Grenzen

- `flush()` blockiert, bis das Telegramm gesendet ist. Das ist im Repo genauso. Eine Abfrage-Antwort dauert damit ca. 12 ms.
- Die ESPHome-Glue-Schicht muss mit ESPHome 2026.10.1 kompiliert werden; der Host-Build deckt sie nicht ab.
- UART-/TX-Timing und GPIO21-Bootpegel müssen auf Hardware gemessen werden.
- `register_stale_after: 0` lässt den Cache unbegrenzt gültig; ein sinnvoller positiver Wert ist erst nach Messung der Register-Pollintervalle festzulegen.

## Nächste Schritte

1. ESPHome 2026.10.1 installieren und Firmware kompilieren.
2. Dry-Run-Schalter implementieren.
3. Vor dem Anschluss GPIO21 / RS485_EN im Boot- und Resetverhalten messen (siehe `docs/SAFETY.md`).
4. UART-/TX-Timing, Peer-Erkennung, Watchdog, Diagnosewerte und übrige Funktionsfälle gemäß `docs/TODO.md` prüfen.
5. Erst nach diesen Prüfungen an den realen Bus anschließen.
