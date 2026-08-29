from app.colors import CSS_COLORS, color_distance, nearest_color


def test_uses_complete_local_css_palette():
    assert len(CSS_COLORS) > 100
    assert nearest_color("#ff0000") == ("Red", "#FF0000")


def test_nearest_color_is_deterministic_and_offline():
    name, matched = nearest_color("#663399")
    assert name == "Rebeccapurple"
    assert matched == "#663399"


def test_ciede2000_distance_is_symmetric_and_exact_for_same_color():
    assert color_distance("#123456", "#123456") == 0
    assert color_distance("#FF0000", "#00FF00") == color_distance("#00FF00", "#FF0000")
