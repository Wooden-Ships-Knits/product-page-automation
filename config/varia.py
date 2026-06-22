"""
tempat variable untuk berbagai macam perubahan mulai dari nama sheet dll
"""
IM_header = 56
season = "26 Spring"

Style = "KELLY TOP LIGHTWEIGHT"
Color = ["BLUE HEAVEN"]
production_type = "fixed"

# ============================================================
#  Report Launcher override (auto-integration)
#  If the dashboard wrote launcher_params.json next to this file, use those
#  values instead of the ones above. Editing this file by hand still works
#  whenever the dashboard isn't used.
# ============================================================
import json as _json, os as _os
_lp = _os.path.join(_os.path.dirname(__file__), "launcher_params.json")
if _os.path.exists(_lp):
    try:
        with open(_lp, encoding="utf-8") as _f:
            _ov = _json.load(_f)
        season = str(_ov.get("season", season)).strip()
        Style = str(_ov.get("Style", Style)).strip()
        _color = _ov.get("Color", Color)
        if isinstance(_color, list):
            Color = [str(c).strip() for c in _color if str(c).strip()]
        else:
            Color = [str(_color).strip()] if str(_color).strip() else []
        production_type = str(_ov.get("production_type", production_type)).strip()
    except Exception as _e:
        print(f"[launcher] could not read {_lp}: {_e}")

# Build data AFTER applying any override, so the dashboard values take effect.
# (Building it earlier would freeze in the hardcoded defaults above.)
data = [
    {
    "Styles": Style,
    "Colors": Color,
    "Production": production_type
        },
]