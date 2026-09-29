from agents.fact_check import numbers_in, unsupported_numbers


def test_numbers_normalized():
    assert numbers_in("It costs $1,200 and is 16.0% faster, 5 GB") == {"1200", "16", "5"}


def test_invented_number_is_flagged_but_sourced_and_small_ones_pass():
    script = {"shots": [
        {"text": "An 8 billion parameter model needs about 5 gigabytes.", "scene": {"type": "big_number", "props": {"value": 5, "decimals": "0"}}},
        {"text": "It is 73% faster.", "scene": {"type": "key_point", "props": {"text": "73% faster"}}},
        {"text": "Released in 2024.", "scene": {"type": "key_point", "props": {"text": "Since 2024"}}},
    ]}
    flags = unsupported_numbers(script, "Models released in 2024 are small.")
    assert {f["number"] for f in flags} == {"73"}
    assert {f["where"] for f in flags} == {"narration", "scene"}
