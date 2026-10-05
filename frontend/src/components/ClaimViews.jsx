import { ChevronRight, CircleAlert, Fingerprint, ListChecks } from "lucide-react";

import { BulletList, Panel, PrimaryButton, ScoreCard } from "./ui.jsx";

/**
 * Phase 6 — claim credibility.
 *
 * Wording matters here: PrepMate is assessing how well a candidate can defend
 * a claim, not whether they are lying. Both the copy and the prompt avoid the
 * accusation framing.
 */
export function ClaimFeedback({ evaluation, onNext, loading }) {
  if (!evaluation) return null;

  const followUp = (evaluation.follow_up || "").trim();

  return (
    <div className="space-y-5">
      <Panel
        title={
          <span className="flex items-center gap-2">
            <Fingerprint className="size-4 text-fuchsia-400" aria-hidden="true" />
            How well you defended the claim
          </span>
        }
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <ScoreCard label="Credibility" score={evaluation.credibility_score} />
          <ScoreCard label="Technical depth" score={evaluation.technical_depth} />
          <ScoreCard label="Clarity" score={evaluation.clarity} />
        </div>

        {evaluation.verdict && (
          <p className="mt-4 rounded-xl bg-zinc-800/50 px-4 py-3 text-sm leading-relaxed text-zinc-300">
            {evaluation.verdict}
          </p>
        )}

        <p className="mt-4 flex items-start gap-2 text-xs leading-relaxed text-zinc-500">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          This measures how clearly and specifically you defended the claim — not whether you built it. Both a
          real project described vaguely and a borrowed one answered well score differently for a reason.
        </p>
      </Panel>

      <div className="grid gap-5 sm:grid-cols-2">
        <Panel
          title={
            <span className="flex items-center gap-2">
              <ListChecks className="size-4 text-emerald-400" aria-hidden="true" />
              Evidence you provided
            </span>
          }
        >
          <BulletList
            items={evaluation.evidence}
            tone="good"
            empty="Your answer contained no concrete evidence for this claim."
          />
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2">
              <CircleAlert className="size-4 text-amber-400" aria-hidden="true" />
              Gaps an interviewer would probe
            </span>
          }
        >
          <BulletList items={evaluation.gaps} tone="bad" empty="No significant gaps found." />
        </Panel>
      </div>

      <Panel title="Tightening this claim">
        <p className="text-sm leading-relaxed text-zinc-200">
          {followUp || "No follow-up was produced for this claim."}
        </p>

        <div className="mt-4">
          <PrimaryButton onClick={onNext} disabled={Boolean(loading)}>
            {loading ? "Preparing..." : "Next claim"}
            <ChevronRight className="ml-1 inline size-4" aria-hidden="true" />
          </PrimaryButton>
        </div>
      </Panel>
    </div>
  );
}

/** One representative score for a transcript entry. */
function scoreFor(item) {
  const evaluation = item.evaluation || {};

  const keys =
    item.kind === "attack"
      ? ["credibility_score", "technical_depth", "clarity"]
      : ["technical_accuracy", "communication", "depth"];

  const scores = keys.map((key) => Number(evaluation[key])).filter(Number.isFinite);

  if (!scores.length) return null;

  return Math.round((scores.reduce((sum, value) => sum + value, 0) / scores.length) * 10) / 10;
}

/**
 * Phase 4 — the running transcript.
 *
 * Kept visible because the adaptive loop only makes sense once you can see
 * that PrepMate is reacting to what you actually said.
 */
export function HistoryTimeline({ history }) {
  if (!Array.isArray(history) || history.length === 0) return null;

  return (
    <Panel title={`Transcript · ${history.length} answered`}>
      <ol className="space-y-4">
        {history.map((item, index) => {
          const isAttack = item.kind === "attack";
          const score = scoreFor(item);

          return (
            <li key={index} className="border-l-2 border-zinc-800 pl-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-zinc-500">#{index + 1}</span>
                {item.topic && (
                  <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-400">
                    {item.topic}
                  </span>
                )}
                {isAttack && (
                  <span className="rounded-full bg-fuchsia-500/15 px-2 py-0.5 text-[10px] text-fuchsia-300">
                    claim
                  </span>
                )}
                {score !== null && <span className="text-xs tabular-nums text-zinc-400">{score}/10</span>}
              </div>

              <p className="mt-1 text-sm leading-relaxed font-medium text-zinc-200">{item.question}</p>

              {item.answer && (
                <p className="mt-1 line-clamp-3 text-sm leading-relaxed text-zinc-500">{item.answer}</p>
              )}
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}
