"""End-to-end tests against a real local Gemma.

Skipped unless PREPMATE_LIVE=1:

    ollama pull gemma3:4b
    cd backend && PREPMATE_LIVE=1 pytest tests/test_live.py -v

These are the only tests that can catch prompt regressions that actually
matter — a mocked suite cannot tell you the model still follows the "no
greetings, one question" contract.
"""

from __future__ import annotations

from ai import attack, evaluator, gemma, interviewer, report
from resume.profile import create_profile
from tests.conftest import needs_live

pytestmark = needs_live


SAMPLE_RESUME = """
Niranjan R Soorej
B.Tech Computer Science, Example University, 2025

SKILLS
Python, C++, Node.js, Express.js, MongoDB, JWT, React, Docker

PROJECTS
Content Sharing Application
Built a REST backend in Express.js with MongoDB that lets users upload and
share files with role-based access. Used JWT for authentication and added
indexing on frequently queried fields to improve response time.

Data Structures Library
Implemented a balanced binary search tree and a hash map in C++ for a
university data structures course.

ACHIEVEMENTS
Solved 250+ problems on LeetCode.
"""


def test_model_is_available():
    assert gemma.is_available(), f"{gemma.MODEL} is not installed in Ollama"


def test_profile_extraction_uses_only_resume_facts():
    profile = create_profile(SAMPLE_RESUME)

    assert profile["skills"], "Gemma should extract skills from a resume with an explicit SKILLS section"
    assert profile["projects"], "Gemma should extract projects"

    joined = " ".join(profile["skills"]).lower()

    assert "mongodb" in joined or "express" in joined


def test_question_is_single_and_not_greeting():
    profile = create_profile(SAMPLE_RESUME)

    result = interviewer.generate_question(profile, "Backend Software Engineer", "Technical")

    assert result["question"]
    assert "?" in result["question"], "an interview question should be a question"
    assert not result["question"].lower().startswith(
        ("okay", "alright", "sure", "great", "here's", "here is")
    )


def test_evaluation_produces_scores_and_a_follow_up():
    result = evaluator.evaluate_answer(
        "Why does an index speed up a query in MongoDB?",
        "It lets MongoDB find matching documents without scanning the whole collection.",
        {"skills": ["MongoDB"]},
    )

    for key in ("technical_accuracy", "communication", "depth"):
        assert 1 <= result[key] <= 10

    assert result["follow_up"].strip()
    assert isinstance(result["strengths"], list)
    assert isinstance(result["weaknesses"], list)

    # Guard against the `{}` collapse: without a schema the model answers an
    # empty object and every field above falls back to a safe default.
    assert result["verdict"].strip(), "evaluator returned no verdict (empty JSON?)"
    assert result["strengths"], "evaluator returned no strengths (empty JSON?)"
    assert result["topics_to_revise"], "evaluator returned no topics (empty JSON?)"


def test_claim_pool_finds_concrete_claims():
    claims = attack.extract_claims(
        {"skills": ["MongoDB", "Express.js"]},
        (
            "Built a backend with 10+ RESTful API endpoints using Node.js, "
            "Express.js and MongoDB.\n"
            "Optimized database queries by adding indexes on userId and createdAt, "
            "reducing response time from 400ms to 40ms.\n"
            "Solved 250+ DSA problems.\n"
            "Implemented authentication using JWT and bcrypt password hashing."
        ),
    )

    assert claims, "no claims extracted from a resume full of them"

    for item in claims:
        assert item["claim"].strip()
        assert 1 <= item["verifiability"] <= 10


def test_resume_attack_produces_a_claim_and_a_question():
    profile = create_profile(SAMPLE_RESUME)

    result = attack.attack_question(profile, "Backend Software Engineer")

    assert result["valid"], "Resume Attack should find a concrete claim in this resume"
    assert result["claim"]
    assert result["question"]
    assert result["category"]


def test_claim_defence_is_scored():
    result = attack.evaluate_claim_defence(
        "Improved response time using indexing",
        "Which collection did you index and what did you measure?",
        "I created a compound index on userId and createdAt, and query time went from about 400ms to 40ms.",
    )

    assert 1 <= result["credibility_score"] <= 10
    assert result["evidence"], "a concrete answer should produce evidence"
    assert result["follow_up"].strip()


def test_report_is_generated_from_history():
    history = [
        {
            "question": "Why does an index speed up a MongoDB query?",
            "answer": "It avoids scanning the whole collection.",
            "topic": "Database",
            "kind": "question",
            "evaluation": {
                "technical_accuracy": 7,
                "communication": 6,
                "depth": 4,
                "strengths": ["Correct mechanism"],
                "weaknesses": ["No measurement"],
                "follow_up": "How did you measure the improvement?",
            },
        },
        {
            "question": "Which queries did you optimise with indexing?",
            "answer": "The file listing query filtered by userId and createdAt.",
            "topic": "Database",
            "kind": "attack",
            "claim": "Improved response time using indexing",
            "evaluation": {
                "credibility_score": 6,
                "technical_depth": 6,
                "clarity": 7,
                "evidence": ["Named the query"],
                "gaps": ["No before/after numbers"],
                "follow_up": "What were the before and after latencies?",
            },
        },
    ]

    result = report.generate_report(history, {"skills": ["MongoDB"]}, "Backend Engineer", "Resume Attack")

    assert 1.0 <= result["overall_score"] <= 10.0
    assert result["summary"], "the report should have a written summary"
    assert "PREPMATE INTERVIEW REPORT" in report.format_report_text(result)
