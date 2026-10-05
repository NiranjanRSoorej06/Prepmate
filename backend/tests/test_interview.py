"""Interview engine: question generation and answer evaluation."""

from __future__ import annotations

import pytest

from ai import evaluator, interviewer
from ai.gemma import InvalidModelOutputError, ModelTimeoutError, ModelUnavailableError


class TestGenerateQuestion:
    def test_returns_expected_shape(self, stub_gemma, sample_profile):
        stub_gemma(
            interviewer,
            {
                "question": "How would you index this collection?",
                "topic": "Database",
                "difficulty": 6,
                "targets_weakness": False,
            },
        )

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

        assert result["question"] == "How would you index this collection?"
        assert result["topic"] == "Database"
        assert result["difficulty"] == 6
        assert result["degraded"] is False
        assert result["mode"] == "Technical"

    def test_history_is_sent_to_the_model(self, stub_gemma, sample_profile):
        calls = stub_gemma(interviewer, {"question": "Next?", "topic": "API", "difficulty": 5})

        interviewer.generate_question(
            sample_profile,
            "Backend Engineer",
            "Technical",
            history=[
                {
                    "question": "Explain indexes.",
                    "answer": "They speed up reads.",
                    "evaluation": {"depth": 3, "weaknesses": ["no measurement"]},
                    "topic": "Database",
                }
            ],
        )

        prompt = calls[0]["user"]

        assert "Explain indexes." in prompt
        assert "no measurement" in prompt
        assert "Database" in prompt

    def test_legacy_previous_questions_are_accepted(self, stub_gemma, sample_profile):
        calls = stub_gemma(interviewer, {"question": "Next?", "topic": "API"})

        interviewer.generate_question(
            sample_profile,
            "Backend Engineer",
            "Technical",
            previous_questions=["First question?"],
            previous_answers=["First answer."],
        )

        assert "First question?" in calls[0]["user"]
        assert "First answer." in calls[0]["user"]

    def test_greeting_is_stripped(self, stub_gemma, sample_profile):
        stub_gemma(interviewer, {"question": "Okay, what does an index do?"})

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

        assert result["question"] == "what does an index do?"

    def test_difficulty_is_clamped(self, stub_gemma, sample_profile):
        stub_gemma(interviewer, {"question": "Why?", "difficulty": 99})

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

        assert result["difficulty"] == 10

    def test_garbage_difficulty_falls_back(self, stub_gemma, sample_profile):
        stub_gemma(interviewer, {"question": "Why?", "difficulty": "hard"})

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

        assert result["difficulty"] == 5

    def test_alternate_question_key_is_accepted(self, stub_gemma, sample_profile):
        stub_gemma(interviewer, {"text": "Where does auth happen?"})

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

        assert result["question"] == "Where does auth happen?"

    def test_unparseable_output_degrades_gracefully(self, stub_gemma, sample_profile):
        # The critical guarantee: a bad model response must never kill the
        # interview turn.
        stub_gemma(interviewer, {})

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

        assert result["degraded"] is True
        assert result["question"]

    def test_malformed_json_degrades_gracefully(self, monkeypatch, sample_profile):
        # A confusing reply should not kill the turn.
        def bad(*_args, **_kwargs):
            raise InvalidModelOutputError("not json")

        monkeypatch.setattr(interviewer, "ask_gemma_json", bad)

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

        assert result["degraded"] is True
        assert result["question"]

    def test_dead_model_is_reported_not_hidden(self, monkeypatch, sample_profile):
        # A fallback question would mask the fact that Ollama is not running.
        def down(*_args, **_kwargs):
            raise ModelUnavailableError()

        monkeypatch.setattr(interviewer, "ask_gemma_json", down)

        with pytest.raises(ModelUnavailableError):
            interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

    def test_timeout_is_reported_not_hidden(self, monkeypatch, sample_profile):
        def slow(*_args, **_kwargs):
            raise ModelTimeoutError(600)

        monkeypatch.setattr(interviewer, "ask_gemma_json", slow)

        with pytest.raises(ModelTimeoutError):
            interviewer.generate_question(sample_profile, "Backend Engineer", "Technical")

    def test_unknown_mode_falls_back_to_technical(self, stub_gemma, sample_profile):
        stub_gemma(interviewer, {"question": "Why?"})

        result = interviewer.generate_question(sample_profile, "Backend Engineer", "Nonsense Mode")

        assert result["mode"] == "Technical"


class TestEvaluateAnswer:
    def test_returns_expected_shape(self, stub_gemma, sample_profile):
        stub_gemma(
            evaluator,
            {
                "technical_accuracy": 8,
                "communication": 7,
                "depth": 6,
                "verdict": "Good answer.",
                "topic": "Database",
                "strengths": ["Named the mechanism"],
                "weaknesses": ["No trade-offs"],
                "follow_up": "What trade-off did you accept?",
                "topics_to_revise": ["Index selectivity"],
            },
        )

        result = evaluator.evaluate_answer(
            "How do indexes work?",
            "They avoid a scan.",
            sample_profile,
        )

        assert result["technical_accuracy"] == 8
        assert result["communication"] == 7
        assert result["depth"] == 6
        assert result["overall"] == 7.0
        assert result["strengths"] == ["Named the mechanism"]
        assert result["follow_up"] == "What trade-off did you accept?"

    def test_scores_are_always_in_range(self, stub_gemma, sample_profile):
        stub_gemma(
            evaluator,
            {"technical_accuracy": 0, "communication": 55, "depth": "great", "follow_up": "Why?"},
        )

        result = evaluator.evaluate_answer("Q", "A", sample_profile)

        for key in ("technical_accuracy", "communication", "depth"):
            assert 1 <= result[key] <= 10

    def test_follow_up_is_never_empty(self, stub_gemma, sample_profile):
        # The adaptive loop depends on this: an empty follow_up would fall back
        # to an unrelated question.
        stub_gemma(evaluator, {"technical_accuracy": 5, "follow_up": ""})

        result = evaluator.evaluate_answer("Q", "A", sample_profile)

        assert result["follow_up"].strip()

    def test_follow_up_prefix_is_stripped(self, stub_gemma, sample_profile):
        stub_gemma(evaluator, {"follow_up": "Follow-up: why did you choose that?"})

        result = evaluator.evaluate_answer("Q", "A", sample_profile)

        assert result["follow_up"] == "why did you choose that?"

    def test_malformed_lists_are_coerced(self, stub_gemma, sample_profile):
        stub_gemma(
            evaluator,
            {"strengths": "clear\nstructured", "weaknesses": None, "follow_up": "Why?"},
        )

        result = evaluator.evaluate_answer("Q", "A", sample_profile)

        assert result["strengths"] == ["clear", "structured"]
        assert result["weaknesses"] == []

    def test_empty_response_gets_defaults(self, stub_gemma, sample_profile):
        stub_gemma(evaluator, {})

        result = evaluator.evaluate_answer("Q", "A", sample_profile)

        assert result["topic"] == "General"
        assert result["technical_accuracy"] == 5
        assert result["follow_up"]

    def test_interview_type_is_passed_through(self, stub_gemma, sample_profile):
        calls = stub_gemma(evaluator, {"follow_up": "Why?"})

        evaluator.evaluate_answer("Q", "A", sample_profile, interview_type="DSA")

        assert "DSA" in calls[0]["user"]
