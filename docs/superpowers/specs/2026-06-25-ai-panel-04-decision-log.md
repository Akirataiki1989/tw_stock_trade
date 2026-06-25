# AI Panel — 04: `DecisionLog` component

> Part of [AI Panel Overview](2026-06-25-ai-panel-overview.md)

---

## What this unit does

Renders the list of past AI decisions fetched by `useAiDecisions`. Each row shows the timestamp, model, and per-symbol action badges. Rows are expandable (shadcn `Collapsible`) to show the full `analysis` text and `agent_reports.debate_history`.

---

## Interface

```ts
type DecisionLogProps = {
  decisions: AiDecisionRead[];
  isLoading: boolean;
  error: string | null;
};
```

No callbacks — the log is read-only.

---

## Render

### Loading state
Subtle `"Loading history…"` text (zinc-500).

### Error state
`"Failed to load history."` (zinc-500, no red — non-critical).

### Empty state
`"No previous analyses."` (zinc-500).

### Row (collapsed)

```
[2026-06-25 10:00]  gemini-flash · 3.0s     2330 BUY   2454 HOLD   [▾]
```

- Timestamp: `created_at` formatted as `"MMM D, HH:mm"` (e.g. `"Jun 25, 10:00"`)
- Model: `model_used` (zinc-500, small)
- Execution time: `execution_ms / 1000` formatted as `"X.Xs"` (zinc-500)
- Per-symbol action badges: iterate `decisions` JSONB keys → render each `{symbol} {action}` as a badge (reuse `actionBadgeClass`)
- Expand toggle `[▾]` / `[▴]` at the right

### Row (expanded)

```
[2026-06-25 10:00]  gemini-flash · 3.0s     2330 BUY   2454 HOLD   [▴]
────────────────────────────────────────────────────────────────────────
ANALYSIS
  {analysis text — whitespace-pre-wrap, zinc-300, text-xs}

DEBATE
  {agent_reports.debate_history — whitespace-pre-wrap, zinc-500, text-xs}
```

- If `analysis` is null: omit the ANALYSIS section.
- If `agent_reports?.debate_history` is null/absent: omit the DEBATE section.
- If `decisions` JSONB shape is unexpected: skip the badge row gracefully (no crash).

### Dividers
`divide-y divide-zinc-800` between rows.

---

## Files

| File | Action |
|------|--------|
| `components/dashboard/decision-log.tsx` | Create |
| `components/dashboard/decision-log.test.tsx` | Create |

---

## TDD Plan

### Step 1 — Write failing tests

```tsx
// components/dashboard/decision-log.test.tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DecisionLog } from "./decision-log";
import type { AiDecisionRead } from "@/lib/use-ai-session";

const decision: AiDecisionRead = {
  id: 1, session_id: "sess-1",
  analysis: "TSMC shows bullish momentum.",
  decisions: { "2330": { action: "BUY", confidence: 0.85 } },
  market_summary: null, model_used: "gemini-flash",
  tokens_used: 100, execution_ms: 3200,
  agent_reports: { debate_history: "Bull: strong. Bear: risky." },
  created_at: "2026-06-25T10:00:00Z",
};

describe("DecisionLog", () => {
  it("shows loading text when isLoading", () => {
    render(<DecisionLog decisions={[]} isLoading error={null} />);
    expect(screen.getByText(/loading history/i)).toBeInTheDocument();
  });

  it("shows empty state when no decisions", () => {
    render(<DecisionLog decisions={[]} isLoading={false} error={null} />);
    expect(screen.getByText(/no previous analyses/i)).toBeInTheDocument();
  });

  it("renders symbol badge and model for each decision", () => {
    render(<DecisionLog decisions={[decision]} isLoading={false} error={null} />);
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("2330")).toBeInTheDocument();
    expect(screen.getByText(/gemini-flash/)).toBeInTheDocument();
  });

  it("expands to show analysis text on click", async () => {
    render(<DecisionLog decisions={[decision]} isLoading={false} error={null} />);
    expect(screen.queryByText("TSMC shows bullish momentum.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /expand/i }));
    expect(screen.getByText("TSMC shows bullish momentum.")).toBeInTheDocument();
  });

  it("shows debate history when expanded", async () => {
    render(<DecisionLog decisions={[decision]} isLoading={false} error={null} />);
    await userEvent.click(screen.getByRole("button", { name: /expand/i }));
    expect(screen.getByText("Bull: strong. Bear: risky.")).toBeInTheDocument();
  });

  it("renders without crashing when decisions JSONB is null", () => {
    const noDecisions = { ...decision, decisions: null };
    render(<DecisionLog decisions={[noDecisions]} isLoading={false} error={null} />);
    // Should render row without badges, no crash
    expect(screen.getByText(/gemini-flash/)).toBeInTheDocument();
  });
});
```

### Step 2 — Run to confirm FAIL
```bash
npx vitest run components/dashboard/decision-log.test.tsx
```

### Step 3 — Implement `decision-log.tsx`

- Map over `decisions` array, one `Collapsible` per row (shadcn pattern — same import as `RecentDecisions`).
- `formatDateTime`: `new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })`
- Expand toggle button: `aria-label="expand"` / `aria-label="collapse"` for test selectors.
- Guard `decisions` JSONB: `Object.entries(result.decisions ?? {})`.

### Step 4 — Run to confirm PASS
```bash
npx vitest run components/dashboard/decision-log.test.tsx
```
Expected: 6 tests pass

### Step 5 — Commit
```bash
git add components/dashboard/decision-log.tsx components/dashboard/decision-log.test.tsx
git commit -m "feat: add DecisionLog component"
```
