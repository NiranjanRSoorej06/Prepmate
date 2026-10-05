import { Loader2, Lock, WifiOff } from "lucide-react";

/** Loading state. Gemma is slow, so the UI must never look frozen. */
export function Loading({ label, sublabel }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/60 px-6 py-10 text-center">
      <Loader2 className="size-6 animate-spin text-indigo-400" aria-hidden="true" />
      <p className="text-sm font-medium text-zinc-200">{label}</p>
      {sublabel && <p className="max-w-md text-xs text-zinc-500">{sublabel}</p>}
    </div>
  );
}

/** Error state with an optional retry and a technical hint. */
export function ErrorNotice({ error, onRetry, onDismiss }) {
  if (!error) return null;

  const hint = error.hint;

  return (
    <div role="alert" className="rounded-2xl border border-red-900/70 bg-red-950/40 p-5">
      <div className="flex items-start gap-3">
        <WifiOff className="mt-0.5 size-5 shrink-0 text-red-400" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-red-200">Something went wrong</p>
          <p className="mt-1 text-sm leading-relaxed text-red-100/90">{error.message || String(error)}</p>

          {hint && (
            <p className="mt-2 rounded-lg bg-black/30 px-3 py-2 font-mono text-xs text-red-200/80">
              {hint}
            </p>
          )}

          {(onRetry || onDismiss) && (
            <div className="mt-4 flex flex-wrap gap-2">
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="rounded-lg bg-red-500/90 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-500"
                >
                  Try again
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={onDismiss}
                  className="rounded-lg border border-red-800 px-4 py-2 text-sm text-red-200 transition hover:bg-red-950"
                >
                  Dismiss
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Persistent "this never leaves your machine" indicator. */
export function PrivacyBadge({ detail }) {
  return (
    <span
      title={detail || "Your resume and answers never leave this machine."}
      className="inline-flex items-center gap-1.5 rounded-full border border-emerald-800/70 bg-emerald-950/40 px-2.5 py-1 text-[11px] font-medium text-emerald-300"
    >
      <Lock className="size-3" aria-hidden="true" />
      Runs locally on Gemma
    </span>
  );
}

/** One score out of 10, colour-coded so weak areas are obvious at a glance. */
export function ScoreCard({ label, score, hint }) {
  const numeric = typeof score === "number" ? score : Number(score);

  const tone =
    !Number.isFinite(numeric) || numeric < 5
      ? "text-red-300 border-red-900/60 bg-red-950/30"
      : numeric < 7
        ? "text-amber-300 border-amber-900/60 bg-amber-950/30"
        : "text-emerald-300 border-emerald-900/60 bg-emerald-950/30";

  return (
    <div className={`rounded-xl border p-4 text-center ${tone}`}>
      <div className="text-3xl font-bold tabular-nums">
        {Number.isFinite(numeric) ? numeric : "—"}
        <span className="text-base font-medium opacity-60">/10</span>
      </div>
      <div className="mt-1 text-xs font-medium uppercase tracking-wide opacity-80">{label}</div>
      {hint && <div className="mt-1 text-[11px] opacity-60">{hint}</div>}
    </div>
  );
}

/** Horizontal progress bar for "question 4 of 5". */
export function ProgressBar({ value, total, label }) {
  const safeTotal = Number(total) > 0 ? Number(total) : 1;
  const safeValue = Math.max(0, Math.min(Number(value) || 0, safeTotal));
  const percent = Math.round((safeValue / safeTotal) * 100);

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-xs">
        <span className="font-medium text-zinc-400">{label}</span>
        <span className="tabular-nums text-zinc-500">
          {safeValue} / {safeTotal}
        </span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-zinc-800"
        role="progressbar"
        aria-valuenow={safeValue}
        aria-valuemin={0}
        aria-valuemax={safeTotal}
        aria-label={label}
      >
        <div
          className="h-full rounded-full bg-indigo-500 transition-[width] duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

/** Bulleted list that renders nothing for an empty collection. */
export function BulletList({ items, tone = "default", empty }) {
  if (!Array.isArray(items) || items.length === 0) {
    return empty ? <p className="text-sm text-zinc-500">{empty}</p> : null;
  }

  const toneClass =
    tone === "good"
      ? "text-emerald-200"
      : tone === "bad"
        ? "text-amber-200"
        : "text-zinc-300";

  return (
    <ul className={`space-y-1.5 text-sm leading-relaxed ${toneClass}`}>
      {items.map((item, index) => (
        <li key={index} className="flex gap-2">
          <span aria-hidden="true" className="mt-1.5 size-1 shrink-0 rounded-full bg-current opacity-60" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

/** Neutral wrapper for a titled block of content. */
export function Panel({ title, action, children, className = "" }) {
  return (
    <section className={`rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-4">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** Primary call-to-action button. */
export function PrimaryButton({ children, onClick, disabled, type = "button", className = "" }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-xl bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40 ${className}`}
    >
      {children}
    </button>
  );
}

/** Secondary / ghost button. */
export function GhostButton({ children, onClick, disabled, type = "button", className = "" }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-xl border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40 ${className}`}
    >
      {children}
    </button>
  );
}

/** Danger button, used for Reset Interview. */
export function DangerButton({ children, onClick, disabled, className = "" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-xl border border-red-900/70 px-4 py-2 text-sm font-medium text-red-300 transition hover:bg-red-950/50 disabled:cursor-not-allowed disabled:opacity-40 ${className}`}
    >
      {children}
    </button>
  );
}
