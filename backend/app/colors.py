"""Deterministic, offline HEX-to-name suggestions."""
from __future__ import annotations

import math
import re

from PIL import ImageColor

DISPLAY_NAMES = {
    "darkgray": "Dark gray", "dimgray": "Dim gray", "lightgray": "Light gray",
    "whitesmoke": "White smoke", "darkred": "Dark red", "orangered": "Orange red",
    "saddlebrown": "Saddle brown", "darkgreen": "Dark green", "limegreen": "Lime green",
    "mintcream": "Mint cream", "skyblue": "Sky blue", "steelblue": "Steel blue",
    "hotpink": "Hot pink",
}


def _css_palette() -> dict[str, str]:
    colors: dict[str, str] = {}
    for token, value in ImageColor.colormap.items():
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            continue
        # CSS contains gray/grey aliases. Keep one stable English spelling.
        if "grey" in token and token.replace("grey", "gray") in ImageColor.colormap:
            continue
        name = DISPLAY_NAMES.get(token, token[:1].upper() + token[1:])
        colors[name] = value.upper()
    return colors


CSS_COLORS = _css_palette()
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _lab(hex_value: str) -> tuple[float, float, float]:
    rgb = [int(hex_value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [((value + 0.055) / 1.055) ** 2.4 if value > 0.04045 else value / 12.92 for value in rgb]
    x = (linear[0] * 0.4124 + linear[1] * 0.3576 + linear[2] * 0.1805) / 0.95047
    y = linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722
    z = (linear[0] * 0.0193 + linear[1] * 0.1192 + linear[2] * 0.9505) / 1.08883
    transform = lambda value: value ** (1 / 3) if value > 0.008856 else 7.787 * value + 16 / 116
    fx, fy, fz = transform(x), transform(y), transform(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def nearest_color(hex_value: str) -> tuple[str, str]:
    value = hex_value.strip().upper()
    if not HEX_RE.fullmatch(value):
        raise ValueError("Color must be a six-digit HEX value")
    target = _lab(value)
    name, matched = min(
        CSS_COLORS.items(),
        key=lambda item: math.sqrt(sum((left - right) ** 2 for left, right in zip(target, _lab(item[1])))),
    )
    return name, matched
