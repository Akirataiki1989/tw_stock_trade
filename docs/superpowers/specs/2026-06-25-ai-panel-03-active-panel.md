# AI Panel — 03: `RunAnalysisForm` + `AnalysisDisplay` components

> Part of [AI Panel Overview](2026-06-25-ai-panel-overview.md)

---

## What these units do

Two focused components that together cover the "active" top half of the AI Panel:

- **`RunAnalysisForm`** — symbol input + Analyze button. Drives `useAiSession.start()`.
- **`AnalysisDisplay`** — renders the current session state (idle hint → running spinner → done result → error message). Purely presentational; receives `AiSessionState` as a prop.

Separating them makes `AnalysisDisplay` independently testable without needing to interact with the form.

---

## `RunAnalysisForm`

### Interface

```ts
type RunAnalysisFormProps = {
  initialSymbol?: string;       // pre-fills input (from Holdings tab cross-tab selection)
  isDisabled?: boolean;         // true while session is pending/running/fetching
  onSubmit: (symbol: string) => void;
};
```

### Behavior

- Controlled input. If `initialSymbol` changes (user clicks a holding), update the input value.
- Trims and uppercases the symbol before calling `onSubmit`.
- `isDisabled` greys out and disables both the input and the button.
- Submit on button click or Enter key.
- Empty input: button is disabled (no submit).

---

## `AnalysisDisplay`

### Interface

```ts
type AnalysisDisplayProps = {
  state: AiSessionState;  // imported from use-ai-session
};
```

### Render per state

| State | What renders |
|-------|-------------|
| `idle` | `"Enter a symbol above to run analysis."` (zinc-500, small) |
| `pending` | `"Starting analysis…"` + spinner dot |
| `running` | `"Analyzing {symbol}…"` + spinner dot |
| `fetching` | `"Loading result…"` + spinner dot |
| `done` | Full result block (see below) |
| `error` | Red error message + retry hint |

### Done result block

```
ANALYSIS                                    [model] · [Xms]
────────────────────────────────────────────────────────
{reasoning text — prose, zinc-300, text-sm, whitespace-pre-wrap}

DECISIONS
  2330  BUY   85%  ←  actionBadge + Math.round(confidence*100)%
  2454  HOLD  60%

DEBATE  [expand ▾]
  {agent_reports.debate_history — collapsed by default, Collapsible}
```

- **`reasoning` field (confirmed name)**: display `decisions[symbol].reasoning` as the main analysis text. Fall back to `result.analysis` only if `decisions` is null (e.g. multi-symbol aggregated result). The two values are identical for single-symbol runs — prefer the per-symbol one for accuracy.
- **`confidence`**: `0.0–1.0` float. Display as `Math.round(confidence * 100)%`. Omit if absent.
- **`decisions` JSONB confirmed shape**: `Record<string, { action: "BUY"|"SELL"|"HOLD"; confidence?: number; shares?: number; target_price?: number; stop_loss?: number; reasoning?: string; }>`. Iterate with `Object.entries(result.decisions ?? {})`. If null, skip the DECISIONS section entirely (no crash).
- `debate_history` shown in `<pre>` inside a shadcn `Collapsible`, same pattern as `RecentDecisions`.
- `model_used` + `execution_ms / 1000` shown as a subtle line above the divider.

---

## Files

| File | Action |
|------|--------|
| `components/dashboard/run-analysis-form.tsx` | Create |
| `components/dashboard/run-analysis-form.test.tsx` | Create |
| `components/dashboard/analysis-display.tsx` | Create |
| `components/dashboard/analysis-display.test.tsx` | Create |

---

## TDD Plan

### `RunAnalysisForm`

#### Step 1 — Write failing tests

