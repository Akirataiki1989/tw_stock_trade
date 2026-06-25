# AI Panel — 01: `useAiSession` hook

> Part of [AI Panel Overview](2026-06-25-ai-panel-overview.md)

---

## What this unit does

Encapsulates the full lifecycle of one AI analysis run:
1. POST `/ai/analyze` → receives `session_id`
2. Opens `WS /ws/ai-stream?session_id=...&token=...`
3. Listens for `started` / `completed` / `failed` events
4. On `completed`: fetches `GET /ai/decisions/{session_id}` for the full result
5. Exposes a unified state machine to the UI

Nothing else in the panel touches the WebSocket directly.

---

## State machine

```
idle
  ↓ start(symbol)
pending          ← POST in flight
  ↓ session_id received, WS opens
running          ← waiting for WS completed/failed event
  ↓ "completed" event
fetching         ← GET /ai/decisions/{session_id} in flight
  ↓ result received
done             ← AiDecisionRead available
  ↓ reset() or start() again
idle

  ↓ any error at any stage
error            ← error message available
  ↓ reset() or start() again
idle
```

---

## Interface

```ts
type AiSessionState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "running"; symbol: string }
  | { status: "fetching" }
  | { status: "done"; result: AiDecisionRead }
  | { status: "error"; message: string };

type AiDecisionRead = {
  id: number;
  session_id: string;
  analysis: string | null;
  decisions: Record<string, unknown> | null;
  market_summary: string | null;
  model_used: string | null;
  tokens_used: number;
  execution_ms: number;
  agent_reports: { debate_history?: string; [key: string]: unknown } | null;
  created_at: string;
};

function useAiSession(token: string | null): {
  state: AiSessionState;
  start: (symbol: string) => void;
  reset: () => void;
}
```

---

## Behavior details

- `start(symbol)` is a no-op if `state.status` is not `"idle"` or `"error"` (prevents double-submit).
- POSTs `{ symbols: [symbol], mode: "full" }`. Takes the first item from the response array.
- WS URL: `wss://api.guieunuch.cc/ws/ai-stream?session_id={id}&token={jwt}`
- WS auth: JWT passed as query param (same pattern as `/ws/quotes`).
- On WS `"failed"` event: transitions to `error` with the event's `error` field.
- On WS disconnect before `"completed"`: transitions to `error` with "Connection lost".
- No automatic reconnect — user re-submits.
- `reset()` closes any open WS connection and returns to `idle`.
- Cleanup on unmount: close WS, cancel any in-flight fetch.

---

## Files

| File | Action |
|------|--------|
| `lib/use-ai-session.ts` | Create |
| `lib/use-ai-session.test.ts` | Create |

---

## TDD Plan

### Step 1 — Write failing tests

