from agents.fact_check import numbers_in, unsupported_numbers


def test_numbers_normalized():
    assert numbers_in("It costs $1,200 and is 16.0% faster, 5 GB") == {"1200", "16", "5"}


def test_invented_number_is_flagged_but_sourced_and_small_ones_pass():
    script = {"shots": [
        {"text": "An 8 billion parameter model needs about 5 gigabytes.", "scene": {"type": "key_point", "props": {"text": "5 GB is enough"}}},
        {"text": "It is 73% faster.", "scene": {"type": "key_point", "props": {"text": "73% faster"}}},
        {"text": "Released in 2024.", "scene": {"type": "key_point", "props": {"text": "Since 2024"}}},
    ]}
    flags = unsupported_numbers(script, "Models released in 2024 are small.")
    assert {f["number"] for f in flags} == {"73"}
    assert {f["where"] for f in flags} == {"narration", "scene"}


def test_chart_numbers_get_no_small_number_pass():
    # A bar chart is its numbers: an invented "4 GB" bar is flagged even though 4 is small.
    script = {"shots": [
        {"text": "Load the parts separately.", "scene": {"type": "bar_chart", "props": {
            "title": "Memory", "unit": "GB", "items": [{"label": "Model", "value": 4}, {"label": "VAE", "value": 2}]}}},
        {"text": "Use three steps.", "scene": {"type": "key_point", "props": {"text": "3 steps"}}},
    ]}
    flags = unsupported_numbers(script, "The model needs 2 GB.")
    assert [(f["shot"], f["number"]) for f in flags] == [(0, "4")]


def test_invented_terminal_commands_are_flagged():
    src = "Start it with `python main.py --lowvram`. Models go in models/checkpoints."
    script = {"shots": [
        {"text": "Launch it.", "scene": {"type": "terminal", "props": {"lines": ["$ python main.py --lowvram"]}}},
        {"text": "Launch it.", "scene": {"type": "terminal", "props": {"lines": ["$ comfyui --stream-weights", "ok"]}}},
    ]}
    flags = unsupported_numbers(script, src)
    assert [(f["shot"], f["number"], f["where"]) for f in flags] == [
        (1, "comfyui", "command"), (1, "--stream-weights", "command")]


def test_command_arguments_are_checked_but_everyday_shell_words_are_not():
    from agents.fact_check import command_words
    assert command_words("$ ollama pull gpt-oss-20b") == ["ollama", "pull", "gpt-oss-20b"]
    assert command_words("$ pip install -U open-webui") == ["open-webui"]
    assert command_words("$ curl -d '{\"model\": \"x\"}' http://x") == []
    script = {"shots": [{"text": "Pull it.", "scene": {"type": "terminal", "props": {"lines": ["$ ollama pull gpt-oss-20b"]}}}]}
    assert [f["number"] for f in unsupported_numbers(script, "Run: ollama pull gpt-oss:20b")] == ["gpt-oss-20b"]
