"""PrepMate API.

A local-only FastAPI service that turns a resume PDF into an adaptive,
resume-grounded mock interview. Every AI call goes to Ollama on this machine;
nothing leaves it.

Run with:

    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging

import pytesseract
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai import attack as attack_module
from ai import modes as modes_module
from ai import report as report_module
from ai.evaluator import evaluate_answer
from ai.gemma import (
    MODEL,
    InvalidModelOutputError,
    ModelTimeoutError,
    ModelUnavailableError,
    PrepMateError,
    health,
)
from ai.interviewer import generate_question
from database import store
from resume.parser import ResumeParseError, extract_text_from_pdf, is_ocr_only
from resume.profile import ProfileError, create_profile

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("prepmate")

#: Cap on upload size — resumes are never larger than this.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

DEFAULT_ROLE = "Backend Software Engineer"

app = FastAPI(
    title="PrepMate API",
    description="Private AI interview partner powered by local Gemma",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Error handling — every failure becomes an actionable message for the UI
# --------------------------------------------------------------------------

_STATUS_BY_ERROR: list[tuple[type[Exception], int]] = [
    (ModelUnavailableError, 503),
    (ModelTimeoutError, 504),
    (InvalidModelOutputError, 502),
    (ResumeParseError, 422),
    (ProfileError, 422),
]


def _status_for(error: Exception) -> int:
    for error_type, status in _STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return status

    return 500


@app.exception_handler(PrepMateError)
async def handle_prepmate_error(request, error: PrepMateError):  # noqa: ARG001
    """Map PrepMate's own errors onto friendly, human-readable messages."""
    status = _status_for(error)

    logger.warning("%s -> %s", type(error).__name__, error)

    return JSONResponse(
        status_code=status,
        content={
            "detail": str(error),
            "error": type(error).__name__,
            "hint": _hint_for(error),
        },
    )


@app.exception_handler(pytesseract.TesseractNotFoundError)
async def handle_missing_tesseract(request, error):  # noqa: ARG001
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Tesseract is not installed, so scanned resumes cannot be read. "
                "Install it (macOS: brew install tesseract, Ubuntu: "
                "sudo apt install tesseract-ocr) and restart PrepMate."
            ),
            "error": "TesseractNotFoundError",
            "hint": "Install the OCR engine, or upload a PDF with a real text layer.",
        },
    )


def _hint_for(error: Exception) -> str:
    if isinstance(error, ModelUnavailableError):
        return f"Start Ollama and run: ollama pull {MODEL}"

    if isinstance(error, ModelTimeoutError):
        return "The local model was slow to respond. Try again."

    if isinstance(error, InvalidModelOutputError):
        return "A larger model (ollama pull gemma3:12b) gives more reliable output."

    if isinstance(error, (ResumeParseError, ProfileError)):
        return "Try a different PDF, or export it with a real text layer."

    return ""


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------


class HistoryItem(BaseModel):
    question: str = ""
    answer: str = ""
    evaluation: dict = Field(default_factory=dict)
    topic: str = ""
    kind: str = "question"
    claim: str = ""


class QuestionRequest(BaseModel):
    resume_profile: dict = Field(default_factory=dict)
    role: str = DEFAULT_ROLE
    interview_type: str = modes_module.DEFAULT_MODE
    history: list[HistoryItem] = Field(default_factory=list)
    previous_questions: list[str] = Field(default_factory=list)
    previous_answers: list[str] = Field(default_factory=list)


class EvaluateRequest(BaseModel):
    resume_profile: dict = Field(default_factory=dict)
    question: str = ""
    answer: str = ""
    interview_type: str = ""


class AttackRequest(BaseModel):
    resume_profile: dict = Field(default_factory=dict)
    role: str = DEFAULT_ROLE
    attacked_claims: list[str] = Field(default_factory=list)
    resume_text: str | None = None
    session_id: str | None = None


class ClaimEvaluationRequest(BaseModel):
    claim: str
    question: str
    answer: str
    resume_profile: dict = Field(default_factory=dict)


class ReportRequest(BaseModel):
    history: list[HistoryItem] = Field(default_factory=list)
    resume_profile: dict = Field(default_factory=dict)
    role: str = DEFAULT_ROLE
    interview_type: str = modes_module.DEFAULT_MODE


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/")
def root():
    return {
        "message": "PrepMate API is running",
        "model": MODEL,
        "runtime": "ollama",
        "docs": "/docs",
    }


@app.get("/api/health")
def api_health():
    """Report whether the local model is reachable.

    The frontend uses this to show a clear 'is Gemma running?' state instead
    of failing on the first real request.
    """
    status = health()

    if not status["available"]:
        return JSONResponse(status_code=503, content=status)

    return status


@app.get("/api/modes")
def api_modes():
    """The interview modes the frontend offers."""
    return {"modes": modes_module.catalogue()}


