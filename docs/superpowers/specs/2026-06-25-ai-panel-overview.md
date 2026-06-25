# AI Panel — Overview

> Sub-specs linked below. Each file contains full spec + TDD implementation plan.
> Written 2026-06-25. Pending Codex review before execution.

---

## Layout

The AI Panel occupies the fixed right 40% column (always visible, not a tab).

```
┌─────────────────────────────┐
│  Run Analysis               │  ← RunAnalysisForm
│  [symbol input] [Analyze]   │
├─────────────────────────────┤
│  Analysis Result            │  ← AnalysisDisplay
│  (spinner → full text)      │
├─────────────────────────────┤
│  Decision Log               │  ← DecisionLog
│  (past decisions, expand)   │
└─────────────────────────────┘
```

---

## Critical design clarification: WS is event-only, not text-streaming

`WS /ws/ai-stream` sends three event types:
- `{"type": "ai_event", "event": "started", "symbol": "2330", ...}`
- `{"type": "ai_event", "event": "completed", "symbol": "2330", ...}`
- `{"type": "ai_event", "event": "failed", "error": "...", ...}`

It does **not** stream text tokens. The full `analysis` text is only available after `completed` via `GET /ai/decisions/{session_id}`.

**UX implication:** "Live" means a running spinner with status text, not a typewriter effect. On `completed`, fetch the full result and replace the spinner.

---

## Backend API summary

| Endpoint | Method | Key fields |
|----------|--------|-----------|
| `/ai/analyze` | POST | req: `symbols: list[str]`, `mode: str`; res: `[{session_id, status}]` |
| `/ws/ai-stream` | WS | query: `session_id`, `token`; pushes: `started`/`completed`/`failed` events |
| `/ai/decisions` | GET | query: `limit`, `symbol`; res: `AiDecisionRead[]` |
| `/ai/decisions/{session_id}` | GET | res: single `AiDecisionRead` |

`AiDecisionRead` key fields: `session_id`, `analysis` (text), `decisions` (JSONB by symbol), `agent_reports` (JSONB with `debate_history`), `created_at`.

---

## Decomposition

| # | File | What it covers |
|---|------|----------------|
| 01 | [use-ai-session](2026-06-25-ai-panel-01-use-ai-session.md) | Hook: POST /ai/analyze + WS lifecycle → unified state machine |
| 02 | [use-ai-decisions](2026-06-25-ai-panel-02-use-ai-decisions.md) | Hook: GET /ai/decisions with refresh trigger |
| 03 | [run-analysis-form + analysis-display](2026-06-25-ai-panel-03-active-panel.md) | Components: symbol input form + result display |
| 04 | [decision-log](2026-06-25-ai-panel-04-decision-log.md) | Component: history list with expandable detail |
| 05 | [ai-panel](2026-06-25-ai-panel-05-ai-panel.md) | Orchestrator: wires all above + page.tsx integration |

---

## Cross-tab coordination

`HoldingsTable` already has `onSelectSymbol` callback wired in the component (from the Holdings tab implementation). `app/page.tsx` does not yet pass it in. `AiPanel` will receive `selectedSymbol?: string` prop; when set, the symbol input is pre-filled (but not auto-submitted — user still clicks Analyze).

---

## Design tokens (same as rest of dashboard)

- Surface: `zinc-900`, border: `border-zinc-800`, dividers: `divide-zinc-800`
- Accent: `blue-500` for the Analyze button
- Running state: `zinc-500` spinner text
- Analysis text: `zinc-300`, monospace for numbers
- BUY badge: reuse `actionBadgeClass` from `lib/action-badge.ts`

---

## Open questions for Codex review

1. `decisions` JSONB schema per symbol — exact shape unknown. Spec assumes `{action, confidence?, reason?}` keyed by symbol. Codex should verify against actual agent output or flag if shape differs.
2. Multi-symbol analyze: the form supports one symbol at a time (simpler UX). Is there a case for multi-symbol? Currently out of scope.
3. WS reconnect on disconnect mid-run — should we retry? Spec says: no retry, show error and let user re-submit.
