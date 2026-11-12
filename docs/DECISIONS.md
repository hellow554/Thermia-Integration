# Entscheidungen

Jede Entscheidung nennt die Quelle. Änderungen nur nach Rücksprache mit dem Nutzer.

| # | Entscheidung | Quelle |
|---|---|---|
| D1 | Repo `ryckema/Thermia_itec` ist die Quelle der Wahrheit für Adressen, Skalierung, Zeiten und Abläufe. | Nutzer |
| D2 | Zielplattform ist ESPHome auf dem Waveshare ESP32-S3-Relay-1CH, Ersatz für die Python-Integration. | Nutzer |
| D3 | Eigene Custom-Komponente (C++), keine Lambdas für Bus-Logik. | Nutzer |
| D4 | Ziel-ESPHome-Version 2026.10 (aktuelles Patch-Release 2026.10.1). | Nutzer, ESPHome-Changelog |
| D5 | Pins: TX GPIO17, RX GPIO18, Freigabe DE/RE GPIO21, Relais GPIO47. | Nutzer, Schaltplan |
| D6 | Raumsensor-Emulation (0x0A) startet AUS nach jedem Neustart. | Repo-README §3, YAML `RESTORE_DEFAULT_OFF` |
| D7 | 0x0F ACK-Emulation startet AN. | Repo-YAML `RESTORE_DEFAULT_ON` |
| D8 | Watchdog Standard 30 min, Bereich 0–120 min. | Repo-YAML |
| D9 | Watchdog nach Neustart streng: ohne frischen Wert keine Antwort. Abweichung vom Repo, weil die Repo-Version nach Neustart mit einem wiederhergestellten Wert antwortet. | Nutzer (Option A), Repo-Befund siehe SAFETY.md |
| D10 | Sollwert-Anforderung wird nach 5 Abfragen ohne Bestätigung verworfen. | Repo-YAML |
| D11 | Raumtemperatur gültig nur zwischen 5 und 35 °C, Sollwert zwischen 10 und 30 °C. | Repo-YAML |
| D12 | Warmwasser-Nachheizung ist ein Einmalauslöser (Wert 1 für eine Abfrage). | Repo-README |
| D13 | Umwälzpumpe: Relais GPIO47, Standard AUS nach jedem ESP-Neustart, sonst Zustand wie zuletzt von HA gesetzt. | Nutzer |
| D14 | Vorlauftemperatur ist Register `0xA7F8` (Regler-Block). Vom Nutzer bestätigt, keine weitere Prüfung nötig. | Nutzer |
| D15 | Warmwassertemperatur `0xA7FC` ist aktiv, wie im Repo. | Repo-Katalog |
| D16 | 0x0F-ACK-Emulation ist Teil des Projekts, mit Hinweis in der Dokumentation. | Nutzer |
| D17 | Diagnose-Entitäten und Kandidaten sind standardmäßig deaktiviert. | Nutzer (früher), Repo-Kandidatenstatus |
| D18 | Geräte pro Modbus-Slave: Regler (0x02), Zubehör (0x06), Raumregler (0x0A), DCM (0x0F), Außeneinheit (0x1E). Slaves 0x04, 0x14, 0xA4, 0xA5 ohne Gerät, weil das Repo sie nicht belegt. | Repo-Protokollübersicht |
| D19 | Sendezeiten: nach 5 ms Stille plus Repo-Vorlaufzeit, DE 200 µs vor dem Senden, DE 1200 µs nach dem Senden. | Repo-YAML |
| D20 | Die Logik liegt in einer reinen C++-Kernbibliothek mit Host-Tests. Die ESPHome-Glue-Schicht ist dünn. | Eigene Entscheidung, Begründung in PLAN |
