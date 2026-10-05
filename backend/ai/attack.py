"""Resume Attack Mode and claim credibility.

This is PrepMate's differentiator. Instead of asking generic questions,
PrepMate reads the resume, picks a *specific* claim the candidate made, and
asks a question whose only satisfying answer requires actually having done the
work. Then it scores how well the candidate defended the claim.

Framing matters: this measures how well a candidate can defend their resume,
not whether they are lying. The language here is deliberately about evidence,
depth and preparation.
"""

from __future__ import annotations

from typing import Any

from . import schemas
from .gemma import ask_gemma_json
from .normalize import as_list, as_text, clamp_score, strip_chatty_prefix

CLAIM_CATEGORIES = (
    "Database",
    "API",
    "Security",
    "Frontend",
    "Performance",
    "Architecture",
    "Testing",
    "Data Structures & Algorithms",
    "Cloud & DevOps",
    "Leadership",
    "Project",
    "Other",
)

ATTACK_SYSTEM_PROMPT = """
You are PrepMate in Resume Attack Mode.

You read the candidate's own resume and challenge one specific claim they
made about themselves.

Process:

1. Find a concrete, falsifiable claim. Good claims name a technology, a
   number, an optimisation, a security measure, a scale, or an outcome.
   Weak claims ("worked on a web app", "good team player") are not worth
   attacking — skip them.
2. Choose the claim that is most interviewable: most technical, most
   measurable, or most likely to be a bluff.
3. Ask EXACTLY ONE verification question about that claim.
4. The question must demand specifics: which files, which queries, which
   index, which numbers, which failure mode.
5. Do NOT ask the candidate to repeat the claim, and do NOT ask a yes/no
   question.
6. Never invent facts. Only use the resume and the profile given to you.
7. Stay professional and neutral. You are testing preparation and depth,
   not accusing anyone of dishonesty.
8. Ask only a question: no greetings, no commentary, no explanation.
   Keep it under 40 words.

Return JSON only:

{
  "claim": "the exact claim from the resume, quoted or tightly paraphrased",
  "category": "one of the categories listed below",
  "question": "the single verification question",
  "why_it_matters": "one short sentence on what a strong answer would show",
  "difficulty": 5
}

Categories: Database, API, Security, Frontend, Performance, Architecture,
Testing, Data Structures & Algorithms, Cloud & DevOps, Leadership, Project,
Other.
"""

CLAIM_POOL_SYSTEM_PROMPT = """
You are PrepMate's resume claim analyst.

You read a candidate's resume and list the concrete claims they make about
themselves that an interviewer could verify.

A good claim is specific and checkable. Look for:

- Numbers: "10+ endpoints", "250+ problems", "40% faster", "CGPA 9.42".
- Named technologies doing real work: indexing, JWT, caching, bcrypt.
- Security decisions: hashing, token handling, access control.
- Performance or optimisation claims.
- Scope claims: team size, users, endpoints shipped.
- Measurable outcomes of any kind.

Ignore vague claims such as "good communicator", "passionate developer" or
"worked on a web app". Quote the claim tightly from the resume.

Return JSON only:

{
  "claims": [
    {
      "claim": "the claim, tightly quoted from the resume",
      "category": "one of the categories listed below",
      "verifiability": 7,
      "reason": "why this is worth challenging in an interview"
    }
  ]
}

List between 3 and 8 claims, strongest first.

Categories: Database, API, Security, Frontend, Performance, Architecture,
Testing, Data Structures & Algorithms, Cloud & DevOps, Leadership, Project,
Other.
"""

CREDIBILITY_SYSTEM_PROMPT = """
You are PrepMate assessing how well a candidate defended one claim from
their resume during an interview.

You are NOT deciding whether the candidate lied. You are measuring
preparation and demonstrated technical depth. A candidate who genuinely
built the thing may still answer vaguely; a candidate who did not may still
know the theory. Judge only the answer given.

Return JSON only:

{
  "claim": "the claim being assessed",
  "credibility_score": 0,
  "technical_depth": 0,
  "clarity": 0,
  "verdict": "one sentence: strong, partial or weak defence of the claim",
  "evidence": ["concrete things in the answer that support the claim"],
  "gaps": ["important things the answer did not cover"],
  "follow_up": "ONE short question probing the biggest gap, asked verbatim"
}

Rules:

- credibility_score, technical_depth and clarity are integers 1-10.
- "evidence" lists specifics the candidate actually provided (numbers,
  mechanisms, decisions, trade-offs). Empty list if the answer was vague.
- "gaps" lists missing specifics: no measurement, no reason, no failure
  mode, no trade-off. Be honest, not harsh.
- "follow_up" must probe a gap and be phrased as a question under 30 words.
"""


