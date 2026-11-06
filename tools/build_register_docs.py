#!/usr/bin/env python3
"""Regenerate docs/REGISTERS.md from the field catalogue. Run from the repository root."""
import importlib, pathlib, sys, types

ROOT = pathlib.Path(__file__).resolve().parents[1]
base = ROOT / "custom_components" / "thermia_itec_eco"
pkg = types.ModuleType("thermia_pure"); pkg.__path__ = [str(base)]; sys.modules["thermia_pure"] = pkg
fields = importlib.import_module("thermia_pure.fields")
rows = ["| Gerät (Slave) | Name (EN) | Quelle auf dem Bus | Art | Standard |", "|---|---|---|---|---|"]
for f in fields.FIELDS:
    state = "blockiert" if f.blocked else ("an" if f.enabled_default else "aus")
    rows.append(f"| {fields.device_of(f)} | {f.name_en} | `{f.source}` | {f.kind} | {state} |")
doc = ("# Register-Übersicht\n\nAutomatisch aus `fields.py` erzeugt (`python3 tools/build_register_docs.py`). Nicht von Hand ändern.\n\n"
       "Quelle der Adressen und Abläufe: ryckema/Thermia_itec, Ordner `Write (Beta)/iTec Eco`.\n\n" + "\n".join(rows) + "\n")
(ROOT / "docs" / "REGISTERS.md").write_text(doc, encoding="utf-8")
print("written", ROOT / "docs" / "REGISTERS.md")
