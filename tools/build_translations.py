#!/usr/bin/env python3
"""Regenerate strings.json and translations/*.json from fields.py.

Run from the project root:  python3 tools/build_translations.py
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components" / "thermia_itec_eco"

# Load the pure field module without importing Home Assistant.
_pkg = types.ModuleType("thermia_pure")
_pkg.__path__ = [str(BASE)]
sys.modules["thermia_pure"] = _pkg
fields = importlib.import_module("thermia_pure.fields")

CONFIG = {
    "en": {
        "step": {
            "user": {
                "title": "Thermia iTec Eco",
                "description": "Select the serial port of the USB-RS485 adapter. Setup sends no telegrams. Stop any running add-on that uses the same port first.",
                "data": {"port": "Serial port", "room_sensor_entity": "Room temperature sensor (optional)"},
            }
        },
        "error": {"cannot_open": "The port cannot be opened. Is it in use or is the adapter not connected?"},
        "abort": {"no_ports": "No serial port found.", "already_configured": "This port is already configured."},
    },
    "options_en": {
        "room_sensor_entity": "Room temperature sensor (forwarded to the heat pump)",
        "watchdog_minutes": "Watchdog: stop answering after this many minutes without a new value (0 = off)",
    },
    "options_de": {
        "room_sensor_entity": "Raumtemperatursensor (wird an die Wärmepumpe weitergegeben)",
        "watchdog_minutes": "Watchdog: nach so vielen Minuten ohne neuen Wert nicht mehr antworten (0 = aus)",
    },
    "de": {
        "step": {
            "user": {
                "title": "Thermia iTec Eco",
                "description": "Wähle den seriellen Port des USB-RS485-Adapters. Die Einrichtung sendet keine Telegramme. Ein eventuell laufendes Add-on, das denselben Port nutzt, muss vorher gestoppt sein.",
                "data": {"port": "Serieller Port", "room_sensor_entity": "Raumtemperatursensor (optional)"},
            }
        },
        "error": {"cannot_open": "Der Port kann nicht geöffnet werden. Ist er belegt oder der Adapter nicht angeschlossen?"},
        "abort": {"no_ports": "Kein serieller Port gefunden.", "already_configured": "Dieser Port ist bereits eingerichtet."},
    },
}


def build(lang: str) -> dict:
    sensors: dict[str, dict] = {}
    binaries: dict[str, dict] = {}
    others: dict[str, dict] = {}
    for f in fields.FIELDS:
        if f.blocked:
            continue
        name = f.name_en if lang == "en" else f.name_de
        target = binaries if f.kind == "binary" else sensors
        assert f.key not in target and f.key not in fields.BUS_ENTITY_NAMES, f.key
        target[f.key] = {"name": name}
    for key, (en, de) in fields.BUS_ENTITY_NAMES.items():
        sensors[key] = {"name": en if lang == "en" else de}
    for platform, entries in fields.PLATFORM_ENTITY_NAMES.items():
        for key, (en, de) in entries.items():
            others.setdefault(platform, {})[key] = {"name": en if lang == "en" else de}
    config = dict(CONFIG[lang])
    config["options"] = {
        "step": {
            "init": {
                "title": "Thermia iTec Eco",
                "data": {k: (v if lang == "en" else v) for k, v in
                         (CONFIG["options_" + lang]).items()},
            }
        }
    }
    entity = {
        "sensor": dict(sorted(sensors.items())),
        "binary_sensor": dict(sorted(binaries.items())),
    }
    entity.update({p: dict(sorted(v.items())) for p, v in others.items()})
    return {"config": config, "entity": entity}


def main() -> None:
    (BASE / "translations").mkdir(exist_ok=True)
    en = build("en")
    de = build("de")
    (BASE / "strings.json").write_text(json.dumps(en, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (BASE / "translations" / "en.json").write_text(json.dumps(en, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (BASE / "translations" / "de.json").write_text(json.dumps(de, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"sensors: {len(en['entity']['sensor'])}, binary: {len(en['entity']['binary_sensor'])}")


if __name__ == "__main__":
    main()