def _validate_claim(raw: dict[str, Any]) -> dict[str, Any]:
    claim = as_text(raw.get("claim"))
    question = strip_chatty_prefix(as_text(raw.get("question")))

    category = as_text(raw.get("category"), default="Other")

    if category not in CLAIM_CATEGORIES:
        for known in CLAIM_CATEGORIES:
            if category.lower() in known.lower():
                category = known
                break
        else:
            category = "Other"

    return {
        "claim": claim,
        "category": category,
        "question": question,
        "why_it_matters": as_text(raw.get("why_it_matters")),
        "difficulty": clamp_score(raw.get("difficulty"), default=6),
        "valid": bool(claim and question),
    }


def extract_claims(profile: dict, resume_text: str | None = None) -> list[dict[str, Any]]:
    """List the resume claims worth attacking.

    Used to seed the attack pool so the UI can show what PrepMate intends to
    challenge before it challenges anything.
    """
    prompt = f"""
CANDIDATE PROFILE:
{profile}

RAW RESUME TEXT:
{resume_text or "(not available)"}

List the strongest verifiable claims this candidate makes about themselves,
strongest first.
"""

    try:
        raw = ask_gemma_json(
            CLAIM_POOL_SYSTEM_PROMPT,
            prompt,
            temperature=0.3,
            schema=schemas.CLAIM_POOL,
        )
    except Exception:
        return []

    items = raw.get("claims")

    if not isinstance(items, list):
        items = raw.get("items") if isinstance(raw.get("items"), list) else []

    claims: list[dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        claim = as_text(item.get("claim"))

        if not claim:
            continue

        category = as_text(item.get("category"), default="Other")

        if category not in CLAIM_CATEGORIES:
            category = "Other"

        claims.append(
            {
                "claim": claim,
                "category": category,
                "verifiability": clamp_score(item.get("verifiability"), default=5),
                "reason": as_text(item.get("reason")),
            }
        )

    return claims[:10]


def attack_question(
    profile: dict,
    role: str,
    attacked_claims: list[str] | None = None,
    resume_text: str | None = None,
) -> dict[str, Any]:
    """Pick one un-attacked resume claim and generate a verification question."""
    attacked = [str(item).strip() for item in (attacked_claims or []) if str(item).strip()]

    avoid = "\n".join(f"- {claim}" for claim in attacked) or "None yet"

    prompt = f"""
CANDIDATE PROFILE:
{profile}

TARGET ROLE: {role}

RAW RESUME TEXT (ground truth — only use what is here):
{(resume_text or "(not available; rely on the profile)")}

CLAIMS ALREADY CHALLENGED (do not choose these again):
{avoid}

Choose the single most interviewable remaining claim and write one
verification question for it, as JSON only.
"""

    raw = ask_gemma_json(
        ATTACK_SYSTEM_PROMPT,
        prompt,
        temperature=0.5,
        schema=schemas.ATTACK_QUESTION,
    )

    result = _validate_claim(raw)

    result["mode"] = "Resume Attack"

    return result


def evaluate_claim_defence(
    claim: str,
    question: str,
    answer: str,
    profile: dict | None = None,
) -> dict[str, Any]:
    """Score how well the candidate defended a resume claim."""
    profile_hint = f"\nCANDIDATE PROFILE:\n{profile}" if profile else ""

    prompt = f"""
CLAIM UNDER SCRUTINY:
{claim}

QUESTION ASKED:
{question}

CANDIDATE ANSWER:
{answer}
{profile_hint}

Assess how well the candidate defended this claim, as JSON only.
"""

    raw = ask_gemma_json(
        CREDIBILITY_SYSTEM_PROMPT,
        prompt,
        temperature=0.2,
        schema=schemas.CREDIBILITY,
    )

    credibility = clamp_score(raw.get("credibility_score"))
    depth = clamp_score(raw.get("technical_depth"))
    clarity = clamp_score(raw.get("clarity"), default=5)

    gaps = as_list(raw.get("gaps"))
    evidence = as_list(raw.get("evidence"))

    follow_up = strip_chatty_prefix(as_text(raw.get("follow_up")))

    if not follow_up:
        follow_up = (
            "What would you have measured to know whether that change "
            "actually helped?"
        )

    return {
        "claim": as_text(raw.get("claim"), default=claim) or claim,
        "credibility_score": credibility,
        "technical_depth": depth,
        "clarity": clarity,
        "overall": round((credibility + depth + clarity) / 3, 1),
        "verdict": as_text(raw.get("verdict")),
        "evidence": evidence,
        "gaps": gaps,
        "follow_up": follow_up,
    }
