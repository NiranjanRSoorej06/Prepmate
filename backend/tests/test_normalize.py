"""Output normalisation: everything the model returns is coerced to a known type."""

from __future__ import annotations

from ai.normalize import as_list, as_text, clamp_score, strip_chatty_prefix


class TestClampScore:
    def test_plain_int(self):
        assert clamp_score(8) == 8

    def test_string_number(self):
        assert clamp_score("8") == 8

    def test_score_out_of_ten(self):
        assert clamp_score("8/10") == 8

    def test_float(self):
        assert clamp_score(7.6) == 8

    def test_above_range_is_capped(self):
        assert clamp_score(42) == 10

    def test_below_range_is_floored(self):
        assert clamp_score(0) == 1
        assert clamp_score(-5) == 1

    def test_normalised_zero_to_one(self):
        assert clamp_score(0.8) == 8

    def test_garbage_uses_default(self):
        assert clamp_score("excellent", default=5) == 5
        assert clamp_score(None) == 5
        assert clamp_score([]) == 5

    def test_bool_is_not_a_score(self):
        assert clamp_score(True) == 5

    def test_nan(self):
        assert clamp_score(float("nan")) == 5


class TestAsList:
    def test_list_passthrough(self):
        assert as_list(["a", "b"]) == ["a", "b"]

    def test_newline_string(self):
        assert as_list("a\n- b\n- c") == ["a", "b", "c"]

    def test_bullets_stripped(self):
        assert as_list(["- a", "• b"]) == ["a", "b"]

    def test_none_and_empty(self):
        assert as_list(None) == []
        assert as_list([]) == []

    def test_dict_is_flattened(self):
        assert as_list({"speed": "fast"}) == ["speed: fast"]


class TestAsText:
    def test_string(self):
        assert as_text("hello") == "hello"

    def test_quotes_stripped(self):
        assert as_text('"hello"') == "hello"

    def test_default_applied_to_empty(self):
        assert as_text("", default="General") == "General"
        assert as_text(None, default="General") == "General"

    def test_list_joined(self):
        assert as_text(["a", "b"]) == "a b"


class TestStripChattyPrefix:
    def test_strips_prefixes(self):
        for raw in [
            "Okay, why did you choose that index?",
            "Ok, why did you choose that index?",
            "Question: why did you choose that index?",
            "Follow-up: why did you choose that index?",
            "Here's my question: why did you choose that index?",
        ]:
            assert strip_chatty_prefix(raw) == "why did you choose that index?"

    def test_leaves_clean_text_alone(self):
        assert strip_chatty_prefix("Why did you choose that index?") == "Why did you choose that index?"

    def test_repeated_prefixes(self):
        assert strip_chatty_prefix("Okay, Sure, why?") == "why?"
