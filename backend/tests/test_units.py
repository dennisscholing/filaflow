from decimal import Decimal
from app.units import length_mm_to_weight_mg, weight_mg_to_length_mm


def test_length_weight_roundtrip():
    length = Decimal("330000")
    weight = length_mm_to_weight_mg(length, Decimal("1.75"), Decimal("1.24"))
    restored = weight_mg_to_length_mm(weight, Decimal("1.75"), Decimal("1.24"))
    assert abs(restored - length) < Decimal("1")


def test_one_meter_pla_is_about_three_grams():
    assert 2900 < length_mm_to_weight_mg(Decimal("1000"), Decimal("1.75"), Decimal("1.24")) < 3100
