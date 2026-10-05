import { Award, Check, RefreshCw, TriangleAlert, X } from "lucide-react";
import { useState } from "react";

import { BulletList, DangerButton, GhostButton, Panel, PrimaryButton, ScoreCard } from "./ui.jsx";

/** Phase 8 — the end-of-interview report. */
export function ReportView({ report, onRegenerate, onReset, loading }) {
  const [copied, setCopied] = useState(false);

  if (!report) return null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(report.text || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="space-y-5">
      <Panel
        title={
          <span className="flex items-center gap-2">
            <Award className="size-4 text-indigo-400" aria-hidden="true" />
            PrepMate interview report
          </span>
        }
        action={
          <div className="flex gap-2">
            <GhostButton onClick={copy}>{copied ? "Copied" : "Copy as text"}</GhostButton>
            <GhostButton onClick={onRegenerate} disabled={Boolean(loading)}>
              <RefreshCw className="mr-1.5 inline size-3.5" aria-hidden="true" />
              Regenerate
            </GhostButton>
          </div>
        }
      >
        {report.degraded && (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-900/60 bg-amber-950/30 p-3 text-xs leading-relaxed text-amber-200/90">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            The written summary could not be generated on this attempt, so this report is built directly from
            the per-answer evaluations. Regenerate to try the full version again.
          </div>
        )}

        <div className="mb-5 flex flex-wrap items-center gap-4">
          <div>
            <p className="text-5xl font-bold tabular-nums text-white">
              {report.overall_score}
              <span className="text-xl font-medium text-zinc-500">/10</span>
            </p>
            <p className="mt-1 text-xs uppercase tracking-wide text-zinc-500">
              overall · {report.questions_asked} answered
              {report.readiness ? ` · ${report.readiness}` : ""}
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <ScoreCard label="Technical accuracy" score={report.technical_accuracy} />
          <ScoreCard label="Communication" score={report.communication} />
          <ScoreCard label="Depth" score={report.depth} />
        </div>

        {report.summary && (
          <p className="mt-5 rounded-xl bg-zinc-800/50 px-4 py-3 text-sm leading-relaxed text-zinc-300">
            {report.summary}
          </p>
        )}
      </Panel>

      <div className="grid gap-5 sm:grid-cols-2">
        <Panel title="Strongest areas">
          <BulletList items={report.strongest_areas} tone="good" empty="Not enough data to call a strength yet." />
        </Panel>

        <Panel title="Needs improvement">
          <BulletList items={report.weakest_areas} tone="bad" empty="No clear weak area yet." />
        </Panel>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <Panel
          title={
            <span className="flex items-center gap-2">
              <Check className="size-4 text-emerald-400" aria-hidden="true" />
              Resume claims you defended
            </span>
          }
        >
          <BulletList
            items={report.claims_defended}
            tone="good"
            empty="Run Resume Attack Mode to find out which claims you can hold up."
          />
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2">
              <X className="size-4 text-amber-400" aria-hidden="true" />
              Claims needing preparation
            </span>
          }
        >
          <BulletList
            items={report.claims_needing_work}
            tone="bad"
            empty="Run Resume Attack Mode to find out which claims you can hold up."
          />
        </Panel>
      </div>

      <Panel title="Topics to revise">
        <BulletList items={report.topics_to_revise} empty="Nothing flagged for revision." />
      </Panel>

      {Array.isArray(report.practice_plan) && report.practice_plan.length > 0 && (
        <Panel title="Recommended practice plan">
          <ol className="space-y-3">
            {report.practice_plan.map((step, index) => (
              <li key={index} className="flex gap-3">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-indigo-500/15 text-xs font-semibold text-indigo-300">
                  {step.step || index + 1}
                </span>
                <div className="min-w-0">
                  {step.focus && <p className="text-sm font-medium text-zinc-200">{step.focus}</p>}
                  <p className="text-sm leading-relaxed text-zinc-400">{step.action}</p>
                  {step.why && <p className="mt-0.5 text-xs text-zinc-600">{step.why}</p>}
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      )}

      {Array.isArray(report.next_interview_focus) && report.next_interview_focus.length > 0 && (
        <Panel title="Open the next session with">
          <BulletList items={report.next_interview_focus} />
        </Panel>
      )}

      <div className="flex flex-wrap gap-3 pt-1">
        <PrimaryButton onClick={onReset}>Start a new interview</PrimaryButton>
        <DangerButton onClick={onReset}>Reset everything</DangerButton>
      </div>
    </div>
  );
}
