# Hinweise für KI-Agenten

Dieses Repository ist eine Home-Assistant-Integration für die Thermia iTec Eco. Lies zuerst `docs/HANDOVER.md`.

- Antworte dem Nutzer auf Deutsch.
- **Das Repo `ryckema/Thermia_itec` ist die Quelle der Wahrheit** für Adressen, Skalierung, Zeiten und Abläufe.
  Erfinde kein Protokollverhalten. Unklare Punkte als offen markieren und nachfragen.
- Vor jeder Änderung an Sendepfad oder Emulation: Tests laufen lassen und das Risiko am Bus benennen.
- Keine Entitäten aktivieren, die im Repo als Kandidat oder Diagnose markiert sind.
- Nach Änderungen an `fields.py`: `python3 tools/build_translations.py` und `python3 tools/build_register_docs.py` ausführen.
- Die HA-Module (`sensor.py`, `climate.py`, …) lassen sich hier nicht importieren. Nur `py_compile`.
