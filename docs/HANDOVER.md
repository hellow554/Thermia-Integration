# Übergabe

Für weitere Entwickler und KI-Agenten. Vor dem Arbeiten `AGENTS.md` lesen.

## Was existiert

- Protokollkern in C++ mit Host-Tests (`bash tests/run_tests.sh`).
- Registerkatalog in `components/thermia_bus/catalogue.py`; Generator erstellt C++-Registertabelle, Registerdoku und ESPHome-Entitäten.
- ESPHome-Komponente mit YAML-Konfiguration für DCM-ACK und Raumthermostat sowie HA-Sensorreferenz.
- Change-only-Publishing für Sensoren, Binärsensoren, Textsensoren und Climate.
- Diagnosewerte einschließlich `tx_dropped`, `oldest_register_age_seconds` und `register_data_stale`.
- Konfigurierbare Invalidierung veralteter Registerwerte über `register_stale_after` (0 = deaktiviert).

## Konfigurationsregeln

- `dcm.0x0f_emulation` fehlt/false: keine DCM-ACK-Emulation; true: beim Start aktiv.
- `room_temperature.room_temperature_sensor` ist eine ESPHome-Sensor-ID, normalerweise ein Home-Assistant-Sensor.
- `room_temperature.enable` fehlt: automatisch anhand der vorhandenen Sensorreferenz; false: deaktiviert; true ohne Sensor: Konfigurationsfehler.
- Die Raumemulation ist beim Start logisch aktiv, sofern aktiviert konfiguriert. Eine Antwort wird erst nach einem gültigen aktuellen Temperaturwert gesendet.
- `register_stale_after` ist in Sekunden; 0 deaktiviert Ablauf, positive Werte invalidieren überalterte Registerwerte. `register_data_stale` zeigt an, ob mindestens ein gespeicherter Registerwert überaltert oder noch gar keiner empfangen wurde.

## Noch offen

- ESPHome-Kompilierung mit genau 2026.10.1 ausführen (CI-Job vorhanden; in der vorherigen Arbeitsumgebung nicht lokal installiert).
- `docs/BENCH_TEST.md` und `docs/TODO.md`: Boot-Pegel / DE-Transceiverzustand, UART-/TX-Timing und Verhalten am realen Bus prüfen.
- Dry-Run-Schalter für den Prüfstand fertigstellen; bis dahin ist Schritt 3 ausdrücklich nicht ausführbar.
- Erst nach den elektrischen Prüfungen tatsächlichen Anschluss an die Wärmepumpe vornehmen.

## Regeln für Änderungen

- Register nur über `catalogue.py` ändern, dann `python3 tools/gen.py` und `bash tests/run_tests.sh`.
- Keine Zahl ohne Quelle im Repo. Die Quelle gehört in die Kommentarzeile des Feldes.
- Softwareänderungen am Sendepfad sind für diesen Stand vom Nutzer vor der Hardwareprüfung freigegeben. Daraus folgt keine Freigabe, das Board vor Abschluss der offenen Sicherheitsmessung anzuschließen.
