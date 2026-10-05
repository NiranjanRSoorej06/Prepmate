"""Resume parsing, profiling, report generation and the session store."""

from __future__ import annotations

import pytest

from ai import report
from database import SessionStore
from resume import parser, profile


class TestParser:
    def test_empty_bytes_raise(self):
        with pytest.raises(parser.ResumeParseError):
            parser.extract_text_from_pdf(b"")

    def test_non_pdf_raises_a_readable_error(self):
        with pytest.raises(parser.ResumeParseError) as caught:
            parser.extract_text_from_pdf(b"this is definitely not a pdf")

        assert "pdf" in str(caught.value).lower()

    def test_real_pdf_text_layer(self):
        # A PDF PyMuPDF can actually read.
        source = parser.pymupdf.open()
        page = source.new_page()
        page.insert_text((72, 100), "Backend Software Engineer with FastAPI and MongoDB experience.")
        data = source.tobytes()
        source.close()

        text = parser.extract_text_from_pdf(data)

        assert "FastAPI" in text
        assert parser.is_ocr_only(data) is False

    def test_blank_pdf_returns_empty_text(self):
        source = parser.pymupdf.open()
        source.new_page()
        data = source.tobytes()
        source.close()

        assert parser.extract_text_from_pdf(data) == ""

    def test_ocr_failure_degrades_to_text_layer(self, monkeypatch):
        source = parser.pymupdf.open()
        page = source.new_page()
        page.insert_text((72, 100), "a" * 10)
        data = source.tobytes()
        source.close()

        monkeypatch.setattr(parser, "_ocr", lambda _image: "")

        # A thin text layer plus no OCR must still return the thin layer.
        assert parser.extract_text_from_pdf(data).startswith("a")


class TestProfileNormalisation:
    def test_missing_fields_get_defaults(self):
        result = profile.normalise_profile({})

        assert result["skills"] == []
        assert result["projects"] == []
        assert result["name"] == ""
        assert result["seniority"] == "student"

    def test_projects_are_structured(self):
        result = profile.normalise_profile(
            {"projects": [{"name": "App", "technologies": ["FastAPI", "MongoDB"]}]}
        )

        assert result["projects"][0]["name"] == "App"
        assert result["projects"][0]["technologies"] == ["FastAPI", "MongoDB"]

    def test_projects_as_a_single_object_are_wrapped(self):
        result = profile.normalise_profile({"projects": {"name": "Solo"}})

        assert result["projects"][0]["name"] == "Solo"

    def test_comma_separated_technologies_are_split(self):
        result = profile.normalise_profile(
            {"projects": [{"name": "App", "technologies": "FastAPI, MongoDB, JWT"}]}
        )

        assert result["projects"][0]["technologies"] == ["FastAPI", "MongoDB", "JWT"]

    def test_unknown_seniority_falls_back(self):
        assert profile.normalise_profile({"seniority": "guru"})["seniority"] == "student"

    def test_experience_months_are_bounded(self):
        assert profile.normalise_profile({"total_experience_months": 99999})[
            "total_experience_months"
        ] == 600
        assert profile.normalise_profile({"total_experience_months": "abc"})[
            "total_experience_months"
        ] == 0

    def test_empty_resume_text_raises(self):
        with pytest.raises(profile.ProfileError):
            profile.create_profile("   ")

    def test_empty_profile_raises_actionable_error(self, stub_gemma):
        stub_gemma(profile, {})

        with pytest.raises(profile.ProfileError) as caught:
            profile.create_profile("Jane Doe. jane@example.com")

        assert "resume" in str(caught.value).lower()


