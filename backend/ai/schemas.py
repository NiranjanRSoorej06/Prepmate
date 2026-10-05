"""JSON schemas for every structured Gemma call.

gemma3:4b answers a literal `{}` surprisingly often when a prompt merely
asks for "JSON", especially when the prompt also embeds a large resume
profile. Handing Ollama an explicit schema per call and letting it constrain
decoding removes that failure mode entirely.

Every schema here mirrors the normalisation already applied downstream, so a
schema-constrained reply and a hand-written reply are equally safe.
"""

from __future__ import annotations

from typing import Any

_SCORE = {"type": "integer"}
_STRING = {"type": "string"}
_STRING_LIST = {"type": "array", "items": {"type": "string"}}


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


EVALUATION: dict[str, Any] = _obj(
    {
        "technical_accuracy": _SCORE,
        "communication": _SCORE,
        "depth": _SCORE,
        "verdict": _STRING,
        "strengths": _STRING_LIST,
        "weaknesses": _STRING_LIST,
        "follow_up": _STRING,
        "topics_to_revise": _STRING_LIST,
        "topic": _STRING,
    },
    ["technical_accuracy", "communication", "depth", "verdict", "follow_up", "topic"],
)


QUESTION: dict[str, Any] = _obj(
    {
        "question": _STRING,
        "topic": _STRING,
        "difficulty": {"type": "integer"},
        "reason": _STRING,
    },
    ["question", "topic", "difficulty"],
)


CLAIM_POOL: dict[str, Any] = _obj(
    {
        "claims": {
            "type": "array",
            "items": _obj(
                {
                    "claim": _STRING,
                    "category": _STRING,
                    "verifiability": _SCORE,
                    "reason": _STRING,
                },
                ["claim", "category", "verifiability"],
            ),
        }
    },
    ["claims"],
)


ATTACK_QUESTION: dict[str, Any] = _obj(
    {
        "claim": _STRING,
        "category": _STRING,
        "question": _STRING,
        "why_it_matters": _STRING,
        "difficulty": _SCORE,
    },
    ["claim", "category", "question", "why_it_matters", "difficulty"],
)


CREDIBILITY: dict[str, Any] = _obj(
    {
        "credibility_score": _SCORE,
        "technical_depth": _SCORE,
        "clarity": _SCORE,
        "verdict": _STRING,
        "evidence": _STRING_LIST,
        "gaps": _STRING_LIST,
        "follow_up": _STRING,
    },
    ["credibility_score", "technical_depth", "clarity", "verdict", "evidence", "gaps"],
)


REPORT_ANALYSIS: dict[str, Any] = _obj(
    {
        "overall_score": _SCORE,
        "technical_accuracy": _SCORE,
        "communication": _SCORE,
        "depth": _SCORE,
        "readiness": _STRING,
        "summary": _STRING,
        "strongest_areas": _STRING_LIST,
        "weakest_areas": _STRING_LIST,
        "topics_to_revise": _STRING_LIST,
    },
    ["readiness", "summary", "strongest_areas", "weakest_areas", "topics_to_revise"],
)


REPORT_PLAN: dict[str, Any] = _obj(
    {
        "claims_defended": _STRING_LIST,
        "claims_needing_work": _STRING_LIST,
        "practice_plan": {
            "type": "array",
            "items": _obj(
                {"focus": _STRING, "action": _STRING, "why": _STRING},
                ["focus", "action"],
            ),
        },
        "next_interview_focus": _STRING_LIST,
    },
    ["claims_defended", "claims_needing_work", "practice_plan", "next_interview_focus"],
)


PROFILE: dict[str, Any] = _obj(
    {
        "name": _STRING,
        "email": _STRING,
        "phone": _STRING,
        "links": _STRING_LIST,
        "target_role": _STRING,
        "total_experience_months": {"type": "integer"},
        "skills": _STRING_LIST,
        "projects": {
            "type": "array",
            "items": _obj(
                {
                    "name": _STRING,
                    "description": _STRING,
                    "technologies": _STRING_LIST,
                    "highlights": _STRING_LIST,
                },
                ["name", "description"],
            ),
        },
        "education": _STRING_LIST,
        "claims": {
            "type": "array",
            "items": _obj({"claim": _STRING, "category": _STRING}, ["claim"]),
        },
        "topics_to_prepare": _STRING_LIST,
    },
    ["name", "target_role", "skills", "projects", "claims"],
)