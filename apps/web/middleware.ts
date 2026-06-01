import { clerkMiddleware } from "@clerk/nextjs/server";

/**
 * Clerk middleware — runs on every matched request before the page renders.
 *
 * Public routes (no auth required): landing page only.
 * Everything else (/onboarding, /dashboard, /coach, /api/*) requires sign-in.
 * Clerk's own proxy path (/__clerk/) must always be routed through.
 */
export default clerkMiddleware();

export const config = {
  matcher: [
    // Skip Next.js internals and static files
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for Clerk's auto-proxy path
    "/__clerk/(.*)",
    // Always run for API and tRPC routes
    "/(api|trpc)(.*)",
  ],
};