class TestReport:
    def test_requires_history(self):
        with pytest.raises(ValueError):
            report.generate_report([], {}, "Backend Engineer", "Technical")

    def test_returns_expected_shape(self, stub_gemma, sample_history, sample_profile):
        stub_gemma(
            report,
            {
                "overall_score": 7.4,
                "technical_accuracy": 7.8,
                "communication": 7.1,
                "depth": 7.3,
                "readiness": "nearly ready",
                "summary": "Solid technical base, shallow on measurement.",
                "strongest_areas": ["Indexing basics"],
                "weakest_areas": ["Measurement methodology"],
                "topics_to_revise": ["Index selectivity"],
                "claims_defended": [],
                "claims_needing_work": ["Optimised database queries using indexing"],
                "practice_plan": [
                    {"step": 1, "focus": "MongoDB", "action": "Read the index docs", "why": "flagged"}
                ],
                "next_interview_focus": ["Measurement"],
            },
        )

        result = report.generate_report(sample_history, sample_profile, "Backend Engineer", "Technical")

        assert result["overall_score"] == 7.4
        assert result["summary"].startswith("Solid")
        assert result["claims_needing_work"] == ["Optimised database queries using indexing"]
        assert result["practice_plan"][0]["action"] == "Read the index docs"
        assert result["degraded"] is False
        assert result["questions_asked"] == 2

    def test_scores_are_bounded(self, stub_gemma, sample_history, sample_profile):
        # Content is present, so this exercises the clamping path rather than
        # the degraded fallback.
        stub_gemma(
            report,
            {
                "overall_score": 99,
                "technical_accuracy": -4,
                "summary": "Solid but shallow.",
                "strongest_areas": ["APIs"],
            },
        )

        result = report.generate_report(sample_history, sample_profile, "Backend Engineer", "Technical")

        assert result["degraded"] is False
        assert 1.0 <= result["overall_score"] <= 10.0
        assert 1.0 <= result["technical_accuracy"] <= 10.0

    def test_empty_model_object_falls_back(self, stub_gemma, sample_history, sample_profile):
        # gemma3:4b collapses to a literal `{}` on a long transcript. That must
        # not produce a hollow report.
        stub_gemma(report, {})

        result = report.generate_report(sample_history, sample_profile, "Backend Engineer", "Technical")

        assert result["degraded"] is True
        assert result["summary"]
        assert result["practice_plan"]

    def test_transcript_includes_attack_claims(self, stub_gemma, sample_history, sample_profile):
        calls = stub_gemma(report, {"overall_score": 6})

        report.generate_report(sample_history, sample_profile, "Backend Engineer", "Resume Attack")

        prompt = calls[0]["user"]

        assert "Optimised database queries using indexing" in prompt
        assert "CREDIBILITY" in prompt

    def test_model_failure_falls_back_to_evaluation_data(self, monkeypatch, sample_history, sample_profile):
        def boom(*_args, **_kwargs):
            raise RuntimeError("ollama down")

        monkeypatch.setattr(report, "ask_gemma_json", boom)

        result = report.generate_report(sample_history, sample_profile, "Backend Engineer", "Technical")

        assert result["degraded"] is True
        assert result["overall_score"] > 0
        assert result["claims_needing_work"] == ["Optimised database queries using indexing"]
        assert result["practice_plan"]

    def test_text_rendering_contains_the_headline(self, stub_gemma, sample_history, sample_profile):
        stub_gemma(report, {"overall_score": 7.4, "strongest_areas": ["APIs"]})

        result = report.generate_report(sample_history, sample_profile, "Backend Engineer", "Technical")
        text = report.format_report_text(result)

        assert "PREPMATE INTERVIEW REPORT" in text
        assert "7.4 / 10" in text
        assert "STRONGEST AREAS" in text


class TestSessionStore:
    def test_round_trip(self):
        store = SessionStore()
        session = store.create("cv.pdf", "resume body", {"name": "A"})

        found = store.get(session.id)

        assert found is not None
        assert found.resume_text == "resume body"

    def test_public_dict_hides_resume_text(self):
        store = SessionStore()
        session = store.create("cv.pdf", "SECRET RESUME", {})

        assert "SECRET RESUME" not in str(session.public_dict())

    def test_missing_session_returns_none(self):
        assert SessionStore().get("nope") is None
        assert SessionStore().get("") is None

    def test_delete(self):
        store = SessionStore()
        session = store.create("cv.pdf", "x", {})

        assert store.delete(session.id) is True
        assert store.get(session.id) is None
        assert store.delete(session.id) is False

    def test_expired_sessions_are_pruned(self):
        store = SessionStore(ttl=0)
        store.create("cv.pdf", "x", {})

        assert store.get(store._sessions and next(iter(store._sessions))) is None

    def test_capacity_is_bounded(self):
        store = SessionStore()
        store._ttl = 10_000

        for index in range(60):
            store.create(f"cv{index}.pdf", "x", {})

        assert len(store._sessions) <= 50
