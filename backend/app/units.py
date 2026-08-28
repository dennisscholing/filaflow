from decimal import Decimal, ROUND_HALF_UP


PI = Decimal("3.141592653589793")


def length_mm_to_weight_mg(length_mm: Decimal, diameter_mm: Decimal, density_g_cm3: Decimal) -> int:
    area_mm2 = PI * (diameter_mm / 2) ** 2
    volume_mm3 = length_mm * area_mm2
    weight_mg = volume_mm3 * density_g_cm3
    return int(weight_mg.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def weight_mg_to_length_mm(weight_mg: int, diameter_mm: Decimal, density_g_cm3: Decimal) -> Decimal:
    area_mm2 = PI * (diameter_mm / 2) ** 2
    if area_mm2 <= 0 or density_g_cm3 <= 0:
        return Decimal("0")
    return (Decimal(weight_mg) / (area_mm2 * density_g_cm3)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def grams_to_mg(value: Decimal) -> int:
    return int((value * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def mg_to_grams(value: int) -> float:
    return round(value / 1000, 3)
