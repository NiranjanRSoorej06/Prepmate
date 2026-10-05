/**
 * Interview session persistence.
 *
 * The session of record lives in localStorage so a refresh — or closing the
 * laptop — never destroys an interview. The PDF itself is deliberately NOT
 * stored: it stays on the backend, and only the derived profile and the
 * session id are kept here.
 */

export const STORAGE_KEY = "prepmate_interview";

export const STORAGE_VERSION = 2;

export function emptyState() {
  return {
    version: STORAGE_VERSION,
    profile: null,
    sessionId: null,
    filename: "",
    ocrUsed: false,
    role: "Backend Software Engineer",
    interviewType: "Technical",
    question: "",
    topic: "",
    difficulty: 5,
    claim: "",
    answer: "",
    evaluation: null,
    history: [],
    attackedClaims: [],
    report: null,
    questionNumber: 0,
    totalQuestions: 5,
    updatedAt: 0,
  };
}

/**
 * Read a saved session.
 *
 * Anything unreadable, corrupt or from an older incompatible build is
 * discarded and treated as "no session" — a corrupt value must never be able
 * to crash the app on load.
 */
export function loadInterviewState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (!saved) return null;

    const parsed = JSON.parse(saved);

    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }

    if (parsed.version !== STORAGE_VERSION) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }

    const base = emptyState();

    // Only take fields we know about, and only from the right type. This is
    // what makes a hand-edited or half-written value harmless.
    const merged = { ...base };

    for (const key of Object.keys(base)) {
      const value = parsed[key];

      if (value === undefined || value === null) continue;
      if (typeof value !== typeof base[key]) continue;

      if (Array.isArray(base[key]) && !Array.isArray(value)) continue;

      merged[key] = value;
    }

    if (!merged.profile || typeof merged.profile !== "object") {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }

    return merged;
  } catch {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Storage can be unavailable entirely (private mode); ignore.
    }

    return null;
  }
}

export function saveInterviewState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...state, updatedAt: Date.now() }));
    return true;
  } catch {
    // Quota exceeded or storage disabled. The interview still works in memory.
    return false;
  }
}

export function clearInterviewState() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore — nothing else to do if storage is unavailable.
  }
}

/** A session is only worth restoring if it has something to restore. */
export function isResumable(state) {
  return Boolean(
    state &&
      state.profile &&
      (state.question || (Array.isArray(state.history) && state.history.length > 0) || state.report),
  );
}
