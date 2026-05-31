import { APP_NAME } from "@repo/core";

/**
 * Placeholder landing route. Real routes (see docs/DESIGN.md §18.1):
 *   (auth)/      → sign-in / sign-up (Clerk)
 *   onboarding/  → adaptive interview → Life Profile
 *   coach/       → streamed coaching sessions
 *   dashboard/   → life-model: profile, goals, projects
 */
export default function HomePage() {
  return (
    <main style={{ padding: 40, fontFamily: "system-ui" }}>
      <h1>{APP_NAME}</h1>
      <p>Scaffolded. Coaching UI lands in Phase 1 (see docs/DESIGN.md).</p>
    </main>
  );
}
