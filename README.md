# PrepMate

A private, local-first mock interview partner. Upload a resume, get asked
questions by a local LLM that has actually read it, answer them, and receive
per-answer feedback, an adaptive follow-up drill, and a final report with a
concrete practice plan.

Every inference runs on your machine through Ollama. No resume text, answer,
or report leaves your computer.

---

## What it does

**Resume-aware interviews.** The resume is parsed once, turned into a
structured profile, and every question is generated from it. The model asks
about the specific project on *your* resume, not generic questions.

**Five interview modes.** Technical, DSA, Project Deep Dive, Behavioral, and
Resume Attack — each with its own question focus.

**An adaptive loop.** The evaluator does three things at once: it scores the
answer, names the gap, and writes the follow-up question. The next turn of
the interview *is* that follow-up, so a weak point is probed directly instead
of being replaced by an unrelated question.

**Resume Attack.** This is the differentiated mode. PrepMate reads the claims
you make about yourself, ranks them by how verifiable they are, and challenges
the weakest one with a question an interviewer would actually ask — then scores
how credibly you defended it.

It is framed as *defending a claim*, not catching a lie. The point is to find
the holes in your own story before an interviewer does.

**Nothing leaves the machine.** The resume text is held in a two-hour in-memory
server session and is never returned by the API. The browser keeps only your
derived profile, session history, and a session ID in `localStorage` — never
the PDF or the raw text.

---

## Requirements

- Python 3.11+
- Node 20+
- [Ollama](https://ollama.com) with the model pulled:
  ```bash
  ollama pull gemma3:4b
  ```
- Optional, for scanned/image-only PDFs: `tesseract-ocr` on `PATH`

A scanned PDF is detected automatically and falls back to OCR, so PrepMate
works on photographed resumes as well as digital ones.

---

## Setup

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

---

## Running it

Two terminals.

```bash
# Terminal 1 — API on http://localhost:8000
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

```bash
# Terminal 2 — UI on http://localhost:5173
cd frontend
npm run dev
```

Open http://localhost:5173.

Check the model is reachable:

```bash
curl http://localhost:8000/api/health
# {"model":"gemma3:4b","available":true,"local_only":true}
```

If `available` is `false`, start Ollama (`ollama serve`) and confirm the model
is pulled.

---

## How it works

```
resume.pdf
   │  PyMuPDF, or Tesseract when the PDF has no text layer
   ▼
structured profile  ──────────────────────────────┐
   │  { name, skills, projects, claims, ... }      │
   ▼                                              │
question generator ◄── session history ────────────┤
   ▼                                              │
candidate answer                                  │
   ▼                                              │
evaluator ──► scores, strengths, weaknesses ──► the next question
   │                                              │
   ▼                                              ▼
final report ◄─────────────── full transcript ───┘
   scores, summary, weakest areas, practice plan
```

### Layout

| Path | Role |
| --- | --- |
| `backend/main.py` | FastAPI app and every HTTP route |
| `backend/ai/gemma.py` | Ollama transport, typed errors, health, JSON recovery |
| `backend/ai/schemas.py` | JSON schema per structured call |
| `backend/ai/interviewer.py` | History-aware question generation |
| `backend/ai/evaluator.py` | Scoring plus the follow-up that drives the next turn |
| `backend/ai/attack.py` | Claim extraction, attack questions, credibility scoring |
| `backend/ai/report.py` | Two-pass report, plus a local fallback |
| `backend/ai/normalize.py` | Shared score/list/text coercion |
| `backend/resume/` | PDF/OCR extraction and profile normalisation |
| `backend/database/` | Transient in-memory session store |
| `frontend/src/hooks/useInterview.js` | Client state machine and autosave |
| `frontend/src/storage.js` | Versioned `localStorage` persistence |

### Why the schemas exist

A small local model asked for "some JSON" will, often enough to be a real bug,
answer a literal `{}` — which surfaces as a report with an empty summary or an
evaluation that silently defaults to 5/5/5. So every structured call passes an
explicit JSON schema to Ollama, which constrains decoding and makes an empty
reply essentially impossible. If a reply still comes back empty, PrepMate
retries once before falling back to a locally computed result.

The report is generated in two focused passes — judgement, then plan —
because asking one 4B model for a whole report at once reliably produced
nothing.

---

## Configuration

Backend settings are environment variables, all optional:

| Variable | Default | Meaning |
| --- | --- | --- |
| `PREPMATE_MODEL` | `gemma3:4b` | Ollama model to use |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |
| `PREPMATE_TIMEOUT` | `600` | Seconds to wait for one model call |

```bash
export PREPMATE_MODEL=qwen3:8b
export PREPMATE_TIMEOUT=1800
```

Larger models give better judgement but are noticeably slower; anything from
`gemma3:4b` upward works.

---

## Tests

```bash
cd backend
.venv/bin/pytest                    # offline suite, no model needed
```

The live suite exercises the real model and is skipped by default:

```bash
cd backend
PREPMATE_LIVE=1 .venv/bin/pytest tests/test_live.py -v
```

Leave `gemma3:4b` pulled and Ollama running, or those tests will fail.

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

---

## Troubleshooting

**"Could not reach the local model"** — Ollama is not running, or the model is
not pulled. `ollama serve`, then `ollama pull gemma3:4b`.

**Health check says the model is missing** — `ollama list` and pull the model
named in the error.

**Requests time out on a large resume** — raise `PREPMATE_TIMEOUT`. Large PDFs
mean a long first prompt.

**Claims come back empty in Resume Attack** — the resume needs concrete
claims: numbers, named technologies doing real work, measurable outcomes. A
resume of soft skills has nothing verifiable to attack, which is a finding in
its own right.

**A scanned PDF parsed badly** — OCR is a fallback, not a parser. Check
`ocr_used` in the upload response; a cleaner scan or a digital PDF is always
better.

**Stale session after a code change** — reload the page, or use Reset, which
clears `localStorage` and the server session.