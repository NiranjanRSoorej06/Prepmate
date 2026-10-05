import { useCallback, useEffect, useState } from "react";

import { api } from "../api.js";
import { clearInterviewState, emptyState, isResumable, loadInterviewState, saveInterviewState } from "../storage.js";

/**
 * The whole interview lives in one state object so it can be written to
 * localStorage as a single unit. That is what makes a refresh lossless: there
 * is no second place where interview state can hide.
 */
export function useInterview() {
  // Hydrate during the first render rather than in an effect: reading
  // localStorage is synchronous, so there is no reason to render an empty
  // interview for one frame and then correct it.
  const [restored] = useState(() => loadInterviewState());
  const resumable = isResumable(restored);

  const [state, setState] = useState(() => (resumable ? restored : emptyState()));

  // `pendingResume` drives the Phase 10 restoration screen: we restore into
  // memory but do not take over the screen until the candidate chooses.
  const [pendingResume, setPendingResume] = useState(() => (resumable ? restored : null));

  const [loading, setLoading] = useState("");
  const [error, setError] = useState(null);
  const [modelOnline, setModelOnline] = useState(null);

  // ---------------------------------------------------------------
  // Persistence
  // ---------------------------------------------------------------

  // Autosave. Only a session that has actually started is written, so a
  // casual page visit does not litter storage.
  useEffect(() => {
    if (isResumable(state)) {
      saveInterviewState(state);
    }
  }, [state]);

  const patch = useCallback((changes) => {
    setState((previous) => ({ ...previous, ...changes }));
  }, []);

  const reset = useCallback(() => {
    clearInterviewState();
    setState(emptyState());
    setPendingResume(null);
    setError(null);
    setLoading("");
  }, []);

  const continueRestored = useCallback(() => {
    setPendingResume(null);
  }, []);

  const startNewFromResume = useCallback(() => {
    // Keep the profile, throw away the interview in progress.
    setPendingResume(null);
    setState((previous) => ({
      ...emptyState(),
      profile: previous.profile,
      sessionId: previous.sessionId,
      filename: previous.filename,
    }));
  }, []);

  // ---------------------------------------------------------------
  // Model health
  // ---------------------------------------------------------------

  const checkHealth = useCallback(async () => {
    try {
      await api.health();
      setModelOnline(true);
    } catch {
      setModelOnline(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    // Sync with the backend, an external system: ask once on mount and drop
    // the result if the view goes away first.
    api
      .health()
      .then(() => {
        if (!cancelled) setModelOnline(true);
      })
      .catch(() => {
        if (!cancelled) setModelOnline(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // ---------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------

  const uploadResume = useCallback(async (file) => {
    setLoading("Analyzing resume...");
    setError(null);

    try {
      const data = await api.uploadResume(file);

      setState((previous) => ({
        ...emptyState(),
        profile: data.profile,
        sessionId: data.session_id,
        filename: data.filename,
        ocrUsed: Boolean(data.ocr_used),
        totalQuestions: previous.totalQuestions || 5,
      }));

      return data;
    } catch (caught) {
      setError(toError(caught));
      return null;
    } finally {
      setLoading("");
    }
  }, []);

  const startInterview = useCallback(
    async (overrides = {}) => {
      const next = { ...state, ...overrides };

      setLoading(next.interviewType === "Resume Attack" ? "Finding a claim to challenge..." : "Generating question...");
      setError(null);

      try {
        if (next.interviewType === "Resume Attack") {
          const data = await api.attackQuestion({
            resume_profile: next.profile,
            role: next.role,
            resume_text: undefined,
            session_id: next.sessionId,
            attacked_claims: next.attackedClaims || [],
          });

          setState((previous) => ({
            ...previous,
            role: next.role,
            interviewType: next.interviewType,
            question: data.question,
            topic: data.category,
            difficulty: data.difficulty,
            claim: data.claim,
            answer: "",
            evaluation: null,
            questionNumber: 1,
          }));

          return;
        }

        const data = await api.question({
          resume_profile: next.profile,
          role: next.role,
          interview_type: next.interviewType,
          history: next.history,
        });

        setState((previous) => ({
          ...previous,
          role: next.role,
          interviewType: next.interviewType,
          question: data.question,
          topic: data.topic,
          difficulty: data.difficulty,
          answer: "",
          evaluation: null,
          questionNumber: (previous.questionNumber || 0) + 1,
        }));
      } catch (caught) {
        setError(toError(caught));
      } finally {
        setLoading("");
      }
    },
    [state],
  );

  const submitAnswer = useCallback(async () => {
    const isAttack = state.interviewType === "Resume Attack";

    setLoading(isAttack ? "Assessing your defence of this claim..." : "Evaluating answer...");
    setError(null);

    try {
      const payload = {
        resume_profile: state.profile,
        question: state.question,
        answer: state.answer,
      };

      const evaluation = isAttack
        ? await api.attackEvaluate({ ...payload, claim: state.claim || "" })
        : await api.evaluate({ ...payload, interview_type: state.interviewType });

      const entry = {
        question: state.question,
        answer: state.answer,
        evaluation,
        topic: state.topic || evaluation.topic || "",
        kind: isAttack ? "attack" : "question",
        claim: isAttack ? state.claim || "" : "",
      };

      setState((previous) => ({
        ...previous,
        evaluation,
        history: [...previous.history, entry],
        attackedClaims: isAttack && previous.claim ? [...previous.attackedClaims, previous.claim] : previous.attackedClaims,
      }));

      setModelOnline(true);
    } catch (caught) {
      setError(toError(caught));
    } finally {
      setLoading("");
    }
  }, [state]);

  /**
   * Phase 3, the adaptive loop.
   *
   * If the evaluator wrote a follow-up we ask exactly that. Only when there is
   * no usable follow-up do we fall back to generating a fresh question.
   */
  const nextQuestion = useCallback(async () => {
    const followUp = state.evaluation?.follow_up;

    if (followUp && followUp.trim()) {
      setState((previous) => ({
        ...previous,
        question: followUp.trim(),
        topic: previous.evaluation?.topic || previous.topic || "",
        difficulty: Math.min(10, (previous.difficulty || 5) + 1),
        answer: "",
        evaluation: null,
        questionNumber: (previous.questionNumber || 0) + 1,
      }));

      return;
    }

    setLoading("Preparing follow-up...");
    setError(null);

    try {
      if (state.interviewType === "Resume Attack") {
        const data = await api.attackQuestion({
          resume_profile: state.profile,
          role: state.role,
          session_id: state.sessionId,
          attacked_claims: state.attackedClaims || [],
        });

        setState((previous) => ({
          ...previous,
          question: data.question,
          topic: data.category,
          claim: data.claim,
          difficulty: data.difficulty,
          answer: "",
          evaluation: null,
          questionNumber: (previous.questionNumber || 0) + 1,
        }));

        return;
      }

      const data = await api.question({
        resume_profile: state.profile,
        role: state.role,
        interview_type: state.interviewType,
        history: state.history,
      });

      setState((previous) => ({
        ...previous,
        question: data.question,
        topic: data.topic,
        difficulty: data.difficulty,
        answer: "",
        evaluation: null,
        questionNumber: (previous.questionNumber || 0) + 1,
      }));
    } catch (caught) {
      setError(toError(caught));
    } finally {
      setLoading("");
    }
  }, [state]);

  const generateReport = useCallback(async () => {
    setLoading("Generating final report...");
    setError(null);

    try {
      const data = await api.report({
        history: state.history,
        resume_profile: state.profile,
        role: state.role,
        interview_type: state.interviewType,
      });

      setState((previous) => ({ ...previous, report: data }));

      return data;
    } catch (caught) {
      setError(toError(caught));
      return null;
    } finally {
      setLoading("");
    }
  }, [state]);

  const loadClaimPool = useCallback(async () => {
    setLoading("Reading your resume for claims...");
    setError(null);

    try {
      const data = await api.attackClaims({
        resume_profile: state.profile,
        session_id: state.sessionId,
      });

      return data.claims || [];
    } catch (caught) {
      setError(toError(caught));
      return [];
    } finally {
      setLoading("");
    }
  }, [state.profile, state.sessionId]);

  const setAnswer = useCallback((value) => patch({ answer: value }), [patch]);

  const setRole = useCallback((value) => patch({ role: value }), [patch]);
  const setInterviewType = useCallback((value) => patch({ interviewType: value }), [patch]);
  const setTotalQuestions = useCallback((value) => patch({ totalQuestions: value }), [patch]);

  return {
    state,
    patch,
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
    loadClaimPool,
    setAnswer,
    setRole,
    setInterviewType,
    setTotalQuestions,
    reset,
  };
}

function toError(caught) {
  if (caught instanceof Error) return caught;

  return new Error("Something went wrong.");
}
