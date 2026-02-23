from djvrt.capture import js_random_init_script, scenario_js_random_seed


def test_scenario_js_random_seed_is_stable() -> None:
    first = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-control")
    second = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-control")
    assert first == second


def test_scenario_js_random_seed_changes_with_scenario() -> None:
    first = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-control")
    second = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-variant")
    assert first != second


def test_js_random_init_script_uses_uint32_seed() -> None:
    script = js_random_init_script((1 << 40) + 5)
    assert "let state = 5 >>> 0;" in script
    assert "Math.random = () => {" in script
    assert "Math.imul(1664525, state)" in script
