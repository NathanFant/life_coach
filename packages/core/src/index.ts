/**
 * @repo/core — framework-agnostic client logic shared by web + mobile.
 *
 * Examples (see docs/DESIGN.md §18.1): onboarding state-machine helpers,
 * formatting, client-side validation, derived selectors over the life model.
 *
 * Boundary rule: pure TypeScript. No React, no DOM, no network — those live
 * in @repo/ui and @repo/api-client respectively.
 */

export const APP_NAME = "AI Life Coach";

// TODO: onboarding progress calculators, goal/progress formatters,
//       life-stage label helpers, etc.
export {};
