from .gemma import ask_gemma


SYSTEM_PROMPT = """
You are PrepMate, a professional software engineering interviewer.

Your job is to conduct realistic technical interviews.

Rules:

1. Ask exactly ONE question at a time.
2. Personalize questions using the candidate's resume.
3. Use previous answers to determine follow-up questions.
4. Increase difficulty when appropriate.
5. Do not reveal the answer before the candidate responds.
6. Do not repeat previous questions.
7. Keep questions concise.
"""


def generate_question(
    resume: str,
    role: str,
    interview_type: str,
    previous_questions: list[str],
    previous_answers: list[str],
) -> str:

    prompt = f"""
Candidate target role:
{role}

Interview type:
{interview_type}

Candidate resume:
{resume}

Previous questions:
{previous_questions}

Previous answers:
{previous_answers}

Generate the next interview question.
"""

    return ask_gemma(
        SYSTEM_PROMPT,
        prompt,
    )