import { ChevronRight } from "lucide-react";
import { useEffect, useRef } from "react";

import { BulletList, Panel, PrimaryButton, ScoreCard } from "./ui.jsx";

/** Stat tiles above the fold while an interview is in progress. */
export function Dashboard({ role, interviewType, questionNumber, totalQuestions, topic, history }) {
  const answered = history.length;
  const overall = averageScore(history);

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Interview" value={interviewType || "—"} sub={role || ""} />
      <Stat
        label="Progress"
        value={`${answered} answered`}
        sub={`Question ${Math.max(questionNumber, answered, 1)} of ${totalQuestions}`}
      />
      <Stat label="Current topic" value={topic || "—"} sub="area being tested" />
      <Stat
        label="Average score"
        value={overall ? `${overall}/10` : "—"}
        sub="across all answers"
      />
    </div>
  );
}

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-zinc-100" title={value}>
        {value}
      </p>
      <p className="mt-0.5 truncate text-xs text-zinc-500" title={sub}>
        {sub}
      </p>
    </div>
  );
}

/** Mean of the three sub-scores, so the dashboard has one number to show. */
function averageScore(history) {
  if (!Array.isArray(history) || history.length === 0) return null;

  const totals = [];

  for (const item of history) {
    const evaluation = item?.evaluation;

    if (!evaluation) continue;

    const keys =
      item.kind === "attack"
        ? ["credibility_score", "technical_depth", "clarity"]
        : ["technical_accuracy", "communication", "depth"];

    const scores = keys
      .map((key) => Number(evaluation[key]))
      .filter((value) => Number.isFinite(value));

    if (scores.length) {
      totals.push(scores.reduce((sum, value) => sum + value, 0) / scores.length);
    }
  }

  if (!totals.length) return null;

  return Math.round((totals.reduce((sum, value) => sum + value, 0) / totals.length) * 10) / 10;
}

/**
 * Phase 9: the question is the visually dominant element on the screen —
 * everything else is secondary to it.
 */
export function QuestionCard({ question, topic, difficulty, number, total, isAttack, claim }) {
  return (
    <section className="relative overflow-hidden rounded-2xl border border-indigo-900/60 bg-gradient-to-br from-indigo-950/40 via-zinc-900/60 to-zinc-900/60 p-6 sm:p-8">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-indigo-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-indigo-300">
          Question {Math.max(number, 1)}
          {total ? ` of ${total}` : ""}
        </span>

        {topic && (
          <span className="rounded-full border border-zinc-700 bg-zinc-800/60 px-2.5 py-1 text-[11px] text-zinc-400">
            {topic}
          </span>
        )}

        {difficulty > 0 && (
          <span className="rounded-full border border-zinc-700 bg-zinc-800/60 px-2.5 py-1 text-[11px] text-zinc-400">
            Difficulty {difficulty}/10
          </span>
        )}

        {isAttack && (
          <span className="rounded-full bg-fuchsia-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-fuchsia-300">
            Resume claim under test
          </span>
        )}
      </div>

      {isAttack && claim && (
        <blockquote className="mb-5 rounded-xl border border-fuchsia-900/40 bg-black/30 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-fuchsia-300/80">
            Claim from your resume
          </p>
          <p className="mt-1 text-sm leading-relaxed text-zinc-300">{claim}</p>
        </blockquote>
      )}

      <p className="text-xl leading-snug font-semibold text-balance text-white sm:text-2xl">
        {question}
      </p>
    </section>
  );
}

/** Answer box with a live word count — verbosity is a real interview weakness. */
export function AnswerBox({ value, onChange, onSubmit, disabled, loading, submitLabel = "Submit answer" }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!disabled) ref.current?.focus();
  }, [disabled]);

  const words = value.trim() ? value.trim().split(/\s+/).length : 0;

  return (
    <Panel
      title="Your answer"
      action={
        <span className="text-xs tabular-nums text-zinc-500">
          {words} word{words === 1 ? "" : "s"}
        </span>
      }
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={9}
        placeholder="Answer as you would in a real interview — explain your reasoning, not just the conclusion."
        className="w-full resize-y rounded-xl border border-zinc-700 bg-zinc-800/60 px-4 py-3 text-sm leading-relaxed text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-indigo-500 disabled:opacity-60"
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <PrimaryButton onClick={onSubmit} disabled={disabled || !value.trim() || Boolean(loading)}>
          {loading ? "Evaluating..." : submitLabel}
        </PrimaryButton>

        {words === 0 && <span className="text-xs text-zinc-600">Write something first.</span>}
      </div>
    </Panel>
  );
}

/** Feedback for a regular interview answer. */
export function AnswerFeedback({ evaluation, onNext, loading, nextLabel = "Ask the follow-up" }) {
  if (!evaluation) return null;

  const followUp = (evaluation.follow_up || "").trim();

  return (
    <div className="space-y-5">
      <Panel title="Evaluation">
        <div className="grid gap-3 sm:grid-cols-3">
          <ScoreCard label="Accuracy" score={evaluation.technical_accuracy} />
          <ScoreCard label="Communication" score={evaluation.communication} />
          <ScoreCard label="Depth" score={evaluation.depth} />
        </div>

        {evaluation.verdict && (
          <p className="mt-4 rounded-xl bg-zinc-800/50 px-4 py-3 text-sm leading-relaxed text-zinc-300">
            {evaluation.verdict}
          </p>
        )}
      </Panel>

      <div className="grid gap-5 sm:grid-cols-2">
        <Panel title="Strengths">
          <BulletList items={evaluation.strengths} tone="good" empty="No clear strengths in this answer." />
        </Panel>

        <Panel title="Weaknesses">
          <BulletList items={evaluation.weaknesses} tone="bad" empty="Nothing stood out as weak." />
        </Panel>
      </div>

      {Array.isArray(evaluation.topics_to_revise) && evaluation.topics_to_revise.length > 0 && (
        <Panel title="Topics to revise">
          <BulletList items={evaluation.topics_to_revise} />
        </Panel>
      )}

      <Panel title="Suggested follow-up">
        <p className="text-sm leading-relaxed text-zinc-200">
          {followUp || "No follow-up was produced for this answer."}
        </p>
        <p className="mt-2 text-xs text-zinc-500">
          PrepMate asks this exact question next, because it goes straight at the weakest point.
        </p>

        <div className="mt-4">
          <PrimaryButton onClick={onNext} disabled={Boolean(loading)}>
            {loading ? "Preparing..." : nextLabel}
            <ChevronRight className="ml-1 inline size-4" aria-hidden="true" />
          </PrimaryButton>
        </div>
      </Panel>
    </div>
  );
}

/** A single titled list — used by both feedback views. */
export function FeedbackList({ title, icon, children }) {
  return (
    <Panel
      title={
        <span className="flex items-center gap-2">
          {icon}
          {title}
        </span>
      }
    >
      {children}
    </Panel>
  );
}
