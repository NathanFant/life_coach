/**
 * @repo/types — single source of truth for client-side domain types.
 *
 * These zod schemas mirror the backend Pydantic schemas (services/api/app/schemas).
 * Generation from the FastAPI OpenAPI document is planned (see docs/DESIGN.md §9.1);
 * until then, keep these in sync manually.
 *
 * NO business logic here — types and schemas only.
 */
import { z } from "zod";

// ─── Enums (mirror backend) ────────────────────────────────────────────────
export const DomainKind = z.enum([
  "career",
  "business",
  "education",
  "family",
  "marriage",
  "parenting",
  "finances",
  "health",
  "personal_growth",
  "habits",
  "productivity",
  "side_project",
]);
export type DomainKind = z.infer<typeof DomainKind>;

export const GoalHorizon = z.enum(["short", "long"]);
export type GoalHorizon = z.infer<typeof GoalHorizon>;

// ─── Core entities (placeholders — expand alongside the API schemas) ────────
export const LifeProfile = z.object({
  id: z.string().uuid(),
  lifeStage: z.string().nullable(),
  summary: z.string().nullable(),
  completeness: z.number().min(0).max(1),
});
export type LifeProfile = z.infer<typeof LifeProfile>;

export const Goal = z.object({
  id: z.string().uuid(),
  title: z.string(),
  horizon: GoalHorizon,
  status: z.enum(["active", "achieved", "paused", "dropped"]),
  progress: z.number().min(0).max(1),
});
export type Goal = z.infer<typeof Goal>;

// TODO: Project, Milestone, Task, Relationship, TimelineEvent, Insight,
//       SemanticFact, Conversation, Message, CoachingSession — see docs/DESIGN.md §4.
