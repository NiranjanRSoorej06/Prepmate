"""Final interview report.

Runs once, at the end of a session, and reads the entire transcript. Its job is
to turn a list of scored answers into something a candidate can act on: what
they proved, what they could not defend, and what to study next.

The report is generated in two passes rather than one. Asking a 4B model for
scores, prose, six lists and a nested study plan in a single JSON object gets a
literal `{}` back — it gives up on the schema. Splitting the analytical pass
from the actionable pass, each with a small schema, is what makes this reliable
on a small local model.

Whatever the model returns, the report can never be empty: the numeric roll-up
is computed locally, and a failed or unusable generation falls back to a report
assembled directly from the per-answer evaluations.
"""

from __future__ import annotations

from typing import Any

from . import schemas
from .gemma import ask_gemma_json
from .normalize import as_list, as_text, clamp_score

ANALYSIS_SYSTEM_PROMPT = """
You are PrepMate's report writer.

You are given a complete interview transcript: every question, the candidate's
answer, and the evaluator's scores and feedback. Judge the session as a whole.

Return JSON only:

{
  "overall_score": 7.4,
  "technical_accuracy": 7.8,
  "communication": 7.1,
  "depth": 7.3,
  "readiness": "interview-ready",
  "summary": "3-5 sentences on how the candidate performed overall",
  "strongest_areas": ["area"],
  "weakest_areas": ["area"],
  "topics_to_revise": ["topic"]
}

Rules:

- Scores are numbers from 1 to 10. Base them on the evaluator's scores,
  not on optimism.
- "summary" must reflect what actually happened, weak answers included.
- Be demanding but constructive. No empty praise.
"""

PLAN_SYSTEM_PROMPT = """
You are PrepMate's interviewer, turning an interview into a study plan.

You are given the candidate's transcript, their weakest areas and the topics
they need to revise. Write the follow-up.

Return JSON only:

{
  "claims_defended": ["claim from the resume the candidate explained well"],
  "claims_needing_work": ["claim they could not defend"],
  "practice_plan": [
    {"step": 1, "focus": "...", "action": "...", "why": "..."}
  ],
  "next_interview_focus": ["what to open the next session with"]
}

Rules:

- Only reference claims that appear in the transcript. Never invent one.
- "practice_plan" has 3-5 steps, most valuable first. Each "action" must be
  something the candidate can actually do this week.
- "why" is one short line.
"""

#: If none of these keys survive, the generation was useless and the report is
#: rebuilt from the evaluations instead.
_ANALYSIS_KEYS = (
    "summary",
    "strongest_areas",
    "weakest_areas",
    "topics_to_revise",
)

_PLAN_KEYS = ("claims_defended", "claims_needing_work", "practice_plan")


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return round(sum(values) / len(values), 1)


