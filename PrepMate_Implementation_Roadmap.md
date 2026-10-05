# PrepMate — Complete Implementation & Submission Roadmap

## 1. Project Goal

PrepMate is a private AI interview partner built for a real friend preparing for software engineering interviews.

Core idea:

> Upload a resume → Gemma understands the candidate → PrepMate conducts a personalized interview → evaluates answers → adapts follow-up questions → challenges resume claims → produces a useful interview report.

The project should keep Gemma at the center and run locally through Ollama.

---

# 2. Current Status

## Working

- [x] Ollama installed
- [x] `gemma3:4b` downloaded
- [x] Gemma tested locally
- [x] Python virtual environment created
- [x] FastAPI backend created
- [x] CORS configured
- [x] PyMuPDF PDF extraction
- [x] Tesseract OCR fallback
- [x] Resume PDF upload endpoint
- [x] Resume text extraction
- [x] Gemma resume profiling
- [x] Structured candidate profile
- [x] Personalized interview question generation
- [x] Answer submission
- [x] Gemma answer evaluation
- [x] Technical accuracy score
- [x] Communication score
- [x] Depth score
- [x] Strengths
- [x] Weaknesses
- [x] Suggested follow-up
- [x] Adaptive follow-up question logic
- [x] React frontend connected to backend
- [x] Complete basic interview flow

## Current issue / next immediate task

- [ ] Persist interview state across browser reloads using `localStorage`

---

# 3. Target Architecture

```text
                     ┌──────────────────┐
                     │   Resume PDF     │
                     └────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ PyMuPDF + Tesseract│
                    │   Resume Parser   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │      Gemma        │
                    │ Resume Profiler   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Candidate Profile │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Interview Engine  │
                    │      Gemma        │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Interview Question│
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Candidate Answer  │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Gemma Evaluator   │
                    └─────────┬─────────┘
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
             Scores       Weaknesses   Follow-up
                                           │
                                           ▼
                                   Adaptive Question
                                           │
                                           └───────► ...
```

---

# 4. Phase 1 — Persistence

## Goal

Refreshing the browser must NOT destroy the current interview.

Persist:

- candidate profile
- target role
- interview type
- current question
- current answer
- current evaluation
- interview history

Do NOT store the original PDF in `localStorage`.

## Implementation

In `frontend/src/App.jsx`:

### Import

```jsx
import { useEffect, useState } from "react";
```

### Storage key

```jsx
const STORAGE_KEY = "prepmate_interview";
```

### Load saved state

```jsx
function loadInterviewState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (!saved) {
      return null;
    }

    return JSON.parse(saved);
  } catch (error) {
    console.error("Failed to load saved interview:", error);
    return null;
  }
}
```

### Initialize state from localStorage

Restore:

```text
profile
role
interviewType
question
answer
evaluation
history
```

### Automatically save

Use `useEffect()` to save the current interview state whenever it changes.

### Reset

Add a reset function:

```jsx
function resetInterview() {
  localStorage.removeItem(STORAGE_KEY);

  setProfile(null);
  setRole("Backend Software Engineer");
  setInterviewType("Technical");
  setQuestion("");
  setAnswer("");
  setEvaluation(null);
  setHistory([]);
}
```

Add a visible `Reset Interview` button.

## Test

1. Upload resume.
2. Start interview.
3. Answer a question.
4. Get evaluation.
5. Refresh browser.
6. Confirm state remains.
7. Click Reset Interview.
8. Confirm state is cleared.

---

# 5. Phase 2 — Improve Interview Question Quality

Current Gemma questions work, but they can be too verbose.

Update interviewer rules:

```text
Keep questions concise and interview-like.
Do not add greetings, introductions, or commentary.
Ask one focused question at a time.
```

Avoid:

> Okay, Niranjan, let's dive in...

Prefer:

> You mentioned using JWT authentication in your Content Sharing Application. What happens if an attacker steals a user's JWT, and how would you mitigate that risk?

---

# 6. Phase 3 — Strong Adaptive Interview Loop

The evaluator already returns:

