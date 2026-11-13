# Entscheidungen

Jede Entscheidung nennt die Quelle. Änderungen nur nach Rücksprache mit dem Nutzer.

| # | Entscheidung | Quelle |
|---|---|---|
| D1 | Repo `ryckema/Thermia_itec` ist die Quelle der Wahrheit für Adressen, Skalierung, Zeiten und Abläufe. | Nutzer |
| D2 | Zielplattform ist ESPHome auf dem Waveshare ESP32-S3-Relay-1CH, Ersatz für die Python-Integration. | Nutzer |
| D3 | Eigene Custom-Komponente (C++), keine Lambdas für Bus-Logik. | Nutzer |
| D4 | Ziel-ESPHome-Version 2026.10 (aktuelles Patch-Release 2026.10.1). | Nutzer, ESPHome-Changelog |
| D5 | Pins: TX GPIO17, RX GPIO18, Freigabe DE/RE GPIO21, Relais GPIO47. | Nutzer, Schaltplan |
| D6 | Raumthermostat-Emulation 0x0A ist aktiv, wenn `room_temperature.room_temperature_sensor` konfiguriert ist und `enable` fehlt oder `true` ist. `enable: false` deaktiviert sie ausdrücklich. Sie ist damit bereits beim ESPHome-Start logisch aktiviert; senden kann sie erst nach einem gültigen, frischen Temperaturwert von Home Assistant. | Nutzer |
| D7 | 0x0F ACK-/DCM-Emulation wird ausschließlich durch `dcm.0x0f_emulation: true` aktiviert. Fehlt der Wert, ist sie AUS. | Nutzer, explizite YAML-Option |
| D8 | Watchdog Standard 30 min, Bereich 0–120 min. Der wiederhergestellte Wert muss beim Boot explizit an den C++-Kern übergeben werden. | Nutzer, Repo-YAML |
| D9 | Watchdog nach Neustart streng: ohne frischen Wert keine Raumtemperaturantwort. Abweichung vom Repo, weil die Repo-Version nach Neustart mit einem wiederhergestellten Wert antwortet. | Nutzer (Option A), Repo-Befund siehe SAFETY.md |
| D10 | Eine Sollwert-Anforderung wird höchstens fünfmal in Raum-Polls übertragen und danach verworfen, sofern sie nicht bestätigt wurde. | Nutzer; genaue Anzahl bewusst festgelegt, Implementierung konsistent angepasst |
| D11 | Raumtemperatur gültig nur zwischen 5 und 35 °C, Sollwert zwischen 10 und 30 °C. | Repo-YAML |
| D12 | Warmwasser-Nachheizung ist ein Einmalauslöser (Wert 1 für eine Abfrage). | Repo-README |
| D13 | Umwälzpumpe: Relais GPIO47, Standard AUS nach jedem ESP-Neustart, sonst Zustand wie zuletzt von HA gesetzt. | Nutzer |
| D14 | Vorlauftemperatur ist Register `0xA7F8` (Regler-Block). Vom Nutzer bestätigt, keine weitere Prüfung nötig. | Nutzer |
| D15 | Warmwassertemperatur `0xA7FC` ist aktiv, wie im Repo. | Repo-Katalog |
| D16 | 0x0F-ACK-Emulation ist Teil des Projekts; Funktion und Aktivierung werden dokumentiert. | Nutzer |
| D17 | Diagnose-Entitäten und Kandidaten sind standardmäßig deaktiviert. | Nutzer (früher), Repo-Kandidatenstatus |
| D18 | Geräte pro Modbus-Slave: Regler (0x02), Zubehör (0x06), Raumregler (0x0A), DCM (0x0F), Außeneinheit (0x1E). Slaves 0x04, 0x14, 0xA4, 0xA5 ohne Gerät, weil das Repo sie nicht belegt. | Repo-Protokollübersicht |
| D19 | Sendezeiten: nach 5 ms Stille plus Repo-Vorlaufzeit, DE 200 µs vor dem Senden, DE 1200 µs nach dem Senden. | Repo-YAML |
| D20 | Die Logik liegt in einer reinen C++-Kernbibliothek mit Host-Tests. Die ESPHome-Glue-Schicht ist dünn. | Eigene Entscheidung, Begründung in PLAN |
| D21 | `room_temperature.room_temperature_sensor` referenziert eine ESPHome-`sensor::Sensor`-ID. Die HA-Entity wird durch einen separaten `platform: homeassistant`-Sensor ausgewählt. Fehlt `enable`, wird die Emulation genau dann aktiviert, wenn diese Sensorreferenz vorhanden und schema-valide ist. `enable: true` ohne Sensor ist ein Konfigurationsfehler. | Nutzer |
| D22 | `register_stale_after` wird in Sekunden angegeben. Standard `0` bedeutet keine automatische Invalidierung; ein positiver Wert macht Registerwerte nach Ablauf des Alters ungültig. Das Alter des ältesten gespeicherten Registerwerts wird separat diagnostisch bereitgestellt; auch interne Raumregler-Synchronisierung ignoriert abgelaufene Cachewerte. | Implementierungsentscheidung; Nutzerwunsch zur Veraltung |
| D23 | Die Komponente veröffentlicht Sensor-, Binär-, Text- und Climate-Zustände nur bei tatsächlicher Änderung. Diagnosewerte mit laufendem Alterszähler dürfen sich weiterhin regelmäßig ändern. | Nutzerwunsch |
| D24 | Prüfstand-Schritt 1 ist für die Softwarebearbeitung vorerst zurückgestellt. Die angenommene Pull-up-Logik 1 ist dokumentiert, gilt aber nicht als elektrische Sicherheitsprüfung; vor dem Anschluss ist die Messung weiterhin erforderlich. | Nutzer |
