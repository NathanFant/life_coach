import { SignUpButton, Show } from "@clerk/nextjs";

/**
 * Public landing page.
 *
 * Signed-in users are offered a link to their dashboard.
 * Signed-out users see the value proposition and a sign-up CTA.
 */
export default function LandingPage() {
  return (
    <div className="page-container">
      {/* Hero */}
      <section
        style={{
          textAlign: "center",
          paddingTop: "var(--space-2xl)",
          paddingBottom: "var(--space-2xl)",
        }}
      >
        <p
          className="text-sm text-accent"
          style={{ letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 16 }}
        >
          Your AI-powered life coach
        </p>
        <h1 className="text-2xl" style={{ marginBottom: 24 }}>
          A coach that actually
          <br />
          <span style={{ color: "var(--color-accent)" }}>remembers your life</span>
        </h1>
        <p
          className="text-muted"
          style={{ fontSize: 18, maxWidth: 560, margin: "0 auto 40px" }}
        >
          Unlike a chatbot, AI Life Coach builds a structured model of who you are,
          where you&apos;re going, and what&apos;s in your way — then keeps you moving.
        </p>

        <Show when="signed-out">
          <SignUpButton mode="modal">
            <button className="btn btn-primary" style={{ padding: "12px 32px", fontSize: 16 }}>
              Start your coaching journey
            </button>
          </SignUpButton>
        </Show>
        <Show when="signed-in">
          <a
            href="/dashboard"
            className="btn btn-primary"
            style={{ padding: "12px 32px", fontSize: 16 }}
          >
            Go to your dashboard →
          </a>
        </Show>
      </section>

      {/* Features */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "var(--space-md)",
          marginTop: "var(--space-xl)",
        }}
      >
        {FEATURES.map((f) => (
          <div key={f.title} className="card">
            <div style={{ fontSize: 28, marginBottom: 12 }}>{f.icon}</div>
            <h3 style={{ fontWeight: 600, marginBottom: 8 }}>{f.title}</h3>
            <p className="text-muted text-sm">{f.description}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

const FEATURES = [
  {
    icon: "🧠",
    title: "Persistent memory",
    description:
      "Remembers your goals, projects, relationships, and life stage across every session — no re-explaining yourself.",
  },
  {
    icon: "🎯",
    title: "Goal-oriented coaching",
    description:
      "Every session ends with a concrete next action. Progress on goals and projects is tracked over time.",
  },
  {
    icon: "🛡️",
    title: "Safe boundaries",
    description:
      "Clear coaching focus — not a therapist or advisor. Crisis situations are handled with appropriate care and resources.",
  },
  {
    icon: "🔒",
    title: "You own your data",
    description:
      "Full export and deletion at any time. Your life model is yours to view, edit, and correct.",
  },
];
