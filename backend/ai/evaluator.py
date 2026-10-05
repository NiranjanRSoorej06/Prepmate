"""Answer evaluation.

The evaluator is the engine of PrepMate's adaptive loop: it scores the answer,
names the gap, and — crucially — writes the follow-up question that the
interview will actually ask next. The frontend uses `follow_up` verbatim so a
weak point is probed directly instead of being replaced by an unrelated
question.
"""

from __future__ import annotations

from typing import Any

from . import schemas
from .gemma import ask_gemma_json
from .normalize import MAX_SCORE, MIN_SCORE, as_list, as_text, clamp_score, strip_chatty_prefix

SYSTEM_PROMPT = """
You are PrepMate's interview evaluator.

You judge one interview answer objectively, the way a strict but fair
technical interviewer would.

Return JSON only, with exactly these keys:

{
  "technical_accuracy": 0,
  "communication": 0,
  "depth": 0,
  "verdict": "",
  "strengths": [],
  "weaknesses": [],
  "follow_up": "",
  "topics_to_revise": [],
  "topic": ""
}

Rules:

- Every score is an integer from 1 to 10. 1 is wrong or empty; 5 is
  correct but shallow; 10 is accurate, deep and well communicated.
- Judge only what the candidate actually said. Do not reward confidence,
  length or vocabulary.
- "technical_accuracy" — is the content correct?
- "communication" — is it structured, clear and concise?
- "depth" — does it explain WHY and cover trade-offs, or only WHAT?
- "strengths" and "weaknesses": 1-4 short, specific items. No praise
  padding, no invented issues.
- "follow_up": ONE short question that probes the weakest or most
  interesting part of this answer. This will be asked verbatim, so it
  must be phrased as a question, must be under 30 words, and must not
  contain greetings, commentary or explanations. Never output an empty
  follow_up.
- "topics_to_revise": concepts the candidate should study next.
- "topic": a 2-3 word label for the area this question covered.
- "verdict": one sentence summarising the answer's quality.
"""


def _fallback_follow_up() -> str:
    """Guarantee the adaptive loop never stalls.

    The evaluator's own follow-up is preferred; this is only used when Gemma
    omitted it entirely.
    """
    return "Can you walk me through the reasoning behind your answer in more detail?"


def evaluate_answer(
    question: str,
    answer: str,
    resume_profile: dict,
    interview_type: str | None = None,
) -> dict[str, Any]:
    """Score an answer and produce the follow-up that drives the next turn."""
    mode_hint = f"\nINTERVIEW MODE: {interview_type}\n" if interview_type else ""

    prompt = f"""
CANDIDATE PROFILE (their real resume):
{resume_profile}

INTERVIEW QUESTION:
{question}

CANDIDATE ANSWER:
{answer}
{mode_hint}
Evaluate this answer as JSON only.
"""

    raw = ask_gemma_json(
        SYSTEM_PROMPT,
        prompt,
        temperature=0.2,
        schema=schemas.EVALUATION,
    )

    technical_accuracy = clamp_score(raw.get("technical_accuracy"))
    communication = clamp_score(raw.get("communication"))
    depth = clamp_score(raw.get("depth"))

    follow_up = strip_chatty_prefix(as_text(raw.get("follow_up")))

    overall = round((technical_accuracy + communication + depth) / 3, 1)

    return {
        "technical_accuracy": technical_accuracy,
        "communication": communication,
        "depth": depth,
        "overall": overall,
        "verdict": as_text(raw.get("verdict")),
        "topic": as_text(raw.get("topic"), default="General"),
        "strengths": as_list(raw.get("strengths")),
        "weaknesses": as_list(raw.get("weaknesses")),
        "follow_up": follow_up or _fallback_follow_up(),
        "topics_to_revise": as_list(raw.get("topics_to_revise")),
    }