def _from_history(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Numeric roll-up computed locally, so the report is never empty."""
    accuracy: list[float] = []
    communication: list[float] = []
    depth: list[float] = []

    for item in history:
        evaluation = item.get("evaluation") or {}

        if not isinstance(evaluation, dict):
            continue

        for key, bucket in (
            ("technical_accuracy", accuracy),
            ("communication", communication),
            ("depth", depth),
        ):
            try:
                bucket.append(float(evaluation.get(key)))
            except (TypeError, ValueError):
                continue

    return {
        "overall_score": _mean(accuracy + communication + depth),
        "technical_accuracy": _mean(accuracy),
        "communication": _mean(communication),
        "depth": _mean(depth),
    }


def _format_transcript(history: list[dict[str, Any]]) -> str:
    lines: list[str] = []

    for index, item in enumerate(history, start=1):
        question = as_text(item.get("question"))
        answer = as_text(item.get("answer"))
        evaluation = item.get("evaluation") or {}

        if not isinstance(evaluation, dict):
            evaluation = {}

        kind = str(item.get("kind") or evaluation.get("kind") or "question")

        lines.append(f"--- {kind.upper()} {index} ---")
        lines.append(f"TOPIC: {as_text(item.get('topic') or evaluation.get('topic'), default='General')}")
        lines.append(f"Q: {question}")
        lines.append(f"A: {answer or '(no answer)'}")

        if kind == "attack":
            claim = item.get("claim") or evaluation.get("claim")

            if claim:
                lines.append(f"RESUME CLAIM UNDER TEST: {claim}")

            credibility = evaluation.get("credibility_score")

            if credibility is not None:
                lines.append(f"CREDIBILITY: {credibility}/10")
                lines.append(f"VERDICT: {as_text(evaluation.get('verdict'))}")
                lines.append(f"GAPS: {'; '.join(as_list(evaluation.get('gaps'))) or 'none noted'}")
        else:
            lines.append(
                "SCORES: accuracy {}/10, communication {}/10, depth {}/10".format(
                    evaluation.get("technical_accuracy", "-"),
                    evaluation.get("communication", "-"),
                    evaluation.get("depth", "-"),
                )
            )
            lines.append(f"STRENGTHS: {'; '.join(as_list(evaluation.get('strengths'))) or 'none noted'}")
            lines.append(f"WEAKNESSES: {'; '.join(as_list(evaluation.get('weaknesses'))) or 'none noted'}")
            lines.append(f"REVISE: {'; '.join(as_list(evaluation.get('topics_to_revise'))) or 'none noted'}")

    return "\n".join(lines)


def _has_content(raw: dict[str, Any], keys: tuple[str, ...]) -> bool:
    """Did the model actually say anything, or did it collapse to `{}`?"""
    return any(raw.get(key) for key in keys)


def generate_report(
    history: list[dict[str, Any]],
    profile: dict,
    role: str,
    interview_type: str,
) -> dict[str, Any]:
    """Build the end-of-interview report from the full session transcript."""
    if not history:
        raise ValueError("Cannot generate a report before any questions are answered.")

    transcript = _format_transcript(history)
    totals = _from_history(history)

    context = f"""
TARGET ROLE: {role}
INTERVIEW MODE: {interview_type}
QUESTIONS ANSWERED: {len(history)}

CANDIDATE PROFILE:
{profile}

FULL INTERVIEW TRANSCRIPT:
{transcript}

COMPUTED AVERAGES (use as the baseline for your scores):
overall {totals['overall_score']}/10, technical accuracy
{totals['technical_accuracy']}/10, communication {totals['communication']}/10,
depth {totals['depth']}/10
"""

    # Pass 1: the judgement.
    analysis: dict[str, Any] = {}

    try:
        analysis = ask_gemma_json(
            ANALYSIS_SYSTEM_PROMPT,
            context,
            temperature=0.3,
            schema=schemas.REPORT_ANALYSIS,
        )
    except Exception:
        analysis = {}

    if not _has_content(analysis, _ANALYSIS_KEYS):
        # Either the model failed or it returned an empty object. The
        # evaluation-derived report is far more useful than a hollow one.
        return _degraded_report(history, profile, role, totals)

    # Pass 2: the plan, informed by pass 1.
    plan: dict[str, Any] = {}

    try:
        plan = ask_gemma_json(
            PLAN_SYSTEM_PROMPT,
            f"""
{context}

ASSESSMENT OF THIS SESSION:
summary: {as_text(analysis.get("summary"))}
strongest areas: {as_list(analysis.get("strongest_areas"))}
weakest areas: {as_list(analysis.get("weakest_areas"))}
topics to revise: {as_list(analysis.get("topics_to_revise"))}

Write the follow-up plan as JSON only.
""",
            temperature=0.4,
            schema=schemas.REPORT_PLAN,
        )
    except Exception:
        plan = {}

    steps: list[dict[str, Any]] = []

    for item in plan.get("practice_plan") or []:
        if isinstance(item, dict):
            focus = as_text(item.get("focus"))
            action = as_text(item.get("action"))

            if focus or action:
                steps.append(
                    {
                        "step": len(steps) + 1,
                        "focus": focus,
                        "action": action,
                        "why": as_text(item.get("why")),
                    }
                )
        elif isinstance(item, str) and item.strip():
            steps.append({"step": len(steps) + 1, "focus": "", "action": item.strip(), "why": ""})

    claims_defended = as_list(plan.get("claims_defended"))
    claims_needing_work = as_list(plan.get("claims_needing_work"))

    if not _has_content(plan, _PLAN_KEYS) and not steps:
        # The plan pass failed but the judgement survived: keep the judgement
        # and backfill the actionable part locally.
        backup = _degraded_report(history, profile, role, totals)

        steps = backup["practice_plan"]
        claims_defended = backup["claims_defended"]
        claims_needing_work = backup["claims_needing_work"]

        if not plan.get("next_interview_focus"):
            plan = {"next_interview_focus": backup["next_interview_focus"]}

    return {
        "overall_score": _score10(analysis.get("overall_score"), totals["overall_score"]),
        "technical_accuracy": _score10(
            analysis.get("technical_accuracy"), totals["technical_accuracy"]
        ),
        "communication": _score10(analysis.get("communication"), totals["communication"]),
        "depth": _score10(analysis.get("depth"), totals["depth"]),
        "readiness": as_text(analysis.get("readiness"), default="in progress"),
        "summary": as_text(analysis.get("summary")),
        "strongest_areas": as_list(analysis.get("strongest_areas")),
        "weakest_areas": as_list(analysis.get("weakest_areas")),
        "topics_to_revise": as_list(analysis.get("topics_to_revise")),
        "claims_defended": claims_defended,
        "claims_needing_work": claims_needing_work,
        "practice_plan": steps[:5],
        "next_interview_focus": as_list(plan.get("next_interview_focus")),
        "questions_asked": len(history),
        "degraded": False,
    }


def _score10(value: Any, fallback: float) -> float:
    """Report scores allow one decimal; fall back to the computed average."""
    if value is None:
        return fallback or clamp_score(fallback)

    try:
        score = float(value)
    except (TypeError, ValueError):
        return round(fallback, 1)

    if score != score:  # NaN
        return round(fallback, 1)

    if 0 < score <= 1:
        score *= 10

    return round(max(1.0, min(10.0, score)), 1)


def _degraded_report(
    history: list[dict[str, Any]],
    profile: dict,
    role: str,
    totals: dict[str, Any],
) -> dict[str, Any]:
    """A report built purely from evaluator output, used if Gemma's fails.

    The session still gets a useful artefact instead of an error screen.
    """
    strengths: list[str] = []
    weaknesses: list[str] = []
    revise: list[str] = []
    defended: list[str] = []
    needing: list[str] = []

    for item in history:
        evaluation = item.get("evaluation") or {}

        if not isinstance(evaluation, dict):
            continue

        strengths.extend(as_list(evaluation.get("strengths")))
        weaknesses.extend(as_list(evaluation.get("weaknesses")))
        revise.extend(as_list(evaluation.get("topics_to_revise")))

        if item.get("kind") == "attack":
            claim = as_text(item.get("claim") or evaluation.get("claim"))

            if not claim:
                continue

            try:
                score = float(evaluation.get("credibility_score", 0))
            except (TypeError, ValueError):
                score = 0

            (defended if score >= 6 else needing).append(claim)

    def unique(items: list[str]) -> list[str]:
        seen: list[str] = []

        for item in items:
            if item and item not in seen:
                seen.append(item)

        return seen

    focus_topics = unique(revise) or unique(weaknesses)

    practice_plan = [
        {
            "step": index,
            "focus": topic,
            "action": f"Revise {topic} and be able to explain it end to end without notes.",
            "why": "Flagged as a weak area in this session.",
        }
        for index, topic in enumerate(focus_topics[:5], start=1)
    ]

    return {
        "overall_score": totals["overall_score"] or 5.0,
        "technical_accuracy": totals["technical_accuracy"] or 5.0,
        "communication": totals["communication"] or 5.0,
        "depth": totals["depth"] or 5.0,
        "readiness": "in progress",
        "summary": (
            f"You answered {len(history)} question(s) for the {role} role. "
            "The full written summary could not be generated right now, so this "
            "report is built directly from the evaluator's per-answer feedback."
        ),
        "strongest_areas": unique(strengths)[:5],
        "weakest_areas": unique(weaknesses)[:5],
        "topics_to_revise": unique(revise)[:8],
        "claims_defended": unique(defended),
        "claims_needing_work": unique(needing),
        "practice_plan": practice_plan,
        "next_interview_focus": focus_topics[:3] or unique(weaknesses)[:3],
        "questions_asked": len(history),
        "degraded": True,
    }


def format_report_text(report: dict[str, Any]) -> str:
    """Plain-text rendering of the report, used for copy-to-clipboard."""
    lines = [
        "PREPMATE INTERVIEW REPORT",
        "=" * 40,
        f"Overall: {report.get('overall_score', 0)} / 10",
        f"Technical Accuracy: {report.get('technical_accuracy', 0)} / 10",
        f"Communication: {report.get('communication', 0)} / 10",
        f"Depth: {report.get('depth', 0)} / 10",
        f"Questions answered: {report.get('questions_asked', 0)}",
        "",
    ]

    if report.get("summary"):
        lines.extend(["SUMMARY", "-" * 40, report["summary"], ""])

    def section(title: str, key: str) -> None:
        items = report.get(key) or []

        if not items:
            return

        lines.append(title)
        lines.append("-" * 40)
        lines.extend(f"- {item}" for item in items)
        lines.append("")

    section("STRONGEST AREAS", "strongest_areas")
    section("NEEDS IMPROVEMENT", "weakest_areas")
    section("RESUME CLAIMS DEFENDED", "claims_defended")
    section("RESUME CLAIMS NEEDING WORK", "claims_needing_work")
    section("TOPICS TO REVISE", "topics_to_revise")

    plan = report.get("practice_plan") or []

    if plan:
        lines.append("RECOMMENDED PRACTICE PLAN")
        lines.append("-" * 40)

        for step in plan:
            focus = step.get("focus") or "Revision"
            lines.append(f"{step.get('step', '?')}. {focus}: {step.get('action', '')}")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["generate_report", "format_report_text"]
