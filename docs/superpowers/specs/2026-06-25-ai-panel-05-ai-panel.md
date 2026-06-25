# AI Panel — 05: `AiPanel` orchestrator + `app/page.tsx` wiring

> Part of [AI Panel Overview](2026-06-25-ai-panel-overview.md)

---

## What this unit does

`AiPanel` is the top-level component that:
1. Holds `useAiSession` and `useAiDecisions`
2. On session `done`: calls `decisions.refresh()` to update the log
3. Passes `selectedSymbol` down to `RunAnalysisForm` as `initialSymbol`
4. Composes `RunAnalysisForm` + `AnalysisDisplay` + `DecisionLog`

`app/page.tsx` wires:
- `selectedSymbol` state (lifted up from Holdings tab's `onSelectSymbol`)
- Passes `token` to `AiPanel`
- Passes `onSelectSymbol` to `HoldingsTable`

---

## Interface

```ts
type AiPanelProps = {
  token: string;
  selectedSymbol?: string;  // from Holdings tab click
};
```

---

## State coordination

```
app/page.tsx
  selectedSymbol (useState)
  │
  ├─ HoldingsTable  onSelectSymbol={setSelectedSymbol}
  │
  └─ AiPanel  token={token}  selectedSymbol={selectedSymbol}
        │
        ├─ useAiSession(token)
        ├─ useAiDecisions(token)
        │
        ├─ RunAnalysisForm
        │     initialSymbol={selectedSymbol}
        │     isDisabled={session is not idle/error}
        │     onSubmit={session.start}
        │
        ├─ AnalysisDisplay  state={session.state}
        │
        └─ DecisionLog  decisions={...}  isLoading={...}  error={...}
```

On `session.state.status === "done"`: call `decisions.refresh()` inside a `useEffect` keyed on the session result's `session_id` (avoids double-refresh on re-render).

---

## Files

| File | Action |
|------|--------|
| `components/dashboard/ai-panel.tsx` | Create |
| `components/dashboard/ai-panel.test.tsx` | Create |
| `app/page.tsx` | Modify |

---

## TDD Plan

### Step 1 — Write failing tests for `AiPanel`

```tsx
// components/dashboard/ai-panel.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AiPanel } from "./ai-panel";
import * as useAiSessionModule from "@/lib/use-ai-session";
import * as useAiDecisionsModule from "@/lib/use-ai-decisions";

vi.mock("@/lib/use-ai-session");
vi.mock("@/lib/use-ai-decisions");

const mockRefresh = vi.fn();

describe("AiPanel", () => {
  beforeEach(() => {
    vi.mocked(useAiDecisionsModule.useAiDecisions).mockReturnValue({
      decisions: [], isLoading: false, error: null, refresh: mockRefresh,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the form, display, and log", () => {
    vi.mocked(useAiSessionModule.useAiSession).mockReturnValue({
      state: { status: "idle" },
      start: vi.fn(),
      reset: vi.fn(),
    });

    render(<AiPanel token="tok" />);
    expect(screen.getByLabelText("Symbol")).toBeInTheDocument();
    expect(screen.getByText(/enter a symbol/i)).toBeInTheDocument();
    expect(screen.getByText(/no previous analyses/i)).toBeInTheDocument();
  });

  it("pre-fills symbol from selectedSymbol prop", () => {
    vi.mocked(useAiSessionModule.useAiSession).mockReturnValue({
      state: { status: "idle" },
      start: vi.fn(),
      reset: vi.fn(),
    });

    render(<AiPanel token="tok" selectedSymbol="2330" />);
    expect(screen.getByLabelText<HTMLInputElement>("Symbol").value).toBe("2330");
  });

  it("calls decisions.refresh() after session completes", async () => {
    const mockStart = vi.fn();
    vi.mocked(useAiSessionModule.useAiSession).mockReturnValue({
      state: {
        status: "done",
        result: {
          id: 1, session_id: "sess-done", analysis: "Done.", decisions: null,
          market_summary: null, model_used: "gemini", tokens_used: 10,
          execution_ms: 1000, agent_reports: null, created_at: "2026-06-25T10:00:00Z",
        },
      },
      start: mockStart,
      reset: vi.fn(),
    });

    render(<AiPanel token="tok" />);
    await waitFor(() => expect(mockRefresh).toHaveBeenCalledTimes(1));
  });
});
```

### Step 2 — Run to confirm FAIL
```bash
npx vitest run components/dashboard/ai-panel.test.tsx
```

### Step 3 — Implement `ai-panel.tsx`

```tsx
"use client";

import { useEffect, useRef } from "react";
import { useAiSession } from "@/lib/use-ai-session";
import { useAiDecisions } from "@/lib/use-ai-decisions";
import { RunAnalysisForm } from "./run-analysis-form";
import { AnalysisDisplay } from "./analysis-display";
import { DecisionLog } from "./decision-log";

export function AiPanel({ token, selectedSymbol }: { token: string; selectedSymbol?: string }) {
  const session = useAiSession(token);
  const decisions = useAiDecisions(token);

  const refreshedFor = useRef<string | null>(null);
  useEffect(() => {
    if (
      session.state.status === "done" &&
      session.state.result.session_id !== refreshedFor.current
    ) {
      refreshedFor.current = session.state.result.session_id;
      decisions.refresh();
    }
  }, [session.state, decisions]);

  const isRunning = !["idle", "error"].includes(session.state.status);

  return (
    <div className="flex flex-col divide-y divide-zinc-800">
      <div className="p-6">
        <RunAnalysisForm
          initialSymbol={selectedSymbol}
          isDisabled={isRunning}
          onSubmit={session.start}
        />
      </div>
      <div className="p-6">
        <AnalysisDisplay state={session.state} />
      </div>
      <div className="flex-1 overflow-y-auto">
        <DecisionLog
          decisions={decisions.decisions}
          isLoading={decisions.isLoading}
          error={decisions.error}
        />
      </div>
    </div>
  );
}
```

### Step 4 — Run to confirm PASS
```bash
npx vitest run components/dashboard/ai-panel.test.tsx
```
Expected: 3 tests pass

### Step 5 — Modify `app/page.tsx`

Add `selectedSymbol` state and wire `onSelectSymbol` → `HoldingsTable`, `selectedSymbol` → `AiPanel`:

```tsx
// additions to app/page.tsx
const [selectedSymbol, setSelectedSymbol] = useState<string | undefined>();

// In the JSX:
<HoldingsTable holdings={holdings} onSelectSymbol={setSelectedSymbol} />
// ...
<AiPanel token={token} selectedSymbol={selectedSymbol} />
```

Remove the `<p>AI Panel coming soon.</p>` placeholder.

### Step 6 — Full test suite + build
```bash
npx vitest run
npm run lint
npm run build
```

### Step 7 — Playwright verification

Log in, verify:
- AI Panel column is visible (no "coming soon" text)
- Click a holding → AI Panel symbol input pre-fills
- Click "Analyze" → form disables, spinner appears
- On completion → analysis text renders, Decision Log updates
- No console errors

### Step 8 — Commit
```bash
git add components/dashboard/ai-panel.tsx components/dashboard/ai-panel.test.tsx app/page.tsx
git commit -m "feat: add AiPanel orchestrator and wire into dashboard"
```
