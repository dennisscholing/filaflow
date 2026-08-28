from app.colors import CSS_COLORS, nearest_color


def test_uses_complete_local_css_palette():
    assert len(CSS_COLORS) > 100
    assert nearest_color("#ff0000") == ("Red", "#FF0000")


def test_nearest_color_is_deterministic_and_offline():
    name, matched = nearest_color("#663399")
    assert name == "Rebeccapurple"
    assert matched == "#663399"