```tsx
// components/dashboard/run-analysis-form.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RunAnalysisForm } from "./run-analysis-form";

describe("RunAnalysisForm", () => {
  it("renders the symbol input and Analyze button", () => {
    render(<RunAnalysisForm onSubmit={vi.fn()} />);
    expect(screen.getByLabelText("Symbol")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze" })).toBeInTheDocument();
  });

  it("calls onSubmit with uppercased trimmed symbol on button click", async () => {
    const onSubmit = vi.fn();
    render(<RunAnalysisForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Symbol"), " 2330 ");
    await userEvent.click(screen.getByRole("button", { name: "Analyze" }));
    expect(onSubmit).toHaveBeenCalledWith("2330");
  });

  it("calls onSubmit on Enter key", async () => {
    const onSubmit = vi.fn();
    render(<RunAnalysisForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Symbol"), "2454{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("2454");
  });

  it("disables input and button when isDisabled=true", () => {
    render(<RunAnalysisForm onSubmit={vi.fn()} isDisabled />);
    expect(screen.getByLabelText("Symbol")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Analyze" })).toBeDisabled();
  });

  it("pre-fills the input from initialSymbol", () => {
    render(<RunAnalysisForm onSubmit={vi.fn()} initialSymbol="2317" />);
    expect(screen.getByLabelText<HTMLInputElement>("Symbol").value).toBe("2317");
  });

  it("disables the button when input is empty", () => {
    render(<RunAnalysisForm onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Analyze" })).toBeDisabled();
  });
});
```

#### Step 2 — Run to confirm FAIL
```bash
npx vitest run components/dashboard/run-analysis-form.test.tsx
```

#### Step 3 — Implement `run-analysis-form.tsx`

Controlled `<input>` with `aria-label="Symbol"`. `useEffect` syncs `initialSymbol` → local state when it changes.

#### Step 4 — Run to confirm PASS

#### Step 5 — Commit
```bash
git add components/dashboard/run-analysis-form.tsx components/dashboard/run-analysis-form.test.tsx
git commit -m "feat: add RunAnalysisForm component"
```

---

### `AnalysisDisplay`

#### Step 1 — Write failing tests

```tsx
// components/dashboard/analysis-display.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnalysisDisplay } from "./analysis-display";

describe("AnalysisDisplay", () => {
  it("shows idle hint when state is idle", () => {
    render(<AnalysisDisplay state={{ status: "idle" }} />);
    expect(screen.getByText(/enter a symbol/i)).toBeInTheDocument();
  });

  it("shows spinner text when running", () => {
    render(<AnalysisDisplay state={{ status: "running", symbol: "2330" }} />);
    expect(screen.getByText(/analyzing 2330/i)).toBeInTheDocument();
  });

  it("shows error message when error", () => {
    render(<AnalysisDisplay state={{ status: "error", message: "AI timeout" }} />);
    expect(screen.getByText("AI timeout")).toBeInTheDocument();
  });

  it("renders reasoning text and confidence when done", () => {
    render(
      <AnalysisDisplay
        state={{
          status: "done",
          result: {
            id: 1, session_id: "sess-1", analysis: "Buy TSMC now.",
            decisions: { "2330": { action: "BUY", confidence: 0.85, reasoning: "Strong momentum." } },
            market_summary: null, model_used: "gemini-flash", tokens_used: 100,
            execution_ms: 3000, agent_reports: null, created_at: "2026-06-25T10:00:00Z",
          },
        }}
      />
    );
    // prefers decisions[symbol].reasoning over result.analysis
    expect(screen.getByText("Strong momentum.")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("falls back to result.analysis when decisions is null", () => {
    render(
      <AnalysisDisplay
        state={{
          status: "done",
          result: {
            id: 2, session_id: "sess-2", analysis: "Fallback analysis.",
            decisions: null, market_summary: null, model_used: "gemini-flash",
            tokens_used: 50, execution_ms: 1500, agent_reports: null,
            created_at: "2026-06-25T10:00:00Z",
          },
        }}
      />
    );
    expect(screen.getByText("Fallback analysis.")).toBeInTheDocument();
  });
});
```

#### Step 2 — Run to confirm FAIL
#### Step 3 — Implement `analysis-display.tsx`
#### Step 4 — Run to confirm PASS
#### Step 5 — Commit
```bash
git add components/dashboard/analysis-display.tsx components/dashboard/analysis-display.test.tsx
git commit -m "feat: add AnalysisDisplay component"
```
