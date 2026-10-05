"""HTTP surface: routes, status codes and error mapping.

Every model call is stubbed, so this exercises the API contract without
needing Ollama.
"""

from __future__ import annotations

import pymupdf
import pytest
from fastapi.testclient import TestClient

import main
from ai import attack, evaluator, interviewer, report


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


class TestMeta:
    def test_root(self, client):
        body = client.get("/").json()

        assert "running" in body["message"]
        assert body["runtime"] == "ollama"

    def test_health_reports_local_only(self, client, monkeypatch):
        monkeypatch.setattr(main, "health", lambda: {"model": "gemma3:4b", "available": True, "local_only": True})

        assert client.get("/api/health").json()["local_only"] is True

    def test_health_503_when_model_is_down(self, client, monkeypatch):
        monkeypatch.setattr(main, "health", lambda: {"model": "gemma3:4b", "available": False, "local_only": True})

        assert client.get("/api/health").status_code == 503

    def test_modes_include_every_interview_style(self, client):
        labels = {mode["label"] for mode in client.get("/api/modes").json()["modes"]}

        assert {"Technical", "DSA", "Project Deep Dive", "Behavioral"} <= labels

    def test_modes_have_focus_metadata(self, client):
        for mode in client.get("/api/modes").json()["modes"]:
            assert mode["focus"]
            assert mode["topics"]