```ts
// lib/use-ai-session.test.ts
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { apiGet, apiPost } from "./api-client";
import { useAiSession } from "./use-ai-session";

vi.mock("./api-client", () => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(),
}));

// Mock WebSocket
const mockWsInstance = {
  close: vi.fn(),
  onopen: null as (() => void) | null,
  onmessage: null as ((e: MessageEvent) => void) | null,
  onclose: null as (() => void) | null,
  onerror: null as ((e: Event) => void) | null,
};
const MockWebSocket = vi.fn(() => mockWsInstance);
vi.stubGlobal("WebSocket", MockWebSocket);

describe("useAiSession", () => {
  afterEach(() => {
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiGet).mockReset();
    mockWsInstance.close.mockReset();
    MockWebSocket.mockClear();
  });

  it("starts in idle state", () => {
    const { result } = renderHook(() => useAiSession("token"));
    expect(result.current.state.status).toBe("idle");
  });

  it("transitions through pending → running → fetching → done on success", async () => {
    vi.mocked(apiPost).mockResolvedValue([{ session_id: "sess-123", status: "running" }]);
    vi.mocked(apiGet).mockResolvedValue({
      id: 1, session_id: "sess-123", analysis: "Buy TSMC.", decisions: null,
      market_summary: null, model_used: "gemini", tokens_used: 100,
      execution_ms: 3000, agent_reports: null, created_at: "2026-06-25T10:00:00Z",
    });

    const { result } = renderHook(() => useAiSession("token"));

    act(() => { result.current.start("2330"); });
    expect(result.current.state.status).toBe("pending");

    await waitFor(() => expect(result.current.state.status).toBe("running"));
    expect(MockWebSocket).toHaveBeenCalledWith(expect.stringContaining("sess-123"));

    // Simulate WS completed event
    act(() => {
      mockWsInstance.onmessage?.({
        data: JSON.stringify({ type: "ai_event", event: "completed", symbol: "2330" }),
      } as MessageEvent);
    });

    await waitFor(() => expect(result.current.state.status).toBe("done"));
    expect(result.current.state).toMatchObject({ status: "done", result: { analysis: "Buy TSMC." } });
  });

  it("transitions to error on WS failed event", async () => {
    vi.mocked(apiPost).mockResolvedValue([{ session_id: "sess-456", status: "running" }]);

    const { result } = renderHook(() => useAiSession("token"));
    act(() => { result.current.start("2330"); });

    await waitFor(() => expect(result.current.state.status).toBe("running"));

    act(() => {
      mockWsInstance.onmessage?.({
        data: JSON.stringify({ type: "ai_event", event: "failed", error: "AI timeout" }),
      } as MessageEvent);
    });

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    expect((result.current.state as { status: "error"; message: string }).message).toBe("AI timeout");
  });

  it("transitions to error on WS disconnect mid-run", async () => {
    vi.mocked(apiPost).mockResolvedValue([{ session_id: "sess-789", status: "running" }]);

    const { result } = renderHook(() => useAiSession("token"));
    act(() => { result.current.start("2330"); });

    await waitFor(() => expect(result.current.state.status).toBe("running"));

    act(() => { mockWsInstance.onclose?.(); });

    await waitFor(() => expect(result.current.state.status).toBe("error"));
  });

  it("reset() returns to idle from error", async () => {
    vi.mocked(apiPost).mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useAiSession("token"));
    act(() => { result.current.start("2330"); });

    await waitFor(() => expect(result.current.state.status).toBe("error"));

    act(() => { result.current.reset(); });
    expect(result.current.state.status).toBe("idle");
  });

  it("start() is a no-op when already running", async () => {
    vi.mocked(apiPost).mockResolvedValue([{ session_id: "sess-abc", status: "running" }]);

    const { result } = renderHook(() => useAiSession("token"));
    act(() => { result.current.start("2330"); });

    await waitFor(() => expect(result.current.state.status).toBe("running"));

    act(() => { result.current.start("2454"); });
    expect(vi.mocked(apiPost)).toHaveBeenCalledTimes(1);
  });
});
```

### Step 2 — Run to confirm FAIL
```bash
npx vitest run lib/use-ai-session.test.ts
```
Expected: `Cannot find module './use-ai-session'`

### Step 3 — Implement `lib/use-ai-session.ts`

State machine using `useReducer`. Key points:
- `start()` calls `apiPost("/ai/analyze", { symbols: [symbol], mode: "full" }, token)`, takes `[0].session_id`
- Opens `new WebSocket(\`wss://api.guieunuch.cc/ws/ai-stream?session_id=${id}&token=${token}\`)`
- `onmessage`: parse JSON, handle `event === "completed"` → call `apiGet("/ai/decisions/${session_id}", token)` → dispatch done
- `onclose` while in `running`: dispatch error "Connection lost"
- Store WS ref in `useRef` for cleanup

### Step 4 — Run to confirm PASS
```bash
npx vitest run lib/use-ai-session.test.ts
```
Expected: 6 tests pass

### Step 5 — Commit
```bash
git add lib/use-ai-session.ts lib/use-ai-session.test.ts
git commit -m "feat: add useAiSession hook"
```

---

## Error handling

| Scenario | Behavior |
|----------|---------|
| POST fails (network/4xx/5xx) | → `error` state with "Failed to start analysis" |
| WS fails to open | → `error` state with "Connection failed" |
| WS `failed` event | → `error` state with event's `error` field |
| WS disconnect before `completed` | → `error` state with "Connection lost" |
| GET /ai/decisions fails after completed | → `error` state with "Failed to load result" |
