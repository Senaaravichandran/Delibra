from verdictforge.providers import strip_hidden_reasoning


def test_hidden_reasoning_blocks_are_not_exposed() -> None:
    response = "<think>Private chain of thought.</think>\nThe concise public answer."

    assert strip_hidden_reasoning(response) == "The concise public answer."


def test_normal_answer_is_preserved() -> None:
    response = "A normal answer with <strong>legitimate markup</strong>."

    assert strip_hidden_reasoning(response) == response
