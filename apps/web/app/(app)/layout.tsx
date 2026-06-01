import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Protected route group layout.
 *
 * Any route under (app)/ requires authentication.
 * Unauthenticated users are redirected to the Clerk sign-in flow.
 * New users without an onboarding_state of 'complete' are redirected to /onboarding
 * (enforced progressively as API integration is wired in).
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const { userId } = await auth();

  if (!userId) {
    redirect("/");
  }

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <nav className="app-sidebar-nav">
          <a href="/dashboard" className="sidebar-link">
            <span>📊</span> Dashboard
          </a>
          <a href="/coach" className="sidebar-link">
            <span>💬</span> Coach
          </a>
          <a href="/onboarding" className="sidebar-link sidebar-link-secondary">
            <span>📋</span> Profile
          </a>
        </nav>
      </aside>
      <div className="app-content">{children}</div>

      <style>{`
        .app-layout {
          display: grid;
          grid-template-columns: 220px 1fr;
          min-height: calc(100vh - 57px);
        }
        .app-sidebar {
          background: var(--color-surface);
          border-right: 1px solid var(--color-border);
          padding: var(--space-lg) var(--space-md);
        }
        .app-sidebar-nav {
          display: flex;
          flex-direction: column;
          gap: var(--space-xs);
        }
        .sidebar-link {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: 10px var(--space-md);
          border-radius: var(--radius-sm);
          color: var(--color-muted);
          font-size: 14px;
          font-weight: 500;
          transition: background 0.1s, color 0.1s;
          text-decoration: none;
        }
        .sidebar-link:hover {
          background: var(--color-surface-raised);
          color: var(--color-text);
        }
        .sidebar-link-secondary {
          margin-top: auto;
        }
        .app-content {
          overflow: auto;
        }
      `}</style>
    </div>
  );
}
