import { Brain, FileText, RotateCcw, Sparkles, Upload } from "lucide-react";
import { useState } from "react";

import { GhostButton, Loading, Panel, PrivacyBadge, PrimaryButton } from "./ui.jsx";

/**
 * Step 1: upload a resume.
 *
 * Kept deliberately plain — the interesting part of PrepMate starts once Gemma
 * has read the resume.
 */
export function ResumeUpload({ onUpload, loading, disabled, modelOnline, onRetryHealth }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);

  function pick(next) {
    if (next) setFile(next);
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);

    const dropped = event.dataTransfer.files?.[0];

    if (dropped) pick(dropped);
  }

  return (
    <div className="space-y-5">
      <Panel
        title="Step 1 · Upload your resume"
        action={<PrivacyBadge detail="The PDF is read on your machine. Only the extracted profile is kept in your browser." />}
      >
        <p className="mb-5 text-sm leading-relaxed text-zinc-400">
          PrepMate reads your resume with a local Gemma model and builds a candidate profile from it. Every
          question afterwards is grounded in what is actually on the page.
        </p>

        {modelOnline === false && (
          <div className="mb-5 rounded-xl border border-amber-900/60 bg-amber-950/30 p-4 text-sm">
            <p className="font-medium text-amber-200">Gemma is not reachable right now.</p>
            <p className="mt-1 text-amber-100/70">
              Start Ollama and pull the model, then check again:
              <code className="ml-1 rounded bg-black/30 px-1.5 py-0.5 font-mono text-xs">ollama serve</code>{" "}
              <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono text-xs">ollama pull gemma3:4b</code>
            </p>
            <button
              onClick={onRetryHealth}
              className="mt-3 rounded-lg border border-amber-800 px-3 py-1.5 text-xs font-medium text-amber-200 transition hover:bg-amber-950/60"
            >
              Check again
            </button>
          </div>
        )}

        <label
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragging
              ? "border-indigo-400 bg-indigo-500/10"
              : "border-zinc-700 hover:border-zinc-600 hover:bg-zinc-800/40"
          }`}
        >
          <input
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(event) => pick(event.target.files?.[0])}
          />

          <span className="rounded-full bg-zinc-800 p-3 text-indigo-400">
            <Upload className="size-5" aria-hidden="true" />
          </span>

          {file ? (
            <>
              <span className="text-sm font-medium text-zinc-200">{file.name}</span>
              <span className="text-xs text-zinc-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB · click to choose a different file
              </span>
            </>
          ) : (
            <>
              <span className="text-sm font-medium text-zinc-200">Drop a PDF resume here</span>
              <span className="text-xs text-zinc-500">or click to browse · PDF only · scanned PDFs work via OCR</span>
            </>
          )}
        </label>

        <div className="mt-5 flex items-center gap-3">
          <PrimaryButton onClick={() => onUpload(file)} disabled={!file || disabled || Boolean(loading)}>
            {loading ? "Analyzing..." : "Analyze resume"}
          </PrimaryButton>

          {file && (
            <GhostButton onClick={() => setFile(null)} disabled={Boolean(loading)}>
              Clear
            </GhostButton>
          )}
        </div>

        {loading && (
          <div className="mt-4">
            <Loading
              label={loading}
              sublabel="A 4B model on CPU takes a few seconds. This happens entirely on your machine."
            />
          </div>
        )}
      </Panel>
    </div>
  );
}

/**
 * Step 2: show what Gemma understood, then choose the interview.
 *
 * Showing the extracted profile is not decoration — it is how the candidate
 * catches a hallucination before a whole interview is built on it.
 */
export function ProfileSetup({ profile, filename, ocrUsed, role, interviewType, modes, totalQuestions, onRole, onInterviewType, onTotalQuestions, onStart, loading, onReset }) {
  const [showProfile, setShowProfile] = useState(false);

  const skills = Array.isArray(profile?.skills) ? profile.skills : [];
  const projects = Array.isArray(profile?.projects) ? profile.projects : [];
  const claims = Array.isArray(profile?.claims) ? profile.claims : [];

  return (
    <div className="space-y-5">
      <Panel
        title="Step 2 · Candidate profile"
        action={
          <GhostButton onClick={() => setShowProfile((value) => !value)}>
            {showProfile ? "Hide profile" : "Show full profile"}
          </GhostButton>
        }
      >
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-2 text-lg font-semibold text-zinc-100">
            <FileText className="size-4 text-indigo-400" aria-hidden="true" />
            {profile?.name || "Candidate"}
          </span>
          <PrivacyBadge />
          {ocrUsed && (
            <span className="rounded-full border border-amber-900/60 bg-amber-950/30 px-2.5 py-1 text-[11px] text-amber-300">
              read via OCR
            </span>
          )}
          {filename && <span className="truncate text-xs text-zinc-500">{filename}</span>}
        </div>

        {skills.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Skills</p>
            <div className="flex flex-wrap gap-1.5">
              {skills.slice(0, 24).map((skill, index) => (
                <span
                  key={index}
                  className="rounded-full border border-zinc-700 bg-zinc-800/70 px-2.5 py-1 text-xs text-zinc-300"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {projects.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
              Projects ({projects.length})
            </p>
            <ul className="space-y-2">
              {projects.slice(0, 5).map((project, index) => (
                <li key={index} className="rounded-xl bg-zinc-800/50 px-3 py-2 text-sm">
                  <span className="font-medium text-zinc-200">
                    {typeof project === "string" ? project : project.name}
                  </span>
                  {typeof project === "object" && project?.technologies?.length > 0 && (
                    <span className="ml-2 text-xs text-zinc-500">{project.technologies.join(" · ")}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {claims.length > 0 && (
          <div className="mt-4 rounded-xl border border-indigo-900/50 bg-indigo-950/20 p-3">
            <p className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-indigo-300">
              <Sparkles className="size-3.5" aria-hidden="true" />
              {claims.length} claim{claims.length === 1 ? "" : "s"} PrepMate can challenge
            </p>
            <ul className="space-y-1 text-xs text-zinc-400">
              {claims.slice(0, 4).map((claim, index) => (
                <li key={index} className="flex gap-2">
                  <span aria-hidden="true" className="mt-1.5 size-1 shrink-0 rounded-full bg-indigo-400" />
                  <span>{typeof claim === "string" ? claim : claim.claim}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {showProfile && (
          <pre className="mt-4 max-h-80 overflow-auto rounded-xl bg-black/40 p-4 text-xs leading-relaxed text-zinc-400">
            {JSON.stringify(profile, null, 2)}
          </pre>
        )}

        <p className="mt-4 text-xs text-zinc-500">
          Spot something missing or wrong? PrepMate only reports what the resume supports — a correction here
          improves every question that follows.
        </p>
      </Panel>

      <Panel title="Step 3 · Choose the interview">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              Target role
            </span>
            <input
              value={role}
              onChange={(event) => onRole(event.target.value)}
              placeholder="Backend Software Engineer"
              className="w-full rounded-xl border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-indigo-500"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              Questions
            </span>
            <input
              type="number"
              min={1}
              max={20}
              value={totalQuestions}
              onChange={(event) => onTotalQuestions(Number(event.target.value))}
              className="w-full rounded-xl border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-indigo-500"
            />
          </label>
        </div>

        <div className="mt-5">
          <p className="mb-2.5 text-xs font-medium uppercase tracking-wide text-zinc-500">Interview mode</p>
          <div className="grid gap-2.5 sm:grid-cols-2">
            {[...modes, { key: "resume_attack", label: "Resume Attack", tagline: "Challenge your claims" }].map(
              (mode) => {
                const selected = interviewType === mode.label;

                return (
                  <button
                    key={mode.key}
                    onClick={() => onInterviewType(mode.label)}
                    disabled={Boolean(loading)}
                    className={`rounded-xl border p-3.5 text-left transition disabled:opacity-50 ${
                      selected
                        ? "border-indigo-500 bg-indigo-500/10"
                        : "border-zinc-800 bg-zinc-800/40 hover:border-zinc-700"
                    }`}
                  >
                    <span className={`block text-sm font-semibold ${selected ? "text-indigo-200" : "text-zinc-200"}`}>
                      {mode.label}
                    </span>
                    <span className="mt-0.5 block text-xs text-zinc-500">{mode.tagline}</span>
                  </button>
                );
              },
            )}
          </div>

          {interviewType === "Resume Attack" && (
            <p className="mt-3 flex items-start gap-2 rounded-xl border border-indigo-900/50 bg-indigo-950/30 p-3 text-xs leading-relaxed text-indigo-200/80">
              <Brain className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Resume Attack picks one concrete claim from your resume and asks a question that only someone who
              actually did the work could answer well. Then it scores how well you defended it.
            </p>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <PrimaryButton onClick={onStart} disabled={Boolean(loading)}>
            {loading ? "Preparing..." : "Start interview"}
          </PrimaryButton>

          <GhostButton onClick={onReset}>
            <RotateCcw className="mr-1.5 inline size-3.5" aria-hidden="true" />
            Start over
          </GhostButton>
        </div>
      </Panel>
    </div>
  );
}