```json
{
  "technical_accuracy": 0,
  "communication": 0,
  "depth": 0,
  "strengths": [],
  "weaknesses": [],
  "follow_up": "",
  "topics_to_revise": []
}
```

The UI must use `evaluation.follow_up` directly.

Flow:

```text
Question
   ↓
Answer
   ↓
Evaluation
   ↓
Weakness identified
   ↓
Evaluator generates follow-up
   ↓
PrepMate asks exact follow-up
   ↓
Answer
   ↓
Evaluation again
```

Do not generate an unrelated new question when a valid follow-up already exists.

---

# 7. Phase 4 — Interview History

Maintain structured history:

```javascript
{
  question: "...",
  answer: "...",
  evaluation: {...}
}
```

This allows PrepMate to:

- avoid repeated questions
- understand previous answers
- increase difficulty
- revisit weak areas
- create a coherent interview

The history should be included when asking Gemma for a new question.

---

# 8. Phase 5 — Resume Attack Mode

This is the major differentiating feature.

## Goal

Instead of asking generic interview questions, PrepMate challenges claims made by the candidate on their resume.

Example resume claim:

> Optimized database queries using indexing for improved performance.

PrepMate asks:

> Which queries were slow before indexing, what index did you add, and how did you measure the performance improvement?

Another example:

> Implementing 10+ RESTful API endpoints.

Challenge:

> How did you structure those endpoints, and how did you handle validation and error responses consistently?

Another:

> Solved 250+ DSA problems.

Challenge:

> Explain a difficult problem where your first approach failed and how you improved its complexity.

## Backend file

Create:

```text
backend/ai/attack.py
```

## Behavior

Gemma should:

1. Inspect resume profile.
2. Find a concrete claim.
3. Select the most interviewable claim.
4. Ask exactly one verification question.
5. Avoid inventing facts.
6. Challenge technical depth rather than simply asking for repetition.

Potential structured output:

```json
{
  "claim": "Optimized database queries using indexing",
  "category": "Database",
  "question": "Which queries did you optimize and how did you measure the improvement?"
}
```

---

# 9. Phase 6 — Resume Claim Credibility

After Resume Attack Mode asks a question, evaluate the answer separately.

Possible output:

```json
{
  "claim": "...",
  "credibility_score": 8,
  "technical_depth": 7,
  "evidence": [
    "Explained why the index helped",
    "Described query selection"
  ],
  "gaps": [
    "Did not mention measurement methodology"
  ],
  "follow_up": "..."
}
```

Do NOT frame this as detecting whether the candidate is lying.

Frame it as:

> How well can the candidate defend the technical claims on their resume?

---

# 10. Phase 7 — Interview Modes

Provide several modes:

### Technical

Focus on:

- backend
- databases
- APIs
- authentication
- systems
- programming concepts

### DSA

Focus on:

- algorithms
- data structures
- complexity
- problem solving

### Project Deep Dive

Focus on:

- architecture
- implementation decisions
- trade-offs
- failures
- scalability
- testing

### Behavioral

Focus on:

- leadership
- teamwork
- conflict
- failure
- decision making

### Resume Attack

Focus on:

- measurable claims
- technical claims
- optimization claims
- security claims
- project claims

---

# 11. Phase 8 — Final Interview Report

At the end of an interview, generate a report.

Include:

```text
Overall Score
Technical Accuracy
Communication
Depth
Strongest Areas
Weakest Areas
Topics to Revise
Questions Asked
Resume Claims Successfully Defended
Resume Claims Needing More Preparation
Recommended Practice Plan
```

Example:

```text
PREPMATE INTERVIEW REPORT

Overall: 7.4 / 10

Strongest:
- REST API fundamentals
- JWT basics
- DSA fundamentals

Needs improvement:
- Database indexing
- Authentication attack scenarios
- System design depth

Recommended revision:
1. MongoDB indexing
2. JWT security
3. Token replay attacks
4. Database query optimization
```

This should be generated by Gemma from the interview history.

---

# 12. Phase 9 — Better UI

Current UI is functional. Improve it after functionality is stable.

## Dashboard

Show:

```text
PrepMate

Interview
Backend Software Engineer

Progress
████████░░ 4 / 5

Current Topic
Authentication

Score
7.3 / 10
```

