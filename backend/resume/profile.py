"""Resume profiling.

Turns raw resume text into a structured candidate profile that every other
part of PrepMate reads. Two constraints shape the prompt and the normaliser:

- Only include what the resume actually supports. A profile that hallucinates
  a project makes every downstream question unanswerable.
- Always return the same keys, even when the resume says nothing about them,
  so the frontend never has to guard for missing fields.
"""

from __future__ import annotations

from typing import Any

from ai import schemas
from ai.gemma import PrepMateError, ask_gemma_json
from ai.normalize import as_list, as_text

SYSTEM_PROMPT = """
You are PrepMate's resume analyzer.

Extract the candidate's information for conducting a personalized
technical interview.

Return JSON only, with exactly these keys:

{
  "name": "",
  "target_role": "",
  "education": [],
  "skills": [],
  "projects": [{"name": "", "description": "", "technologies": []}],
  "experience": [{"role": "", "organisation": "", "highlights": []}],
  "achievements": [],
  "coursework": [],
  "activities": [],
  "claims": [{"claim": "", "category": ""}],
  "seniority": "student | junior | mid | senior",
  "total_experience_months": 0
}

Rules:

- Only include information explicitly present in the resume.
- NEVER invent projects, technologies, employers or achievements.
- If the resume does not mention a field, return an empty value for it.
- "skills" must be flat strings, exactly as written (e.g. "Node.js").
- "projects" entries must have name, description and technologies.
- "claims" are concrete, checkable statements the candidate makes about
  themselves, quoted tightly from the resume. Include every number
  ("10+ RESTful API endpoints", "250+ DSA problems", "CGPA 9.42"), every
  named technology doing real work (indexing, JWT, bcrypt, caching), and
  every performance, security or scale claim. Do NOT include vague soft
  claims such as "good communicator" or "passionate developer". This field
  must never be empty for a normal engineering resume.
- "total_experience_months" is 0 unless the resume states dates you can
  actually compute it from.
"""

EMPTY_PROFILE: dict[str, Any] = {
    "name": "",
    "target_role": "",
    "education": [],
    "skills": [],
    "projects": [],
    "experience": [],
    "achievements": [],
    "coursework": [],
    "activities": [],
    "claims": [],
    "seniority": "student",
    "total_experience_months": 0,
}

_LIST_FIELDS = (
    "education",
    "skills",
    "achievements",
    "coursework",
    "activities",
)

_OBJECT_LIST_FIELDS = ("projects", "experience", "claims")


class ProfileError(PrepMateError):
    """The resume could not be turned into a usable profile."""


def _projects(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        # Model returned a single project or a prose string.
        value = [value] if value else []

    projects: list[dict[str, Any]] = []

    for item in value:
        if isinstance(item, dict):
            name = as_text(item.get("name")) or as_text(item.get("title"))
            description = as_text(item.get("description"))

            if not name and not description:
                continue

            technologies = item.get("technologies") or item.get("tech_stack") or []

            if isinstance(technologies, str):
                technologies = [
                    part.strip() for part in technologies.replace(",", "|").split("|")
                ]

            projects.append(
                {
                    "name": name,
                    "description": description,
                    "technologies": as_list(technologies),
                }
            )
        elif str(item).strip():
            projects.append({"name": str(item).strip(), "description": "", "technologies": []})

    return projects


def _experience(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        value = [value] if value else []

    entries: list[dict[str, Any]] = []

    for item in value:
        if isinstance(item, dict):
            role = as_text(item.get("role")) or as_text(item.get("title"))
            organisation = as_text(item.get("organisation")) or as_text(item.get("company"))

            if not role and not organisation:
                continue

            entries.append(
                {
                    "role": role,
                    "organisation": organisation,
                    "highlights": as_list(item.get("highlights") or item.get("description")),
                }
            )
        elif str(item).strip():
            entries.append({"role": str(item).strip(), "organisation": "", "highlights": []})

    return entries


def _claims(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        value = [value] if value else []

    claims: list[dict[str, str]] = []

    for item in value:
        if isinstance(item, dict):
            claim = as_text(item.get("claim")) or as_text(item.get("text"))

            if claim:
                claims.append({"claim": claim, "category": as_text(item.get("category"))})
        elif str(item).strip():
            claims.append({"claim": str(item).strip(), "category": ""})

    return claims


def normalise_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Force a model response into the exact profile shape."""
    profile = dict(EMPTY_PROFILE)

    profile["name"] = as_text(raw.get("name"))
    profile["target_role"] = as_text(raw.get("target_role"))

    for field in _LIST_FIELDS:
        profile[field] = as_list(raw.get(field))

    profile["projects"] = _projects(raw.get("projects"))
    profile["experience"] = _experience(raw.get("experience"))
    profile["claims"] = _claims(raw.get("claims"))

    seniority = as_text(raw.get("seniority"), default="student").lower()

    if seniority not in {"student", "junior", "mid", "senior"}:
        seniority = "student"

    profile["seniority"] = seniority

    try:
        months = int(float(raw.get("total_experience_months") or 0))
    except (TypeError, ValueError):
        months = 0

    profile["total_experience_months"] = max(0, min(600, months))

    return profile


def create_profile(resume_text: str) -> dict[str, Any]:
    """Extract a structured candidate profile from resume text."""
    if not resume_text.strip():
        raise ProfileError("No resume text was found to analyze.")

    raw = ask_gemma_json(
        SYSTEM_PROMPT,
        f"""
Analyze this resume:

{resume_text}
""",
        temperature=0.1,
        schema=schemas.PROFILE,
    )

    profile = normalise_profile(raw)

    if not profile["skills"] and not profile["projects"] and not profile["education"]:
        raise ProfileError(
            "Gemma could not find any skills, projects or education in this "
            "resume. If it is a scan, check that Tesseract is installed "
            "(tesseract --version)."
        )

    return profile
