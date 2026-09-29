import json
import random
from pathlib import Path

from agents.scene_schema import CATALOGUE, ICONS, fixtures, repair_scene, validate_and_repair

ROOT = Path(__file__).resolve().parent.parent


def shot(scene, text="A line of narration about five gigabytes.", emphasis=None):
    return {"text": text, "emphasis": emphasis or [], "scene": scene}


def test_every_catalogue_example_is_valid_without_repairs():
    for name, c in CATALOGUE.items():
        repairs = []
        out = repair_scene({"type": name, "props": c["example"]}, {"text": "x", "emphasis": []}, name, repairs)
        assert out["type"] == name
        assert repairs == [], (name, repairs)


def test_long_text_is_trimmed_to_limit():
    script, repairs = validate_and_repair({"shots": [shot({"type": "key_point", "props": {"text": "word " * 40}})]})
    text = script["shots"][0]["scene"]["props"]["text"]
    assert len(text) <= 48 and text.endswith("…")
    assert any("trimmed" in r for r in repairs)


def test_unknown_scene_becomes_key_point_from_emphasis():
    script, repairs = validate_and_repair({"shots": [shot({"type": "hologram"}, emphasis=["five gigabytes"])]})
    sc = script["shots"][0]["scene"]
    assert sc["type"] == "key_point" and sc["props"]["text"] == "five gigabytes"
    assert any("unknown scene" in r for r in repairs)


def test_missing_required_prop_falls_back():
    script, _ = validate_and_repair({"shots": [shot({"type": "big_number", "props": {"label": "no value"}})]})
    assert script["shots"][0]["scene"]["type"] == "key_point"


def test_number_strings_are_coerced_and_lists_clamped():
    items = [{"label": f"m{i}", "value": f"{i} GB"} for i in range(9)]
    script, repairs = validate_and_repair({"shots": [shot({"type": "bar_chart", "props": {"title": "Sizes", "items": items}})]})
    props = script["shots"][0]["scene"]["props"]
    assert len(props["items"]) == 6 and props["items"][3]["value"] == 3.0
    assert any("items" in r for r in repairs)


def test_meter_value_clamped_and_bad_max_rejected():
    ok, _ = validate_and_repair({"shots": [shot({"type": "meter", "props": {"label": "RAM", "value": 40, "max": 16}})]})
    assert ok["shots"][0]["scene"]["props"]["value"] == 16
    bad, _ = validate_and_repair({"shots": [shot({"type": "meter", "props": {"label": "RAM", "value": 4, "max": 0}})]})
    assert bad["shots"][0]["scene"]["type"] == "key_point"


def test_emphasis_not_in_text_is_dropped_and_empty_shots_removed():
    script, repairs = validate_and_repair({"shots": [
        {"text": "", "scene": {}},
        shot({"type": "key_point", "props": {"text": "Hi"}}, text="Hello world", emphasis=["world", "missing"]),
    ]})
    assert len(script["shots"]) == 1 and script["shots"][0]["emphasis"] == ["world"]


def test_unknown_icon_replaced():
    script, _ = validate_and_repair({"shots": [shot({"type": "key_point", "props": {"text": "Hi", "icon": "unicorn"}})]})
    assert script["shots"][0]["scene"]["props"]["icon"] in ICONS


def _random_value(rng, depth=0):
    kinds = [None, "", "text " * rng.randint(0, 30), rng.randint(-5, 10**6), rng.random() * 1e5, True,
             [], {}, "12 GB", "nan", [{"label": "x"}] * rng.randint(0, 9)]
    if depth < 2:
        kinds.append({k: _random_value(rng, depth + 1) for k in ("label", "value", "text", "x", "y", "icon")})
        kinds.append([_random_value(rng, depth + 1) for _ in range(rng.randint(0, 8))])
    return rng.choice(kinds)


def test_fuzz_broken_specs_never_raise():
    rng = random.Random(1234)
    names = list(CATALOGUE) + ["nope", None, 7]
    for _ in range(500):
        stype = rng.choice(names)
        props = {k: _random_value(rng) for k in rng.sample(["headline", "text", "value", "items", "points",
                                                            "events", "messages", "lines", "left", "right",
                                                            "max", "label", "title", "icon"], 5)}
        scene = rng.choice([{"type": stype, "props": props}, {"type": stype}, stype, None, []])
        script, _ = validate_and_repair({"shots": [{"text": "some narration", "scene": scene}]})
        assert script["shots"][0]["scene"]["type"] in CATALOGUE


def test_remotion_fixtures_are_in_sync_with_catalogue():
    on_disk = json.loads((ROOT / "video/explainer/test/fixtures.json").read_text())
    assert on_disk == fixtures(), "run: python -m agents.scene_schema --fixtures > video/explainer/test/fixtures.json"


def test_remotion_registry_matches_catalogue():
    reg = (ROOT / "video/explainer/src/scenes/registry.tsx").read_text()
    for name in CATALOGUE:
        assert f"  {name}:" in reg, f"scene {name} missing from registry.tsx"
    icons = (ROOT / "video/explainer/src/icons.tsx").read_text()
    for icon in ICONS:
        assert (f" {icon}:" in icons) or (f'"{icon}":' in icons), f"icon {icon} missing from icons.tsx"


def test_e2e_fixture_script_covers_every_scene():
    script = json.loads((ROOT / "tests/fixtures/explainer_script.json").read_text())
    safe, repairs = validate_and_repair(script)
    assert repairs == []
    assert {s["scene"]["type"] for s in safe["shots"]} == set(CATALOGUE)