## Question area

Make the question visually dominant.

## Answer area

Large textarea.

## Evaluation

Show score cards:

```text
Accuracy       8/10
Communication  7/10
Depth          6/10
```

Then:

```text
Strengths
Weaknesses
Suggested follow-up
```

---

# 13. Phase 10 — Session Restoration UX

When the app reloads and state exists:

Show:

```text
Welcome back.

Your previous interview session was restored.
Question 4 of your current session.
```

Buttons:

```text
Continue Interview
Start New Interview
```

This makes persistence obvious during the demo.

---

# 14. Phase 11 — Privacy Positioning

PrepMate's strong differentiator is local AI.

The architecture should be:

```text
Resume
   ↓
Local machine
   ↓
Ollama
   ↓
Gemma 3 4B
```

Avoid sending resume/interview data to a cloud LLM.

Demo idea:

1. Start PrepMate.
2. Disable Wi-Fi.
3. Upload/use resume.
4. Run interview.
5. Show that Gemma still works.

This demonstrates the private/local architecture.

---

# 15. Phase 12 — Error Handling

Add clean handling for:

- Ollama not running
- Gemma unavailable
- malformed Gemma JSON
- invalid PDF
- scanned PDF
- OCR failure
- empty answer
- backend unavailable
- API timeout
- localStorage corruption

Frontend should show useful messages instead of raw errors.

Example:

```text
PrepMate cannot reach the local Gemma model.

Make sure Ollama is running and Gemma 3 4B is installed.
```

---

# 16. Phase 13 — Loading States

Use clear states:

```text
Analyzing resume...
Generating question...
Evaluating answer...
Preparing follow-up...
Generating final report...
```

Do not leave the UI looking frozen while Gemma is generating.

---

# 17. Phase 14 — Backend Cleanup

Target structure:

```text
backend/
├── ai/
│   ├── __init__.py
│   ├── gemma.py
│   ├── interviewer.py
│   ├── evaluator.py
│   ├── attack.py
│   └── report.py
│
├── database/
│   └── __init__.py
│
├── resume/
│   ├── __init__.py
│   ├── parser.py
│   └── profile.py
│
├── main.py
├── requirements.txt
├── resume.pdf
└── test_*.py
```

---

# 18. Phase 15 — Remove Temporary Test Code

Before final submission:

- [ ] Remove unnecessary test scripts if not needed
- [ ] Remove debug prints
- [ ] Remove hardcoded resume data
- [ ] Remove unused imports
- [ ] Check `.gitignore`
- [ ] Do NOT commit `.venv`
- [ ] Do NOT commit private credentials
- [ ] Do NOT commit personal secrets
- [ ] Keep required sample/demo data only

---

# 19. Phase 16 — README

Create a strong README.

Recommended structure:

```text
# PrepMate

Private AI Interview Partner Powered by Gemma

## Problem

Generic AI interview tools ask generic questions.

Candidates need an interviewer that understands their
actual resume and challenges what they claim.

## Solution

PrepMate turns a resume into an adaptive private interviewer.

## Features

- Resume parsing
- OCR fallback
- Gemma-powered profile extraction
- Personalized interviews
- Answer evaluation
- Adaptive follow-ups
- Resume Attack Mode
- Final interview report
- Local/private AI
- Session persistence

## Architecture

[diagram]

## Tech Stack

Frontend:
React + Vite + Tailwind

Backend:
FastAPI + Python

AI:
Gemma 3 4B + Ollama

Resume:
PyMuPDF + Tesseract

Storage:
Browser localStorage

## Running

### Ollama

ollama pull gemma3:4b

### Backend

source .venv/bin/activate
uvicorn main:app --reload --port 8000

### Frontend

npm install
npm run dev

## Why Gemma?

Explain specifically how Gemma powers:
- profile extraction
- question generation
- evaluation
- adaptive follow-ups
- resume attack
- report generation

## Privacy

Resume and interview data remain local.

## Demo

Explain the end-to-end flow.
```

---

# 20. Phase 17 — Testing Checklist

## Resume

