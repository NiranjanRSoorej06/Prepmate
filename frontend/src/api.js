const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Every request gets a long timeout on purpose: Gemma 3 4B on a laptop CPU can
 * take 30-90s to produce a structured answer. Aborting early would replace a
 * slow-but-correct answer with a fake error.
 */
const TIMEOUT_MS = 600000;

/** Backend `detail` strings are already written for humans, so prefer them. */
function messageFor(error) {
  if (error.response) {
    const data = error.response.data;

    if (typeof data === "string" && data) return data;

    if (data && typeof data.detail === "string" && data.detail) return data.detail;
  }

  if (error.code === "ECONNABORTED") {
    return "PrepMate stopped waiting for the local model. It may still be generating — try again in a moment.";
  }

  if (!error.response) {
    return "PrepMate cannot reach the backend at " + API + ". Make sure it is running (uvicorn main:app --port 8000).";
  }

  return error.message || "Something went wrong.";
}

async function request(path, { method = "GET", body, timeout = TIMEOUT_MS } = {}) {
  try {
    const response = await fetch(API + path, {
      method,
      headers: body instanceof FormData ? undefined : { "Content-Type": "application/json" },
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(timeout),
    });

    const text = await response.text();
    let data = {};

    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text };
      }
    }

    if (!response.ok) {
      const error = new Error(messageFor({ response: { data, status: response.status } }));
      error.detail = data && data.detail;
      throw error;
    }

    return data;
  } catch (error) {
    if (error instanceof TypeError || !error.response) {
      if (error.name === "TimeoutError") {
        throw new Error(messageFor({ code: "ECONNABORTED" }));
      }
      throw new Error(messageFor(error));
    }

    throw error;
  }
}

export const api = {
  health: () => request("/api/health", { timeout: 15000 }),
  modes: () => request("/api/modes", { timeout: 15000 }),

  uploadResume(file) {
    // XHR rather than fetch so a slow upload is not silently indistinguishable
    // from a hung backend.
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", API + "/api/resume/upload");
      xhr.timeout = TIMEOUT_MS;

      xhr.onload = () => {
        let data = {};

        try {
          data = JSON.parse(xhr.responseText || "{}");
        } catch {
          data = { detail: xhr.responseText };
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
        } else {
          reject(new Error(messageFor({ response: { data, status: xhr.status } })));
        }
      };

      xhr.onerror = () => reject(new Error(messageFor({})));
      xhr.ontimeout = () => reject(new Error(messageFor({ code: "ECONNABORTED" })));
      xhr.send(form);
    });
  },

  question: (payload) => request("/api/interview/question", { method: "POST", body: payload }),
  evaluate: (payload) => request("/api/interview/evaluate", { method: "POST", body: payload }),

  attackClaims: (payload) => request("/api/attack/claims", { method: "POST", body: payload }),
  attackQuestion: (payload) => request("/api/attack/question", { method: "POST", body: payload }),
  attackEvaluate: (payload) => request("/api/attack/evaluate", { method: "POST", body: payload }),

  report: (payload) => request("/api/interview/report", { method: "POST", body: payload }),
};

export { API };
