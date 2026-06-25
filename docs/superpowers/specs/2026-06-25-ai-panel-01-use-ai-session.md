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

type AiDecisionSymbol = {
  action: "BUY" | "SELL" | "HOLD";
  confidence?: number;    // 0.0–1.0; display as Math.round(x * 100)%
  shares?: number;
  target_price?: number;
  stop_loss?: number;
  reasoning?: string;     // confirmed field name (not "reason")
};

type AiDecisionRead = {
  id: number;
  session_id: string;
  analysis: string | null;        // equals decisions[symbol].reasoning for single-symbol runs
  decisions: Record<string, AiDecisionSymbol> | null;
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
  completedSessionId: string | null;  // set when status reaches "done"; null otherwise
}
```

---

## Behavior details

- `start(symbol)` is a no-op if `state.status` is not `"idle"` or `"error"` (prevents double-submit).
- POSTs `{ symbols: [symbol], mode: "full" }`. Takes the first item from the response array.
- WS URL: `wss://api.guieunuch.cc/ws/ai-stream?session_id={id}&token={jwt}`
- WS auth: JWT passed as query param (same pattern as `/ws/quotes`).
- On WS `"failed"` event: transitions to `error` with the event's `error` field.
- **`terminalReceivedRef`**: set to `true` when `completed` or `failed` event is received. `onclose` only transitions to `error` ("Connection lost") if `!terminalReceivedRef.current` — prevents the backend's normal post-completed WS close from overwriting `fetching`/`done`.
- **Race condition fix (worker finishes before WS subscribes)**: on `onopen`, immediately poll `GET /ai/decisions/{session_id}` once. If a result already exists in the DB, close the WS and go straight to `done` without waiting for the WS event.
- No automatic reconnect — user re-submits.
- `completedSessionId`: set to the session's `session_id` when state reaches `done`, `null` otherwise. Resets to `null` on `reset()` or `start()`.
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
    expect(result.current.completedSessionId).toBe("sess-123");
  });

  it("backend closing WS after completed does NOT transition to error", async () => {
    vi.mocked(apiPost).mockResolvedValue([{ session_id: "sess-close", status: "running" }]);
    vi.mocked(apiGet).mockResolvedValue({
      id: 2, session_id: "sess-close", analysis: "Hold.", decisions: null,
      market_summary: null, model_used: "gemini", tokens_used: 50,
      execution_ms: 2000, agent_reports: null, created_at: "2026-06-25T10:00:00Z",
    });

    const { result } = renderHook(() => useAiSession("token"));
    act(() => { result.current.start("2330"); });
    await waitFor(() => expect(result.current.state.status).toBe("running"));

    // completed event arrives, then backend closes WS
    act(() => {
      mockWsInstance.onmessage?.({
        data: JSON.stringify({ type: "ai_event", event: "completed", symbol: "2330" }),
      } as MessageEvent);
    });
    act(() => { mockWsInstance.onclose?.(); });  // should be ignored

    await waitFor(() => expect(result.current.state.status).toBe("done"));
    // must NOT have transitioned through error
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

  it("transitions to error on WS disconnect without prior terminal event", async () => {
    vi.mocked(apiPost).mockResolvedValue([{ session_id: "sess-789", status: "running" }]);
    // onopen poll returns nothing yet (not finished)
    vi.mocked(apiGet).mockResolvedValue(null);

    const { result } = renderHook(() => useAiSession("token"));
    act(() => { result.current.start("2330"); });

    await waitFor(() => expect(result.current.state.status).toBe("running"));

    act(() => { mockWsInstance.onclose?.(); });  // no terminal event before this

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
- `onopen`: immediately poll `apiGet("/ai/decisions/${session_id}", token)` once — if result exists (race: worker already done), close WS and dispatch done directly
- `onmessage`: parse JSON; on `completed`/`failed`, set `terminalReceivedRef.current = true` first, then handle transition
- `onmessage` `"completed"`: call `apiGet("/ai/decisions/${session_id}", token)` → dispatch done + set `completedSessionId`
- `onclose`: only dispatch error "Connection lost" if `!terminalReceivedRef.current`
- `terminalReceivedRef = useRef(false)`, reset on each new `start()` call
- Store WS ref in `useRef` for cleanup
- `completedSessionId` tracked in separate `useState<string | null>(null)`, reset on `reset()`/`start()`

### Step 4 — Run to confirm PASS
```bash
npx vitest run lib/use-ai-session.test.ts
```
Expected: 7 tests pass

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
| WS disconnect without prior terminal event | → `error` state with "Connection lost" |
| WS closes after `completed` (normal backend behaviour) | ignored — `terminalReceivedRef` prevents false error |
| GET /ai/decisions fails after completed | → `error` state with "Failed to load result" |
