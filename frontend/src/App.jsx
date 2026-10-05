import { RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "./api.js";
import { ClaimFeedback, HistoryTimeline } from "./components/ClaimViews.jsx";
import { AnswerBox, AnswerFeedback, Dashboard, QuestionCard } from "./components/Interview.jsx";
import { ReportView } from "./components/Report.jsx";
import { ProfileSetup, ResumeUpload } from "./components/ResumeSteps.jsx";
import { DangerButton, ErrorNotice, GhostButton, Loading, PrivacyBadge, ProgressBar } from "./components/ui.jsx";
import { useInterview } from "./hooks/useInterview.js";

const FALLBACK_MODES = [
  { key: "technical", label: "Technical", tagline: "Backend, databases, APIs, auth, systems" },
  { key: "dsa", label: "DSA", tagline: "Algorithms, data structures, complexity" },
  { key: "project_deep_dive", label: "Project Deep Dive", tagline: "Architecture, trade-offs, failures" },
  { key: "behavioral", label: "Behavioral", tagline: "Leadership, conflict, failure, ownership" },
];

export default function App() {
  const interview = useInterview();
  const {
    state,
    loading,
    error,
    setError,
    modelOnline,
    checkHealth,
    pendingResume,
    continueRestored,
    startNewFromResume,
    uploadResume,
    startInterview,
    submitAnswer,
    nextQuestion,
    generateReport,
    setAnswer,
    setRole,
    setInterviewType,
    setTotalQuestions,
    reset,
  } = interview;

  const [modes, setModes] = useState(FALLBACK_MODES);

  // The mode catalogue comes from the backend so the two stay in sync; the
  // fallback above means a dead backend still renders a usable UI.
  useEffect(() => {
    let cancelled = false;

    api
      .modes()
      .then((data) => {
        if (!cancelled && Array.isArray(data.modes) && data.modes.length) {
          setModes(data.modes);
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, []);

  const { profile, question, answer, evaluation, history, report } = state;

  const isAttack = state.interviewType === "Resume Attack";
  const answered = history.length;
  const finished = Boolean(report);
  const interviewStarted = Boolean(question) || answered > 0;
  const reachedLimit = answered >= state.totalQuestions;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-900">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-5 py-5">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white sm:text-2xl">PrepMate</h1>
            <p className="mt-0.5 text-sm text-zinc-500">
              A private AI interviewer that reads your resume, adapts to your answers, and checks whether you
              can defend your claims.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <PrivacyBadge />
            {interviewStarted && (
              <DangerButton onClick={reset} disabled={Boolean(loading)}>
                <RotateCcw className="mr-1.5 inline size-3.5" aria-hidden="true" />
                Reset interview
              </DangerButton>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-5 py-8">
        {pendingResume && <RestoreBanner pending={pendingResume} onContinue={continueRestored} onNew={startNewFromResume} />}

        {error && <ErrorNotice error={error} onRetry={checkHealth} onDismiss={() => setError(null)} />}

        {loading && <Loading label={loading} sublabel="Gemma is generating on your machine. This can take up to a minute on CPU." />}

        {/* ---------- Step 1: resume ---------- */}
        {!profile && !pendingResume && !loading && (
          <ResumeUpload
            onUpload={uploadResume}
            loading={loading}
            modelOnline={modelOnline}
            onRetryHealth={checkHealth}
          />
        )}

        {/* ---------- Step 2 & 3: profile + setup ---------- */}
        {profile && !interviewStarted && !pendingResume && (
          <ProfileSetup
            profile={profile}
            filename={state.filename}
            ocrUsed={state.ocrUsed}
            role={state.role}
            interviewType={state.interviewType}
            modes={modes}
            totalQuestions={state.totalQuestions}
            onRole={setRole}
            onInterviewType={setInterviewType}
            onTotalQuestions={setTotalQuestions}
            onStart={() => startInterview()}
            loading={loading}
            onReset={reset}
          />
        )}

        {/* ---------- In progress ---------- */}
        {profile && interviewStarted && !finished && !pendingResume && (
          <>
            <Dashboard
              role={state.role}
              interviewType={state.interviewType}
              questionNumber={state.questionNumber}
              totalQuestions={state.totalQuestions}
              topic={state.topic}
              history={history}
            />

            <ProgressBar
              value={answered}
              total={state.totalQuestions}
              label={reachedLimit ? "Question limit reached" : "Interview progress"}
            />

            <QuestionCard
              question={question}
              topic={state.topic}
              difficulty={state.difficulty}
              number={answered + 1}
              total={state.totalQuestions}
              isAttack={isAttack}
              claim={state.claim}
            />

            <AnswerBox
              value={answer}
              onChange={setAnswer}
              onSubmit={submitAnswer}
              disabled={Boolean(evaluation) || Boolean(loading)}
              loading={Boolean(loading)}
              submitLabel={isAttack ? "Submit defence" : "Submit answer"}
            />

            {isAttack ? (
              <ClaimFeedback evaluation={evaluation} onNext={nextQuestion} loading={Boolean(loading)} />
            ) : (
              <AnswerFeedback evaluation={evaluation} onNext={nextQuestion} loading={Boolean(loading)} />
            )}

            {answered > 0 && (
              <div className="flex flex-wrap gap-3 pt-2">
                <GhostButton onClick={generateReport} disabled={Boolean(loading)}>
                  End interview &amp; generate report
                </GhostButton>
              </div>
            )}

            <HistoryTimeline history={history} />
          </>
        )}

        {/* ---------- Report ---------- */}
        {finished && (
          <>
            <ReportView report={report} onRegenerate={generateReport} onReset={reset} loading={Boolean(loading)} />
            <HistoryTimeline history={history} />
          </>
        )}

        {!profile && !interviewStarted && !pendingResume && !loading && (
          <HowItWorks />
        )}
      </main>

      <footer className="border-t border-zinc-900 px-5 py-6">
        <p className="mx-auto max-w-5xl text-xs leading-relaxed text-zinc-600">
          PrepMate runs entirely on your machine: the PDF is parsed locally, and every model call goes to
          Ollama on <code className="text-zinc-500">localhost</code>. Your resume and answers are never sent to
          a cloud provider, which means the interview keeps working with Wi-Fi switched off.
        </p>
      </footer>
    </div>
  );
}

/** Phase 10: make persistence visible during the demo. */
function RestoreBanner({ pending, onContinue, onNew }) {
  const answered = Array.isArray(pending.history) ? pending.history.length : 0;

  return (
    <div className="rounded-2xl border border-indigo-800/70 bg-indigo-950/30 p-6">
      <h2 className="text-lg font-semibold text-indigo-100">Welcome back.</h2>

      <p className="mt-2 text-sm leading-relaxed text-indigo-200/80">
        Your previous interview session was restored from this browser.
        {answered > 0 ? (
          <>
            {" "}
            You had answered{" "}
            <strong className="text-indigo-100">
              question {Math.min(answered + 1, pending.totalQuestions)} of {pending.totalQuestions}
            </strong>{" "}
            as <strong className="text-indigo-100">{pending.interviewType}</strong> for{" "}
            <strong className="text-indigo-100">{pending.role}</strong>
            {pending.profile?.name ? ` · ${pending.profile.name}` : ""}.
          </>
        ) : (
          <> You were about to answer your first question.</>
        )}
      </p>

      {pending.question && (
        <p className="mt-3 line-clamp-2 rounded-xl bg-black/25 px-3 py-2 text-sm leading-relaxed text-zinc-400">
          {pending.question}
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          onClick={onContinue}
          className="rounded-xl bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-400"
        >
          Continue interview
        </button>

        <button
          onClick={onNew}
          className="rounded-xl border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:bg-zinc-800"
        >
          Start new interview
        </button>
      </div>
    </div>
  );
}

/** Shown before a resume exists, so the value proposition lands first. */
function HowItWorks() {
  const steps = [
    {
      title: "Read your resume",
      body: "Gemma extracts your skills, projects and measurable claims locally — with OCR fallback for scanned PDFs.",
    },
    {
      title: "Ask grounded questions",
      body: "Questions come from what is actually on your resume, not a generic question bank.",
    },
    {
      title: "Follow up on your weak spots",
      body: "After each answer the evaluator writes the exact next question, aimed at what you glossed over.",
    },
    {
      title: "Challenge your claims",
      body: "Resume Attack Mode picks one claim and asks something only real understanding can answer.",
    },
    {
      title: "Give you a plan",
      body: "A final report lists your real gaps and a practice plan you can act on this week.",
    },
  ];

  return (
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {steps.map((step, index) => (
        <div key={step.title} className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
          <span className="text-xs font-semibold text-indigo-400">{String(index + 1).padStart(2, "0")}</span>
          <h3 className="mt-1 text-sm font-semibold text-zinc-100">{step.title}</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-zinc-500">{step.body}</p>
        </div>
      ))}
    </section>
  );
}
