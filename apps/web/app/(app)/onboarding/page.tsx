"use client";

import { useEffect, useState } from "react";

/**
 * Onboarding page — adaptive question-by-question interview.
 *
 * Calls GET /v1/onboarding to get the current state + next question,
 * then POST /v1/onboarding/answer as the user responds.
 *
 * API integration is wired once NEXT_PUBLIC_API_BASE_URL and Clerk keys
 * are configured (issue #1, #2). Until then, the UI renders with mock state.
 */

type OnboardingState = {
  is_complete: boolean;
  completeness: number;
  next_question: {
    slot: string;
    text: string;
    hint: string;
  } | null;
  filled_slots: Record<string, unknown>;
};

export default function OnboardingPage() {
  const [state, setState] = useState<OnboardingState>({
    is_complete: false,
    completeness: 0,
    next_question: {
      slot: "employment_status",
      text: "Are you currently employed, self-employed, building a business, or something else?",
      hint: "e.g. employed full-time, freelancer, founder, student, between jobs",
    },
    filled_slots: {},
  });
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completionPct = Math.round(state.completeness * 100);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!answer.trim() || !state.next_question) return;

    setSubmitting(true);
    setError(null);

    // TODO: replace with real API call via @repo/api-client
    // const client = createApiClient({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL!, getToken });
    // const next = await client.onboarding.answer({ slot: state.next_question.slot, raw_answer: answer });

    // Mock progression for now
    await new Promise((r) => setTimeout(r, 400));
    setState((prev) => ({
      ...prev,
      completeness: Math.min(1, prev.completeness + 1 / 12),
      filled_slots: { ...prev.filled_slots, [state.next_question!.slot]: answer },
      next_question:
        prev.completeness + 1 / 12 >= 0.9
          ? null
          : {
              slot: "next_slot",
              text: "Great — what's your biggest professional goal for the next 12 months?",
              hint: "Be as specific as you can",
            },
    }));
    setAnswer("");
    setSubmitting(false);
  }

  if (state.is_complete || state.completeness >= 0.9) {
    return (
      <div className="page-narrow" style={{ textAlign: "center", paddingTop: 80 }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🎉</div>
        <h1 className="text-xl" style={{ marginBottom: 12 }}>
          Your life profile is set up!
        </h1>
        <p className="text-muted" style={{ marginBottom: 32 }}>
          Your coach now has the context it needs to help you make real progress.
        </p>
        <a href="/coach" className="btn btn-primary" style={{ padding: "12px 32px" }}>
          Start your first coaching session →
        </a>
      </div>
    );
  }

  return (
    <div className="page-narrow">
      {/* Progress */}
      <div style={{ marginBottom: 32 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: 8,
          }}
        >
          <span className="text-sm text-muted">Setting up your life profile</span>
          <span className="text-sm text-accent">{completionPct}% complete</span>
        </div>
        <div className="progress-bar-track">
          <div
            className="progress-bar-fill"
            style={{ width: `${completionPct}%` }}
          />
        </div>
      </div>

      {/* Question card */}
      {state.next_question && (
        <div className="card">
          <p className="text-muted text-sm" style={{ marginBottom: 8 }}>
            Your coach asks:
          </p>
          <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24, lineHeight: 1.4 }}>
            {state.next_question.text}
          </h2>

          {error && (
            <div
              style={{
                color: "var(--color-danger)",
                fontSize: 14,
                marginBottom: 16,
                padding: "8px 12px",
                background: "rgba(220,38,38,0.08)",
                borderRadius: "var(--radius-sm)",
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={state.next_question.hint || "Your answer…"}
              rows={3}
              style={{
                width: "100%",
                background: "var(--color-bg)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--color-text)",
                fontSize: 16,
                padding: "12px 16px",
                resize: "vertical",
                fontFamily: "inherit",
                outline: "none",
                marginBottom: 16,
              }}
              onFocus={(e) => (e.target.style.borderColor = "var(--color-accent)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--color-border)")}
            />
            <button
              type="submit"
              disabled={!answer.trim() || submitting}
              className="btn btn-primary"
              style={{
                width: "100%",
                padding: "12px",
                opacity: !answer.trim() || submitting ? 0.5 : 1,
              }}
            >
              {submitting ? "Saving…" : "Continue →"}
            </button>
          </form>
        </div>
      )}

      {/* Already answered */}
      {Object.keys(state.filled_slots).length > 0 && (
        <div style={{ marginTop: 24 }}>
          <p className="text-sm text-muted" style={{ marginBottom: 8 }}>
            Answered so far
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {Object.entries(state.filled_slots).map(([slot, value]) => (
              <div
                key={slot}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 13,
                  color: "var(--color-muted)",
                }}
              >
                <span>{slot.replace(/_/g, " ")}</span>
                <span style={{ color: "var(--color-text)" }}>{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
