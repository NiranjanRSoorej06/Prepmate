from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai.interviewer import generate_question


app = FastAPI(
    title="PrepMate API",
    description="Private AI interview partner powered by local Gemma",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InterviewRequest(BaseModel):
    resume: str
    role: str
    interview_type: str
    previous_questions: list[str] = []
    previous_answers: list[str] = []


@app.get("/")
def root():
    return {
        "message": "PrepMate API is running",
        "model": "gemma3:4b",
        "runtime": "ollama",
    }


@app.post("/api/interview/question")
def get_question(request: InterviewRequest):

    question = generate_question(
        resume=request.resume,
        role=request.role,
        interview_type=request.interview_type,
        previous_questions=request.previous_questions,
        previous_answers=request.previous_answers,
    )

    return {
        "question": question
    }