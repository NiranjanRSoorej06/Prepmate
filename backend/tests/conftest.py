"""Shared fixtures.

The default suite runs fully offline: every model call is stubbed, so `pytest`
passes in CI without Ollama. Set `PREPMATE_LIVE=1` to additionally run the
tests that need a real local Gemma.
"""

from __future__ import annotations

import os

import pytest

LIVE = os.getenv("PREPMATE_LIVE") == "1"

needs_live = pytest.mark.skipif(
    not LIVE,
    reason="Needs a local Ollama with gemma3:4b. Run with PREPMATE_LIVE=1 pytest.",
)


@pytest.fixture
def stub_gemma(monkeypatch):
    """Replace `ask_gemma_json` in a module with a canned response."""

    def install(module, response):
        calls: list[dict] = []

        def fake(system_prompt, user_prompt, **kwargs):
            calls.append({"system": system_prompt, "user": user_prompt, **kwargs})
            return response

        monkeypatch.setattr(module, "ask_gemma_json", fake)

        return calls

    return install


@pytest.fixture
def sample_profile() -> dict:
    return {
        "name": "Sample Candidate",
        "target_role": "Backend Software Engineer",
        "education": [{"degree": "B.Tech", "institution": "Example University"}],
        "skills": ["Python", "FastAPI", "MongoDB", "JWT", "React"],
        "projects": [
            {
                "name": "Content Sharing Application",
                "description": "Share files between users with role-based access.",
                "technologies": ["FastAPI", "MongoDB", "JWT"],
            }
        ],
        "experience": [],
        "achievements": ["Improved query latency by adding a compound index"],
        "coursework": ["Data Structures"],
        "activities": [],
        "claims": [
            {"claim": "Improved query latency by adding a compound index", "category": "Database"}
        ],
        "seniority": "student",
        "total_experience_months": 0,
    }


@pytest.fixture
def sample_history() -> list[dict]:
    return [
        {
            "question": "Why does an index speed up this query?",
            "answer": "It avoids a full collection scan.",
            "topic": "Database",
            "kind": "question",
            "claim": "",
            "evaluation": {
                "technical_accuracy": 7,
                "communication": 6,
                "depth": 4,
                "verdict": "Correct but shallow.",
                "topic": "Database",
                "strengths": ["Correct mechanism"],
                "weaknesses": ["No mention of measurement"],
                "follow_up": "How did you measure the improvement?",
                "topics_to_revise": ["Index selectivity"],
            },
        },
        {
            "question": "Optimised database queries using indexing",
            "answer": "I added an index on userId.",
            "topic": "Database",
            "kind": "attack",
            "claim": "Optimised database queries using indexing",
            "evaluation": {
                "claim": "Optimised database queries using indexing",
                "credibility_score": 4,
                "technical_depth": 4,
                "clarity": 6,
                "verdict": "Partial defence.",
                "evidence": ["Named the field"],
                "gaps": ["No before/after numbers"],
                "follow_up": "What were the before and after latencies?",
            },
        },
    ]
