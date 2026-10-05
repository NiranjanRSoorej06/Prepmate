"""Interview modes.

PrepMate is not one generic interview. Each mode changes what the interviewer
is allowed to focus on, and Resume Attack gets its own pipeline entirely
(see `ai.attack`) because it interrogates resume claims rather than topics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TECHNICAL = "Technical"
DSA = "DSA"
PROJECT_DEEP_DIVE = "Project Deep Dive"
BEHAVIORAL = "Behavioral"
RESUME_ATTACK = "Resume Attack"


@dataclass(frozen=True)
class InterviewMode:
    key: str
    label: str
    tagline: str
    focus: str
    question_style: str
    topics: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "tagline": self.tagline,
            "focus": self.focus,
            "topics": list(self.topics),
        }


MODES: dict[str, InterviewMode] = {
    mode.key: mode
    for mode in (
        InterviewMode(
            key="technical",
            label=TECHNICAL,
            tagline="Backend, databases, APIs, auth, systems",
            focus=(
                "backend engineering, databases, API design, authentication "
                "and authorization, systems fundamentals, language internals, "
                "concurrency, caching, scalability, testing and debugging"
            ),
            question_style=(
                "Ask a practical engineering question that a real interviewer "
                "would ask on a backend or full-stack round. Prefer concrete "
                "situations ('what happens when...', 'how would you...') over "
                "definition recall."
            ),
            topics=(
                "Databases",
                "APIs",
                "Authentication",
                "Systems Design",
                "Language Internals",
                "Concurrency",
                "Caching",
                "Testing",
            ),
        ),
        InterviewMode(
            key="dsa",
            label=DSA,
            tagline="Algorithms, data structures, complexity",
            focus=(
                "data structures, algorithmic complexity, problem solving, "
                "trade-offs between approaches, and edge cases"
            ),
            question_style=(
                "Ask an algorithm or data-structure question. State the "
                "problem briefly, then ask the candidate to describe their "
                "approach and time/space complexity. Do not hand over a "
                "language unless the candidate asks."
            ),
            topics=(
                "Arrays",
                "Hashing",
                "Trees",
                "Graphs",
                "Sorting",
                "Dynamic Programming",
                "Complexity Analysis",
            ),
        ),
        InterviewMode(
            key="project_deep_dive",
            label=PROJECT_DEEP_DIVE,
            tagline="Architecture, trade-offs, failures, scaling",
            focus=(
                "architecture, implementation decisions, trade-offs, failures "
                "and debugging stories, scalability, testing strategy, and how "
                "the candidate worked within constraints"
            ),
            question_style=(
                "Pick a project from the resume and ask a deep 'why' question "
                "about a decision the candidate made. Challenge reasoning, not "
                "memory."
            ),
            topics=(
                "Architecture",
                "Design Decisions",
                "Trade-offs",
                "Failure & Debugging",
                "Scalability",
                "Testing Strategy",
            ),
        ),
        InterviewMode(
            key="behavioral",
            label=BEHAVIORAL,
            tagline="Leadership, conflict, failure, ownership",
            focus=(
                "leadership, teamwork, conflict resolution, handling failure, "
                "decision making, ownership, feedback, and time management"
            ),
            question_style=(
                "Ask a situational or behavioural question about a real "
                "situation. Ask for a specific example. Stay professional and "
                "do not accuse the candidate of anything."
            ),
            topics=(
                "Leadership",
                "Teamwork",
                "Conflict",
                "Failure",
                "Decision Making",
                "Ownership",
            ),
        ),
    )
}

DEFAULT_MODE = TECHNICAL

#: Every mode label the frontend may submit, including Resume Attack which is
#: routed to its own endpoint.
KNOWN_LABELS = {mode.label for mode in MODES.values()} | {RESUME_ATTACK}


def resolve(interview_type: str | None) -> InterviewMode:
    """Map a user-facing interview type onto a mode definition.

    Unknown or missing values fall back to the technical round rather than
    failing the request, so an old saved session still works.
    """
    if not interview_type:
        return MODES["technical"]

    wanted = interview_type.strip()

    for mode in MODES.values():
        if wanted.lower() == mode.label.lower():
            return mode

    for mode in MODES.values():
        if wanted.lower() == mode.key:
            return mode

    return MODES["technical"]


def catalogue() -> list[dict[str, object]]:
    """All modes for the frontend mode picker."""
    return [mode.to_dict() for mode in MODES.values()]


def is_attack(interview_type: str | None) -> bool:
    return bool(interview_type) and interview_type.strip().lower() == RESUME_ATTACK.lower()
