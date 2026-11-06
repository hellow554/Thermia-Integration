"""Load the integration's pure modules without importing Home Assistant."""
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components" / "thermia_itec_eco"

if "thermia_pure" not in sys.modules:
    _pkg = types.ModuleType("thermia_pure")
    _pkg.__path__ = [str(BASE)]
    sys.modules["thermia_pure"] = _pkg
