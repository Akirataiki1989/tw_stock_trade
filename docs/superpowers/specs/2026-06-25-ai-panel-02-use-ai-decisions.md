# AI Panel — 02: `useAiDecisions` hook

> Part of [AI Panel Overview](2026-06-25-ai-panel-overview.md)

---

## What this unit does

Fetches `GET /ai/decisions` to populate the Decision Log. Exposes a `refresh()` function so the orchestrator can trigger a re-fetch after a new analysis completes.

---

## Interface

```ts
function useAiDecisions(
  token: string | null,
  options?: { symbol?: string; limit?: number }
): {
  decisions: AiDecisionRead[];
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}
```

- Default `limit`: 20 (matches backend default).
- `symbol` filter: optional, passed as query param `?symbol=2330`.
- `refresh()` increments an internal counter that triggers a re-fetch via `useEffect` dependency.
- Re-fetches when `token`, `symbol`, or `limit` change.

---

## Files

| File | Action |
|------|--------|
| `lib/use-ai-decisions.ts` | Create |
| `lib/use-ai-decisions.test.ts` | Create |

---

## TDD Plan

### Step 1 — Write failing tests

```ts
// lib/use-ai-decisions.test.ts
import { renderHook, act, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "./api-client";
import { useAiDecisions } from "./use-ai-decisions";

vi.mock("./api-client", () => ({ apiGet: vi.fn() }));

const mockDecision = {
  id: 1, session_id: "sess-1", analysis: "Hold.", decisions: null,
  market_summary: null, model_used: "gemini", tokens_used: 50,
  execution_ms: 2000, agent_reports: null, created_at: "2026-06-25T10:00:00Z",
};

describe("useAiDecisions", () => {
  afterEach(() => vi.mocked(apiGet).mockReset());

  it("returns empty list and not loading when token is null", () => {
    const { result } = renderHook(() => useAiDecisions(null));
    expect(result.current.decisions).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it("fetches decisions on mount with default limit=20", async () => {
    vi.mocked(apiGet).mockResolvedValue([mockDecision]);

    const { result } = renderHook(() => useAiDecisions("token"));

    await waitFor(() => expect(result.current.decisions).toHaveLength(1));
    expect(apiGet).toHaveBeenCalledWith("/ai/decisions?limit=20", "token");
    expect(result.current.isLoading).toBe(false);
  });

  it("appends symbol filter when provided", async () => {
    vi.mocked(apiGet).mockResolvedValue([]);

    const { result } = renderHook(() => useAiDecisions("token", { symbol: "2330" }));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(apiGet).toHaveBeenCalledWith("/ai/decisions?limit=20&symbol=2330", "token");
  });

  it("re-fetches when refresh() is called", async () => {
    vi.mocked(apiGet).mockResolvedValue([mockDecision]);

    const { result } = renderHook(() => useAiDecisions("token"));
    await waitFor(() => expect(result.current.decisions).toHaveLength(1));

    vi.mocked(apiGet).mockResolvedValue([mockDecision, { ...mockDecision, id: 2 }]);

    act(() => { result.current.refresh(); });
    await waitFor(() => expect(result.current.decisions).toHaveLength(2));
    expect(vi.mocked(apiGet)).toHaveBeenCalledTimes(2);
  });

  it("sets error on fetch failure", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("server error"));

    const { result } = renderHook(() => useAiDecisions("token"));
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.decisions).toEqual([]);
  });
});
```

### Step 2 — Run to confirm FAIL
```bash
npx vitest run lib/use-ai-decisions.test.ts
```

### Step 3 — Implement `lib/use-ai-decisions.ts`

Standard `useEffect` + `useState` pattern (same shape as `useHoldings`). Internal `refreshCounter` state drives re-fetch.

### Step 4 — Run to confirm PASS
```bash
npx vitest run lib/use-ai-decisions.test.ts
```
Expected: 5 tests pass

### Step 5 — Commit
```bash
git add lib/use-ai-decisions.ts lib/use-ai-decisions.test.ts
git commit -m "feat: add useAiDecisions hook"
```
