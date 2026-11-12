# Plan: ESPHome 2026.10 mit eigener Komponente

Ziel-Version: ESPHome 2026.10.1 (stabiles Patch-Release vom 27.10.2026). Im CI wird genau diese Version installiert.

## Stand

| Phase | Inhalt | Stand |
|---|---|---|
| 0 | Repo-Gerüst, Registerkatalog als einzige Quelle, Generator | erledigt |
| 1 | C++-Kern: Framing, passiver Dekoder, Feldauswertung | erledigt, 89 Host-Tests grün |
| 2 | Emulation: Raumsensor (0x0A), 0x0F ACK, TX-Zeitplan | erledigt im Kern, Host-Tests grün |
| 3 | ESPHome-Glue: Komponente, Plattformen, Gerätekonfiguration | geschrieben, **noch nicht kompiliert** |
| 4 | Dry-Run-Schalter (Protokoll läuft, kein Senden am Bus) | offen |
| 5 | Prüfstand: Schritte aus docs/BENCH_TEST.md | offen, blockiert durch Schritt 1 |
| 6 | Erster Anschluss an den Bus | offen, erst nach Bestehen von Schritt 1–3 |

## Architektur

- `components/thermia_bus/thermia_core.*`: reine C++17-Bibliothek ohne ESPHome. Enthält CRC, Frame-Parser mit Resync,
  passiven Dekoder, Feldauswertung, Raumsensor- und ACK-Emulation und die TX-Zustandsmaschine.
- `components/thermia_bus/thermia_bus.*`: dünne ESPHome-Hülle. Liest UART, schreibt Pins, publiziert Werte.
- `components/thermia_bus/catalogue.py`: einzige Quelle für Register. `tools/gen.py` erzeugt daraus die C++-Tabelle,
  die Dokumentation und die YAML-Entitäten.
- `config/`: Gerätekonfiguration für das Relay-1CH, Entitäten und Raumsteuerung.

## Warum die Logik in C++ und nicht in Lambdas

- Lambdas in YAML sind schwer zu testen. Die Repo-Version steckt die gesamte Protokolllogik in einen großen Lambda-Block im UART-Abschnitt (YAML-Zeilen 466–2466), der nur am Gerät läuft.
- Die Zeitentscheidungen laufen in einer Zustandsmaschine mit Mikrosekunden-Zählung. Sie ist auf dem Host testbar.
- Die Sende-Hardware wird nur an einer Stelle angesprochen (`handle_tx`).

## Bekannte Grenzen

- `flush()` blockiert, bis das Telegramm gesendet ist. Das ist im Repo genauso. Eine Abfrage-Antwort dauert damit ca. 12 ms.
- Die Glue-Schicht ist nicht gegen die ESPHome-API kompiliert. Die CI prüft das (`esphome compile`). Bis dahin gilt sie als ungeprüft.
- Welche Sensor-Methoden im Detail gültig sind (`invalidate_state` bei Binärsensoren), wird beim ersten Kompilieren bestätigt.
- ESPHome-Sub-Devices sind in den Release-Notes 2026.10 nicht erwähnt. Deshalb tragen die Entitäten den Gerätenamen als Präfix,
  z. B. „Regler (0x02) Vorlauftemperatur“.

## Nächste Schritte

1. CI laufen lassen (Host-Tests, Generator-Abgleich, `esphome compile` mit 2026.10.1).
2. Dry-Run-Schalter einbauen (Phase 4).
3. Prüfstand Schritt 1 (Bus beim Einschalten).
4. Erst danach Schritt 2 bis 6.
