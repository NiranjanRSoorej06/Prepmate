"""Interview question generation.

The interviewer is Gemma, constrained by a prompt that keeps it terse and
resume-grounded. Question generation is also where interview *history* is
consumed: what has been asked, how well it was answered, and which weak
topics are still open. That is what turns a list of questions into an
interview.
"""

from __future__ import annotations

from typing import Any

from . import schemas
from .gemma import (
    InvalidModelOutputError,
    ModelTimeoutError,
    ModelUnavailableError,
    ask_gemma_json,
)
from .modes import InterviewMode, resolve

SYSTEM_PROMPT = """
You are PrepMate, an experienced software engineering interviewer
conducting a live, one-on-one interview.

Your output must be a single question and nothing else.

Hard rules:

1. Ask EXACTLY ONE question.
2. Keep it concise: one to two sentences, ideally under 40 words.
3. NO greetings. Never say the candidate's name. No "Okay", "Great",
   "Let's dive in", "Thanks for sharing", or any other commentary.
4. NO preamble, NO explanation, NO hints, NO follow-up commentary.
5. Ground the question in the candidate's actual resume. Reference a real
   project, skill, course or achievement when it fits naturally.
6. Never invent experience, projects or technologies that are not in
   the candidate's profile.
7. Never reveal or hint at the answer.
8. Do not repeat or lightly rephrase a question already asked.
9. Build on previous answers: probe a gap, a hand-wave, or a claim the
   candidate made without explaining the reasoning.
10. Gradually increase difficulty as the interview progresses.

Output format (JSON only):

{
  "question": "the single question to ask",
  "topic": "2-3 word topic label, e.g. Authentication",
  "difficulty": 1,
  "targets_weakness": true
}

- "topic" is used for the dashboard and for avoiding topic loops.
- "difficulty" is an integer 1-10 reflecting this question's level.
- "targets_weakness" is true when the question deliberately probes a
  weakness the evaluator already identified.
"""


def _format_history(history: list[dict[str, Any]] | None) -> str:
    """Render past Q&A pairs as a compact, prompt-friendly transcript."""
    if not history:
        return "No previous questions. This is the opening question."

    lines: list[str] = []

    for index, item in enumerate(history, start=1):
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        evaluation = item.get("evaluation") or {}
        topic = str(item.get("topic") or evaluation.get("topic") or "").strip()

        header = f"Q{index}" + (f" [{topic}]" if topic else "")

        lines.append(f"{header}: {question}")

        if answer:
            lines.append(f"A{index}: {answer}")

        weakness = evaluation.get("weakness") or ""

        if weakness:
            lines.append(f"  -> Evaluator's main concern: {weakness}")

        follow_up = evaluation.get("follow_up")

        if follow_up:
            lines.append(f"  -> Follow-up available (not yet asked): {follow_up}")

    return "\n".join(lines)


def _weak_topics(history: list[dict[str, Any]] | None) -> list[str]:
    """Collect topics the candidate has not answered well yet."""
    topics: list[str] = []

    for item in history or []:
        evaluation = item.get("evaluation") or {}

        score = evaluation.get("depth")

        try:
            weak = float(score) < 6
        except (TypeError, ValueError):
            weak = False

        if weak:
            for source in (evaluation.get("topics_to_revise"), evaluation.get("weaknesses")):
                for entry in source or []:
                    text = str(entry).strip()

                    if text and text not in topics:
                        topics.append(text)

    return topics[:8]


def _fallback_question(mode: InterviewMode, role: str) -> dict[str, Any]:
    """A safe question when Gemma's JSON cannot be trusted.

    Returning a usable question beats failing the whole request, but the
    caller is told it is a fallback so the UI can flag degraded output.
    """
    return {
        "question": (
            f"Based on your resume, walk me through the most technically "
            f"demanding thing you have built for a {role} role."
        ),
        "topic": mode.label,
        "difficulty": 5,
        "targets_weakness": False,
        "degraded": True,
    }


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    question = str(raw.get("question", "")).strip()

    # A model that ignored the format often returns the question as the only
    # value, under a different key, or as the whole object serialised.
    if not question:
        for key in ("text", "prompt", "interview_question", "content"):
            question = str(raw.get(key, "")).strip()

            if question:
                break

    question = question.strip().strip('"').strip()

    # Strip the chit-chat the prompt forbids, so a verbose model still yields
    # a usable question.
    for prefix in (
        "Okay,",
        "Ok,",
        "Alright,",
        "Great question,",
        "Sure,",
        "Here's my question:",
        "Here is my question:",
        "Question:",
    ):
        if question.lower().startswith(prefix.lower()):
            question = question[len(prefix) :].strip()

    difficulty = raw.get("difficulty", 5)

    try:
        difficulty = int(float(difficulty))
    except (TypeError, ValueError):
        difficulty = 5

    return {
        "question": question,
        "topic": str(raw.get("topic", "")).strip() or "General",
        "difficulty": max(1, min(10, difficulty)),
        "targets_weakness": bool(raw.get("targets_weakness", False)),
        "degraded": False,
    }


def generate_question(
    resume_profile: dict,
    role: str,
    interview_type: str,
    history: list[dict[str, Any]] | None = None,
    previous_questions: list[str] | None = None,
    previous_answers: list[str] | None = None,
) -> dict[str, Any]:
    """Produce the next question for an interview in progress.

    Accepts the structured `history` used by the current frontend and the
    older parallel `previous_questions` / `previous_answers` lists, so a
    session saved by an older build still continues correctly.
    """
    mode = resolve(interview_type)
    history = list(history or [])

    if not history and previous_questions:
        answers = previous_answers or []

        history = [
            {
                "question": question,
                "answer": answers[index] if index < len(answers) else "",
            }
            for index, question in enumerate(previous_questions)
        ]

    weak = _weak_topics(history)
    asked = [str(item.get("question", "")).strip() for item in history if item.get("question")]

    prompt = f"""
CANDIDATE PROFILE (extracted from their real resume):

{resume_profile}

TARGET ROLE: {role}
INTERVIEW MODE: {mode.label}
MODE FOCUS: {mode.focus}
MODE QUESTION STYLE: {mode.question_style}
CANDIDATE TOPICS TO COVER: {", ".join(mode.topics)}

INTERVIEW HISTORY SO FAR:
{_format_history(history)}

QUESTIONS ALREADY ASKED (never repeat these):
{asked or "None yet"}

WEAK TOPICS THE CANDIDATE HAS NOT PROVEN YET:
{weak or "None identified yet"}

DIFFICULTY SO FAR: {len(asked)} question(s) asked.

Generate the next question now, as JSON only.
"""

    try:
        raw = ask_gemma_json(
            SYSTEM_PROMPT,
            prompt,
            temperature=0.6,
            schema=schemas.QUESTION,
        )
    except (ModelUnavailableError, ModelTimeoutError):
        # Infrastructure failures must reach the user with the fix in the
        # message. A generic fallback question would hide a dead Ollama.
        raise
    except InvalidModelOutputError:
        return _fallback_question(mode, role)

    result = _normalise(raw)

    if not result["question"]:
        return _fallback_question(mode, role)

    result["mode"] = mode.label

    return result
