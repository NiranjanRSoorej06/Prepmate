"""Resume Attack Mode and claim credibility."""

from __future__ import annotations

from ai import attack


class TestExtractClaims:
    def test_returns_normalised_claims(self, stub_gemma, sample_profile):
        stub_gemma(
            attack,
            {
                "claims": [
                    {
                        "claim": "Improved query latency with indexing",
                        "category": "Database",
                        "verifiability": 8,
                        "reason": "Names an optimisation with an outcome",
                    }
                ]
            },
        )

        claims = attack.extract_claims(sample_profile)

        assert len(claims) == 1
        assert claims[0]["claim"] == "Improved query latency with indexing"
        assert claims[0]["category"] == "Database"
        assert claims[0]["verifiability"] == 8

    def test_unknown_category_becomes_other(self, stub_gemma, sample_profile):
        stub_gemma(attack, {"claims": [{"claim": "x", "category": "Quantum"}]})

        assert attack.extract_claims(sample_profile)[0]["category"] == "Other"

    def test_malformed_response_yields_empty_pool(self, stub_gemma, sample_profile):
        stub_gemma(attack, {"nothing": "useful"})

        assert attack.extract_claims(sample_profile) == []

    def test_model_failure_yields_empty_pool(self, monkeypatch, sample_profile):
        def boom(*_args, **_kwargs):
            raise RuntimeError("ollama down")

        monkeypatch.setattr(attack, "ask_gemma_json", boom)

        assert attack.extract_claims(sample_profile) == []


class TestAttackQuestion:
    def test_returns_expected_shape(self, stub_gemma, sample_profile):
        stub_gemma(
            attack,
            {
                "claim": "Optimised database queries using indexing",
                "category": "Database",
                "question": "Which queries were slow, and what did you measure?",
                "why_it_matters": "Shows real measurement, not a guess",
                "difficulty": 7,
            },
        )

        result = attack.attack_question(sample_profile, "Backend Engineer")

        assert result["claim"] == "Optimised database queries using indexing"
        assert result["category"] == "Database"
        assert result["question"] == "Which queries were slow, and what did you measure?"
        assert result["valid"] is True
        assert result["mode"] == "Resume Attack"

    def test_already_attacked_claims_are_excluded(self, stub_gemma, sample_profile):
        calls = stub_gemma(attack, {"claim": "c", "question": "q", "category": "API"})

        attack.attack_question(
            sample_profile,
            "Backend Engineer",
            attacked_claims=["Optimised database queries"],
        )

        assert "Optimised database queries" in calls[0]["user"]

    def test_session_resume_text_is_grounding(self, stub_gemma, sample_profile):
        calls = stub_gemma(attack, {"claim": "c", "question": "q", "category": "API"})

        attack.attack_question(sample_profile, "Backend Engineer", resume_text="RAW RESUME BODY")

        assert "RAW RESUME BODY" in calls[0]["user"]

    def test_missing_question_is_invalid(self, stub_gemma, sample_profile):
        stub_gemma(attack, {"claim": "only a claim", "category": "API"})

        result = attack.attack_question(sample_profile, "Backend Engineer")

        assert result["valid"] is False

    def test_greeting_is_stripped(self, stub_gemma, sample_profile):
        stub_gemma(attack, {"claim": "c", "question": "Okay, which index did you add?", "category": "Database"})

        result = attack.attack_question(sample_profile, "Backend Engineer")

        assert result["question"] == "which index did you add?"


class TestEvaluateClaimDefence:
    def test_returns_expected_shape(self, stub_gemma):
        stub_gemma(
            attack,
            {
                "claim": "Optimised queries",
                "credibility_score": 8,
                "technical_depth": 7,
                "clarity": 9,
                "verdict": "Strong defence.",
                "evidence": ["Explained why the index helped"],
                "gaps": ["No measurement methodology"],
                "follow_up": "How did you measure it?",
            },
        )

        result = attack.evaluate_claim_defence(
            "Optimised queries",
            "Which queries did you optimise?",
            "I added an index on userId and createdAt.",
        )

        assert result["credibility_score"] == 8
        assert result["technical_depth"] == 7
        assert result["clarity"] == 9
        assert result["overall"] == 8.0
        assert result["evidence"] == ["Explained why the index helped"]
        assert result["follow_up"] == "How did you measure it?"

    def test_scores_are_clamped(self, stub_gemma):
        stub_gemma(attack, {"credibility_score": 99, "technical_depth": -3, "clarity": "n/a"})

        result = attack.evaluate_claim_defence("claim", "q", "a")

        assert 1 <= result["credibility_score"] <= 10
        assert 1 <= result["technical_depth"] <= 10
        assert 1 <= result["clarity"] <= 10

    def test_follow_up_is_never_empty(self, stub_gemma):
        # The report needs this to describe what was missing.
        stub_gemma(attack, {"credibility_score": 5, "follow_up": ""})

        result = attack.evaluate_claim_defence("claim", "q", "a")

        assert result["follow_up"].strip()

    def test_claim_falls_back_to_the_one_asked_about(self, stub_gemma):
        stub_gemma(attack, {"credibility_score": 6, "follow_up": "Why?"})

        result = attack.evaluate_claim_defence("The original claim", "q", "a")

        assert result["claim"] == "The original claim"

    def test_it_does_not_accuse_the_candidate(self, stub_gemma):
        # Framing is a product requirement: PrepMate measures defence of a
        # claim, it does not decide whether anyone lied.
        stub_gemma(attack, {"credibility_score": 2, "verdict": "Vague.", "follow_up": "Why?"})

        result = attack.evaluate_claim_defence("claim", "q", "a")

        reported = " ".join(
            [result["verdict"], *result["evidence"], *result["gaps"]]
        ).lower()

        for accusation in ("lying", "lied", "liar", "dishonest", "exaggerat", "fake"):
            assert accusation not in reported

        prompt = " ".join(attack.CREDIBILITY_SYSTEM_PROMPT.lower().split())

        assert "not deciding whether the candidate lied" in prompt
        assert "preparation and demonstrated technical depth" in prompt


class TestFraming:
    def test_attack_prompt_forbids_accusatory_framing(self):
        prompt = attack.ATTACK_SYSTEM_PROMPT.lower()

        assert "not accusing" in prompt
        assert "do not ask the candidate to repeat" in prompt
