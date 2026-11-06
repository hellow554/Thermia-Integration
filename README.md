# Thermia iTec Eco für Home Assistant

Lokale Integration für die Thermia iTec Eco Wärmepumpe über den internen RS485-Bus, ohne Cloud.
Adressen und Abläufe stammen aus [ryckema/Thermia_itec](https://github.com/ryckema/Thermia_itec) (Dank an die Autoren und die Protokollforschung dort).

> **Status:** Mitlesen ist erprobt. Die Emulationen (Raumsensor, 0x0F ACK) sind implementiert, aber am echten Bus noch nicht
> abschließend geprüft. Nutzung auf eigene Verantwortung.

## Installation über HACS

1. HACS öffnen → drei Punkte → **Benutzerdefinierte Repositories**
2. URL: `https://github.com/hellow554/Thermia_integration.git`, Kategorie **Integration**
3. Thermia iTec Eco installieren, Home Assistant neu starten
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → „Thermia iTec Eco“
5. Port des USB-RS485-Adapters wählen (bevorzugt `/dev/serial/by-id/…`), optional den Raumtemperatursensor

Das alte Add-on, das denselben Port nutzt, muss vorher gestoppt sein.

## Geräte

Regler (0x02), Zubehör (0x06), Raumregler (0x0A), DCM / Online-Modul (0x0F), Außeneinheit (0x1E).
Eine vollständige Liste aller Entitäten mit Bus-Quelle steht in [docs/REGISTERS.md](docs/REGISTERS.md).

## Emulationen

- **Raumsensor-Emulation** (Standard AUS) antwortet auf die Abfragen des Reglers mit der Raumtemperatur.
- **0x0F ACK-Emulation** (Standard AN) quittiert Schreibvorgänge an das DCM-Modul.
- Beide sperren sich, wenn ein zweiter Teilnehmer auf dem Bus antwortet.

## Entwicklung

    python3 -m unittest discover -s tests -v
    python3 tools/build_translations.py
    python3 tools/build_register_docs.py

Übergabe für weitere Entwickler und KI-Agenten: [docs/HANDOVER.md](docs/HANDOVER.md), [AGENTS.md](AGENTS.md).

## Lizenz

MIT, siehe [LICENSE](LICENSE).
