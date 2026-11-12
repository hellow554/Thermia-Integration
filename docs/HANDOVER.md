# Übergabe

Für weitere Entwickler und KI-Agenten. Vor dem Arbeiten AGENTS.md lesen.

## Was existiert

- Protokollkern in C++ mit 89 Host-Tests (`bash tests/run_tests.sh`).
- Registerkatalog in `components/thermia_bus/catalogue.py` mit 78 Feldern und 8 Diagnosewerten.
- Generator `tools/gen.py` für `registers_gen.cpp`, `docs/REGISTERS.md` und `config/entities/thermia_entities.yaml`.
- ESPHome-Komponente, Plattformen und Gerätekonfiguration (noch nicht kompiliert).
- Dokumentation: SAFETY, BENCH_TEST, DECISIONS, PLAN.

## Was fehlt

- ESPHome-Kompilierung und -Test (CI-Job vorhanden, muss laufen).
- Dry-Run-Schalter (Protokoll ohne Senden), damit der Prüfstand Schritt 3 machen kann.
- Prüfstand: Bus-Zustand beim Einschalten (SAFETY.md, Abschnitt 1) ist offen. Das ist der Blocker für den Anschluss.

## Regeln für Änderungen

- Register nur über `catalogue.py` ändern, dann `python3 tools/gen.py` und `bash tests/run_tests.sh`.
- Keine Zahl ohne Quelle im Repo. Die Quelle gehört in die Kommentarzeile des Feldes.
- Sendepfad nur ändern, wenn Schritt 1 des Prüfstands bestanden ist.