class TestQuestion:
    def test_generates_a_question(self, client, monkeypatch):
        monkeypatch.setattr(
            interviewer,
            "ask_gemma_json",
            lambda *a, **k: {"question": "Why that index?", "topic": "Database", "difficulty": 6},
        )

        response = client.post(
            "/api/interview/question",
            json={"resume_profile": {"skills": ["MongoDB"]}, "role": "Backend", "interview_type": "Technical"},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["question"] == "Why that index?"
        assert body["topic"] == "Database"

    def test_history_is_accepted(self, client, monkeypatch):
        monkeypatch.setattr(
            interviewer, "ask_gemma_json", lambda *a, **k: {"question": "Next?", "topic": "API"}
        )

        response = client.post(
            "/api/interview/question",
            json={
                "resume_profile": {},
                "role": "Backend",
                "interview_type": "Technical",
                "history": [{"question": "Q1", "answer": "A1", "evaluation": {"depth": 2}}],
            },
        )

        assert response.status_code == 200

    def test_model_down_returns_503_with_a_hint(self, client, monkeypatch):
        def down(*_args, **_kwargs):
            raise main.ModelUnavailableError()

        monkeypatch.setattr(interviewer, "ask_gemma_json", down)

        response = client.post(
            "/api/interview/question", json={"resume_profile": {}, "role": "Backend"}
        )

        assert response.status_code == 503
        assert "ollama" in response.json()["hint"].lower()


class TestEvaluate:
    def test_evaluates_an_answer(self, client, monkeypatch):
        monkeypatch.setattr(
            evaluator,
            "ask_gemma_json",
            lambda *a, **k: {"technical_accuracy": 8, "communication": 7, "depth": 6, "follow_up": "Why?"},
        )

        response = client.post(
            "/api/interview/evaluate",
            json={"resume_profile": {}, "question": "Q", "answer": "A"},
        )

        assert response.status_code == 200
        assert response.json()["technical_accuracy"] == 8

    def test_empty_answer_is_rejected_with_guidance(self, client):
        response = client.post(
            "/api/interview/evaluate", json={"resume_profile": {}, "question": "Q", "answer": "   "}
        )

        assert response.status_code == 400
        assert "empty answer" in response.json()["detail"].lower()

    def test_missing_question_is_rejected(self, client):
        assert client.post("/api/interview/evaluate", json={"answer": "A"}).status_code == 400


class TestAttack:
    def test_attack_question(self, client, monkeypatch):
        monkeypatch.setattr(
            attack,
            "ask_gemma_json",
            lambda *a, **k: {
                "claim": "Optimised queries",
                "category": "Database",
                "question": "Which query did you fix?",
            },
        )

        response = client.post(
            "/api/attack/question", json={"resume_profile": {"skills": ["MongoDB"]}, "role": "Backend"}
        )

        assert response.status_code == 200
        assert response.json()["claim"] == "Optimised queries"

    def test_attack_requires_a_profile(self, client):
        response = client.post("/api/attack/question", json={"resume_profile": {}})

        assert response.status_code == 400
        assert "resume" in response.json()["detail"].lower()

    def test_unusable_claim_returns_422(self, client, monkeypatch):
        monkeypatch.setattr(attack, "ask_gemma_json", lambda *a, **k: {"claim": "c"})

        response = client.post("/api/attack/question", json={"resume_profile": {"skills": []}})

        assert response.status_code == 422
        assert "claim" in response.json()["detail"].lower()

    def test_claim_evaluation(self, client, monkeypatch):
        monkeypatch.setattr(
            attack,
            "ask_gemma_json",
            lambda *a, **k: {"credibility_score": 7, "technical_depth": 6, "clarity": 8, "follow_up": "Why?"},
        )

        response = client.post(
            "/api/attack/evaluate",
            json={"claim": "Optimised queries", "question": "Which query?", "answer": "The slow one."},
        )

        assert response.status_code == 200
        assert response.json()["credibility_score"] == 7

    def test_claims_endpoint(self, client, monkeypatch):
        monkeypatch.setattr(
            attack, "ask_gemma_json", lambda *a, **k: {"claims": [{"claim": "x", "category": "API"}]}
        )

        response = client.post("/api/attack/claims", json={"resume_profile": {"skills": []}})

        assert response.status_code == 200
        assert response.json()["claims"][0]["claim"] == "x"


class TestReport:
    def test_report_is_generated_with_plain_text(self, client, monkeypatch):
        monkeypatch.setattr(report, "ask_gemma_json", lambda *a, **k: {"overall_score": 7.4})

        response = client.post(
            "/api/interview/report",
            json={
                "resume_profile": {},
                "role": "Backend",
                "interview_type": "Technical",
                "history": [{"question": "Q", "answer": "A", "evaluation": {"depth": 7}}],
            },
        )

        assert response.status_code == 200
        assert "PREPMATE INTERVIEW REPORT" in response.json()["text"]

    def test_empty_history_is_rejected(self, client):
        response = client.post("/api/interview/report", json={"history": []})

        assert response.status_code == 400


class TestResumeUpload:
    def _pdf(self, text: str) -> bytes:
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 100), text)
        data = document.tobytes()
        document.close()

        return data

    def test_upload_builds_a_profile(self, client, monkeypatch):
        monkeypatch.setattr(
            "resume.profile.ask_gemma_json",
            lambda *a, **k: {"name": "Jane Doe", "skills": ["FastAPI"], "projects": [{"name": "App"}]},
        )
        monkeypatch.setattr(main, "is_ocr_only", lambda _data: False)

        response = client.post(
            "/api/resume/upload",
            files={"file": ("cv.pdf", self._pdf("Jane Doe, backend software engineer with FastAPI and MongoDB skills."), "application/pdf")},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["profile"]["name"] == "Jane Doe"
        assert body["session_id"]
        assert body["ocr_used"] is False

    def test_response_never_contains_the_resume_text(self, client, monkeypatch):
        monkeypatch.setattr(
            "resume.profile.ask_gemma_json", lambda *a, **k: {"name": "Jane", "skills": ["FastAPI"]}
        )
        monkeypatch.setattr(main, "is_ocr_only", lambda _data: False)

        secret = "SECRET RESUME MARKER TEXT"
        body = client.post(
            "/api/resume/upload",
            files={"file": ("cv.pdf", self._pdf(secret + " " + "x" * 60), "application/pdf")},
        ).json()

        assert secret not in str(body)

    def test_non_pdf_is_rejected(self, client):
        response = client.post("/api/resume/upload", files={"file": ("cv.txt", b"hello", "text/plain")})

        assert response.status_code == 400
        assert "pdf" in response.json()["detail"].lower()

    def test_unreadable_pdf_returns_422(self, client):
        response = client.post(
            "/api/resume/upload",
            files={"file": ("cv.pdf", b"%PDF-1.4 corrupted", "application/pdf")},
        )

        assert response.status_code == 422
        assert "pdf" in response.json()["detail"].lower()

    def test_empty_upload_is_rejected(self, client):
        assert client.post("/api/resume/upload", files={"file": ("cv.pdf", b"", "application/pdf")}).status_code == 400

    def test_profile_failure_returns_422(self, client, monkeypatch):
        def boom(*_args, **_kwargs):
            raise main.ModelUnavailableError()

        monkeypatch.setattr("resume.profile.ask_gemma_json", boom)
        monkeypatch.setattr(main, "is_ocr_only", lambda _data: False)

        response = client.post(
            "/api/resume/upload",
            files={"file": ("cv.pdf", self._pdf("Jane Doe, backend software engineer. " + "x" * 80), "application/pdf")},
        )

        assert response.status_code == 503

    def test_missing_tesseract_returns_a_useful_503(self, client, monkeypatch):
        import pytesseract

        monkeypatch.setattr(
            main,
            "extract_text_from_pdf",
            lambda _data: (_ for _ in ()).throw(pytesseract.TesseractNotFoundError()),
        )

        response = client.post("/api/resume/upload", files={"file": ("cv.pdf", b"%PDF-1.4 x", "application/pdf")})

        assert response.status_code == 503
        assert "tesseract" in response.json()["detail"].lower()


class TestSessions:
    def test_unknown_session_is_404(self, client):
        assert client.get("/api/resume/session/nope").status_code == 404

    def test_delete_reports_whether_it_existed(self, client):
        assert client.delete("/api/session/nope").json() == {"deleted": False}