@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Parse a resume PDF and build a Gemma-powered candidate profile."""
    filename = file.filename or ""

    if not filename:
        raise HTTPException(status_code=400, detail="No file was provided.")

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="That file is too large. Resumes should be under 10 MB.",
        )

    resume_text = extract_text_from_pdf(contents)

    if len(resume_text.strip()) < 50:
        scanned = is_ocr_only(contents)

        raise HTTPException(
            status_code=422,
            detail=(
                "PrepMate could not read any text from this resume. "
                + (
                    "It looks like a scan, so OCR is required — make sure "
                    "Tesseract is installed and try again."
                    if scanned
                    else "Try exporting the PDF with a real text layer."
                )
            ),
        )

    profile = create_profile(resume_text)
    used_ocr = is_ocr_only(contents)

    session = store.create(filename, resume_text, profile)

    return {
        "filename": filename,
        "characters": len(resume_text),
        "session_id": session.id,
        "ocr_used": used_ocr,
        "profile": profile,
    }


@app.get("/api/resume/session/{session_id}")
def get_session(session_id: str):
    """Metadata about a stored session (never the resume text itself)."""
    session = store.get(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="That session has expired.")

    return session.public_dict()


@app.post("/api/interview/question")
def api_question(request: QuestionRequest):
    """Generate the next interview question."""
    history = [item.model_dump() for item in request.history]

    result = generate_question(
        resume_profile=request.resume_profile,
        role=request.role or DEFAULT_ROLE,
        interview_type=request.interview_type,
        history=history,
        previous_questions=request.previous_questions,
        previous_answers=request.previous_answers,
    )

    return {
        "question": result["question"],
        "topic": result["topic"],
        "difficulty": result["difficulty"],
        "targets_weakness": result["targets_weakness"],
        "degraded": result["degraded"],
        "mode": result.get("mode", request.interview_type),
    }


@app.post("/api/interview/evaluate")
def api_evaluate(request: EvaluateRequest):
    """Score an answer and produce the follow-up question."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="There is no question to evaluate.")

    if not request.answer.strip():
        raise HTTPException(
            status_code=400,
            detail="Write an answer before submitting. PrepMate cannot evaluate an empty answer.",
        )

    return evaluate_answer(
        question=request.question.strip(),
        answer=request.answer.strip(),
        resume_profile=request.resume_profile,
        interview_type=request.interview_type or None,
    )


@app.post("/api/attack/claims")
def api_attack_claims(payload: dict):
    """List the resume claims worth challenging."""
    profile = payload.get("resume_profile") or {}

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Upload a resume before starting Resume Attack Mode.",
        )

    resume_text = payload.get("resume_text")
    session_id = payload.get("session_id")

    if not resume_text and session_id:
        session = store.get(session_id)

        if session is not None:
            resume_text = session.resume_text

    return {"claims": attack_module.extract_claims(profile, resume_text)}


@app.post("/api/attack/question")
def api_attack_question(request: AttackRequest):
    """Pick one un-attacked resume claim and challenge it."""
    if not request.resume_profile:
        raise HTTPException(
            status_code=400,
            detail="Upload a resume before starting Resume Attack Mode.",
        )

    resume_text = request.resume_text

    if not resume_text and request.session_id:
        session = store.get(request.session_id)

        if session is not None:
            resume_text = session.resume_text

    result = attack_module.attack_question(
        profile=request.resume_profile,
        role=request.role or DEFAULT_ROLE,
        attacked_claims=request.attacked_claims,
        resume_text=resume_text,
    )

    if not result["valid"]:
        raise HTTPException(
            status_code=422,
            detail=(
                "PrepMate could not find a concrete claim on this resume to "
                "challenge. Add measurable details — technologies, numbers or "
                "outcomes — and try again."
            ),
        )

    result["session_id"] = request.session_id

    return result


@app.post("/api/attack/evaluate")
def api_attack_evaluate(request: ClaimEvaluationRequest):
    """Score how well the candidate defended a resume claim."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="There is no question to evaluate.")

    if not request.answer.strip():
        raise HTTPException(
            status_code=400,
            detail="Write an answer before submitting. PrepMate cannot evaluate an empty answer.",
        )

    return attack_module.evaluate_claim_defence(
        claim=request.claim,
        question=request.question.strip(),
        answer=request.answer.strip(),
        profile=request.resume_profile or None,
    )


@app.post("/api/interview/report")
def api_report(request: ReportRequest):
    """Generate the final interview report from the whole session."""
    history = [item.model_dump() for item in request.history]

    if not history:
        raise HTTPException(
            status_code=400,
            detail="Answer at least one question before generating a report.",
        )

    result = report_module.generate_report(
        history=history,
        profile=request.resume_profile,
        role=request.role or DEFAULT_ROLE,
        interview_type=request.interview_type,
    )

    result["text"] = report_module.format_report_text(result)

    return result


@app.delete("/api/session/{session_id}")
def api_delete_session(session_id: str):
    """Forget a stored resume immediately."""
    removed = store.delete(session_id)

    return {"deleted": removed}
