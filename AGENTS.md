# Hinweise für KI-Agenten und Entwickler

Dieses Repository ist eine ESPHome-Komponente für die Thermia iTec Eco (über RS485) auf dem Waveshare ESP32-S3-Relay-1CH.

## Vor der Arbeit

1. Lies `docs/HANDOVER.md`, `docs/DECISIONS.md` und `docs/SAFETY.md`.
2. Antworte dem Nutzer auf Deutsch.

## Harte Regeln

- **Quelle der Wahrheit:** Das Repo `ryckema/Thermia_itec` (Ordner `Write (Beta)/iTec Eco`). Adressen, Skalierung,
  Zeiten und Abläufe kommen von dort. Erfinde kein Protokollverhalten. Wenn etwas unklar ist, markiere es als offen und frage nach.
- **Keine Sendung ohne Freigabe:** Änderungen am Sendepfad (`handle_tx`, `TxScheduler`, Emulationen) nur, wenn der Nutzer
  den Prüfstand-Schritt bestätigt hat. Bei Zweifeln nicht senden.
- **Boot-Zustand:** Den Pin GPIO21 (DE) nicht so verändern, dass er beim Start höher liegt als vorher. Siehe SAFETY.md, Abschnitt 1.
- **Pumpe:** Das Relais (GPIO47) bleibt nach jedem Neustart AUS. Keine Automation, die die Pumpe ohne Nutzerbefehl einschaltet.
- **Register nur im Katalog:** `components/thermia_bus/catalogue.py` ist die einzige Quelle. Danach
  `python3 tools/gen.py` ausführen. Generierte Dateien nie von Hand ändern.
- **Tests vor jeder Übergabe:** `bash tests/run_tests.sh` muss grün sein.
- **Keine Geheimnisse im Repo:** `config/secrets.yaml` ist ignoriert. Nur `secrets.yaml.example` committen.

## Architektur in einem Satz

`thermia_core` (reines C++, testbar) macht das Protokoll. `thermia_bus` (ESPHome-Glue) verbindet UART, Pins und Entitäten.
Python-Dateien in `components/thermia_bus` validieren nur die YAML-Konfiguration.

## Typische Aufgaben

- Neues Feld: Eintrag in `catalogue.py` mit Quelle, dann `tools/gen.py`, dann Test in `tests/test_core.cpp`.
- Neuer Diagnosewert: `DIAG_SENSORS` in `catalogue.py` und `diag_id`/`diag_value` in `thermia_bus.cpp`.
- Neue Entität in YAML: nur in `config/` ergänzen, keine Generatorausgabe editieren.