- [ ] Normal text PDF works
- [ ] Scanned PDF works
- [ ] Invalid file rejected
- [ ] Empty PDF handled
- [ ] Profile contains only resume-supported information

## Interview

- [ ] First question generated
- [ ] Question is resume-specific
- [ ] Answer submission works
- [ ] Evaluation works
- [ ] Scores are 1–10
- [ ] Follow-up works
- [ ] Previous questions are remembered
- [ ] Questions don't repeat unnecessarily

## Persistence

- [ ] Refresh preserves state
- [ ] Browser restart preserves state
- [ ] Reset clears state
- [ ] Corrupt localStorage does not crash app

## Attack Mode

- [ ] Claims extracted
- [ ] Claim challenge generated
- [ ] Answer evaluated
- [ ] Follow-up generated

## UI

- [ ] Loading states
- [ ] Error states
- [ ] Mobile-ish responsive layout
- [ ] No console errors
- [ ] No broken buttons

---

# 21. Phase 18 — Demo Script

Keep the demo short and convincing.

### Step 1

Open PrepMate.

### Step 2

Upload the real friend's resume.

### Step 3

Show that Gemma extracts:

```text
Skills
Projects
Coursework
Activities
```

### Step 4

Start a technical interview.

Show a question specifically about a resume project.

### Step 5

Give an intentionally shallow answer.

Show Gemma detecting the weakness.

### Step 6

Click the follow-up.

Show that PrepMate directly probes the weak point.

### Step 7

Use Resume Attack Mode.

Show a claim from the resume being challenged.

### Step 8

Refresh the browser.

Show:

```text
Previous session restored.
```

### Step 9

Optional strongest demo:

Disable Wi-Fi and continue the interview.

This demonstrates local Gemma execution.

---

# 22. Phase 19 — Differentiation

Do NOT describe PrepMate simply as:

> "An AI mock interview app."

That is too generic.

Describe it as:

> **A private AI interviewer that knows your resume, adapts to your answers, and challenges whether you can actually defend the claims you made.**

Core differentiators:

1. Resume-grounded questions
2. Adaptive follow-ups
3. Resume Attack Mode
4. Local Gemma inference
5. Privacy
6. Persistent interview sessions

---

# 23. Phase 20 — Hackathon Submission

Before submitting:

- [ ] Public GitHub repository
- [ ] Good README
- [ ] Clear architecture diagram
- [ ] Screenshots
- [ ] Demo video if required/beneficial
- [ ] Explain why this was built for a real friend
- [ ] Explain Gemma usage
- [ ] Explain local/private architecture
- [ ] Test clean installation
- [ ] Remove secrets
- [ ] Verify repository works from a fresh clone

Submission tags:

```text
#devchallenge
#weekendchallenge
#hf26challenge
```

---

# 24. Priority Order

Do NOT implement everything at once.

Use this order:

## P0 — Must work

1. [ ] localStorage persistence
2. [ ] clean question generation
3. [ ] adaptive follow-up
4. [ ] interview history
5. [ ] error handling

## P1 — Main differentiator

6. [ ] Resume Attack Mode
7. [ ] Claim evaluation
8. [ ] Final interview report

## P2 — Polish

9. [ ] Better dashboard
10. [ ] Session restoration UX
11. [ ] Loading states
12. [ ] UI polish
13. [ ] README
14. [ ] Architecture diagram
15. [ ] Demo preparation

---

# 25. Final Product

The finished PrepMate experience should feel like:

```text
                 PREPMATE
        Private AI Interview Partner

                    │
                    ▼

              Upload Resume
                    │
                    ▼
              Gemma Profile
                    │
                    ▼
             Choose Interview
                    │
                    ▼
            Personalized Question
                    │
                    ▼
               Your Answer
                    │
                    ▼
             Gemma Evaluation
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
       Feedback           Follow-up
                              │
                              ▼
                       Adaptive Interview
                              │
                              ▼
                       Resume Attack
                              │
                              ▼
                       Final Report
```

The key message:

> **PrepMate doesn't just ask you interview questions. It learns what you claim to know, tests whether you actually understand it, and adapts the interview around your weaknesses — privately on your own machine.**
