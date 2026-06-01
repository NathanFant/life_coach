import { auth } from "@clerk/nextjs/server";

/**
 * Dashboard — life model overview.
 *
 * Shows: life profile summary, active goals, active projects, pending tasks.
 * Data is fetched from the FastAPI backend via @repo/api-client once keys
 * are wired (issue #1, #2). Until then, the skeleton renders with empty states.
 */
export default async function DashboardPage() {
  const { getToken } = await auth();
  // const token = await getToken();
  // TODO: fetch life profile + goals + tasks from the API once keys are set

  return (
    <div className="page-container">
      <h1 className="text-xl" style={{ marginBottom: 8 }}>
        Your Life Dashboard
      </h1>
      <p className="text-muted text-sm" style={{ marginBottom: 32 }}>
        Your goals, projects, and progress — all in one place.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "var(--space-md)",
        }}
      >
        {/* Life Profile Summary */}
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <SectionHeader title="Life Profile" action={{ label: "Edit", href: "/onboarding" }} />
          <EmptyState
            icon="🌱"
            message="Complete your onboarding to see your life profile summary here."
            action={{ label: "Start onboarding →", href: "/onboarding" }}
          />
        </div>

        {/* Active Goals */}
        <div className="card">
          <SectionHeader title="Active Goals" />
          <EmptyState icon="🎯" message="No active goals yet. Your coach will help you set some." />
        </div>

        {/* Active Projects */}
        <div className="card">
          <SectionHeader title="Active Projects" />
          <EmptyState
            icon="🚀"
            message="No active projects yet."
          />
        </div>

        {/* Pending Tasks */}
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <SectionHeader title="Your Next Actions" />
          <EmptyState
            icon="✅"
            message="Tasks assigned by your coach will appear here."
            action={{ label: "Start a coaching session →", href: "/coach" }}
          />
        </div>
      </div>
    </div>
  );
}

function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: { label: string; href: string };
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 16,
      }}
    >
      <h2 style={{ fontSize: 16, fontWeight: 600 }}>{title}</h2>
      {action && (
        <a href={action.href} className="text-accent text-sm">
          {action.label}
        </a>
      )}
    </div>
  );
}

function EmptyState({
  icon,
  message,
  action,
}: {
  icon: string;
  message: string;
  action?: { label: string; href: string };
}) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "var(--space-xl) var(--space-md)",
        color: "var(--color-muted)",
      }}
    >
      <div style={{ fontSize: 32, marginBottom: 12 }}>{icon}</div>
      <p className="text-sm" style={{ marginBottom: action ? 16 : 0 }}>
        {message}
      </p>
      {action && (
        <a href={action.href} className="text-accent text-sm">
          {action.label}
        </a>
      )}
    </div>
  );
}
