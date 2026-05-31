/**
 * @repo/api-client — the ONLY way clients (web + mobile) talk to the backend.
 *
 * Responsibilities (see docs/DESIGN.md §9, §18.2):
 *  - typed REST calls (generated from the FastAPI OpenAPI doc)
 *  - auth header injection (Clerk JWT)
 *  - SSE / streaming abstraction (works in both Next.js and Expo)
 *
 * Boundary rule: NO UI, NO direct DB/LLM access. IDs in, typed data out.
 */

export interface ApiClientConfig {
  baseUrl: string;
  /** Returns a fresh Clerk JWT for the Authorization header. */
  getToken: () => Promise<string | null>;
}

export interface StreamHandlers {
  onToken?: (text: string) => void;
  onToolCall?: (payload: unknown) => void;
  onFollowups?: (questions: string[]) => void;
  onChangeDetected?: (payload: unknown) => void;
  onSafety?: (payload: unknown) => void;
  onDone?: (payload: unknown) => void;
}

export function createApiClient(config: ApiClientConfig) {
  // TODO: implement typed fetch wrapper + SSE handling.
  return {
    config,
    // sessions.sendMessage(sessionId, content, handlers) → SSE stream
    // profile.get() / profile.patch()
    // goals.list() / goals.create() / ...
    // onboarding.next() / onboarding.answer() / ...
    // account.export() / account.delete()
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
