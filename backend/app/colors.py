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
    name, matched = min(
        CSS_COLORS.items(),
        key=lambda item: color_distance(value, item[1]),
    )
    return name, matched


def color_distance(left_hex: str, right_hex: str) -> float:
    """CIEDE2000 distance between two six-digit sRGB colors."""
    left, right = left_hex.strip().upper(), right_hex.strip().upper()
    if not HEX_RE.fullmatch(left) or not HEX_RE.fullmatch(right):
        raise ValueError("Color must be a six-digit HEX value")
    l1, a1, b1 = _lab(left)
    l2, a2, b2 = _lab(right)
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7)))
    ap1, ap2 = (1 + g) * a1, (1 + g) * a2
    cp1, cp2 = math.hypot(ap1, b1), math.hypot(ap2, b2)

    def hue(a: float, b: float) -> float:
        value = math.degrees(math.atan2(b, a))
        return value + 360 if value < 0 else value

    hp1, hp2 = hue(ap1, b1), hue(ap2, b2)
    delta_l, delta_c = l2 - l1, cp2 - cp1
    if cp1 * cp2 == 0:
        delta_h_degrees = 0
    elif abs(hp2 - hp1) <= 180:
        delta_h_degrees = hp2 - hp1
    elif hp2 <= hp1:
        delta_h_degrees = hp2 - hp1 + 360
    else:
        delta_h_degrees = hp2 - hp1 - 360
    delta_h = 2 * math.sqrt(cp1 * cp2) * math.sin(math.radians(delta_h_degrees / 2))
    l_bar, cp_bar = (l1 + l2) / 2, (cp1 + cp2) / 2
    if cp1 * cp2 == 0:
        hp_bar = hp1 + hp2
    elif abs(hp1 - hp2) <= 180:
        hp_bar = (hp1 + hp2) / 2
    elif hp1 + hp2 < 360:
        hp_bar = (hp1 + hp2 + 360) / 2
    else:
        hp_bar = (hp1 + hp2 - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hp_bar - 30)) + 0.24 * math.cos(math.radians(2 * hp_bar))
         + 0.32 * math.cos(math.radians(3 * hp_bar + 6)) - 0.20 * math.cos(math.radians(4 * hp_bar - 63)))
    sl = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    sc = 1 + 0.045 * cp_bar
    sh = 1 + 0.015 * cp_bar * t
    rt = -2 * math.sqrt(cp_bar ** 7 / (cp_bar ** 7 + 25 ** 7)) * math.sin(
        math.radians(60 * math.exp(-((hp_bar - 275) / 25) ** 2))
    )
    return math.sqrt((delta_l / sl) ** 2 + (delta_c / sc) ** 2 + (delta_h / sh) ** 2 + rt * (delta_c / sc) * (delta_h / sh))
