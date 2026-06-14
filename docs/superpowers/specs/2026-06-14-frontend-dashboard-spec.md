---
# Frontend Dashboard Spec
**Date:** 2026-06-14
**Project:** tw_stock_trade
**Status:** Approved

## Stack

| Item | Choice |
|------|--------|
| Framework | Next.js 15 (App Router) |
| Components | shadcn/ui (customized, dark theme) |
| Styling | Tailwind v4 |
| Charts | Recharts |
| Icons | @phosphor-icons/react |
| Motion | motion/react (subtle only) |
| Font display | Geist |
| Font mono | Geist Mono (ALL numbers) |

## Design Tokens

| Token | Value |
|-------|-------|
| Background | zinc-950 (#09090b) |
| Surface +1 | zinc-900 (#18181b) |
| Surface +2 | zinc-800 (#27272a) |
| Border | zinc-800 (#27272a) |
| Text primary | zinc-100 (#f4f4f5) |
| Text muted | zinc-500 (#71717a) |
| Accent | blue-500 (#3b82f6) |
| Positive | emerald-400 (#34d399) |
| Negative | red-400 (#f87171) |
| Corner radius | rounded-sm (4px) unified |

## Layout Structure

`
Header (64px fixed)
KPI Row (72px)
──────────────────────────────────────────
Left 60% (tabs, scrollable) | Right 40% (AI Panel, fixed)
`

## Header

- Logo left: "TW Trade", Geist, text-zinc-100
- Center: TWSE ticker via WS /ws/quotes, Geist Mono, green/red on change
- Status dots (2 only, semantic): Market open/closed, API connected
- Right: theme toggle icon button

## KPI Row (non-equal width)

| Slot | Width | Content |
|------|-------|---------|
| Total Assets | 28% | TWD amount + today % change |
| Available Cash | 28% | TWD amount + % of portfolio |
| Holdings MV | 22% | TWD amount + position count |
| Win Rate | 22% | % + trade count |

- Separated by border-l border-zinc-800, no card box, no shadow
- All numbers: Geist Mono
- Sub-text: text-xs text-zinc-500

## Left Panel — Tab Bar

Tabs: **Overview** | **Holdings** | **History**

- Active: border-b-2 border-blue-500 text-zinc-100
- Inactive: text-zinc-500 hover:text-zinc-300

### Tab: Overview

**Performance Chart**
- Recharts AreaChart, Total Assets trend
- Time range toggle: 7D / 30D / 90D (pill, active = bg-zinc-800)
- Fill: blue-500 gradient to transparent
- Grid: horizontal dashes only, stroke zinc-800
- Tooltip: date + TWD (Geist Mono)
- Data: GET /portfolio/history

**Recent Decisions (last 3)**
- Data: GET /ai/decisions?limit=3
- Each row: date | symbol | action badge | short reason | [expand]
- Expand: shows bull/bear/risk summary inline (shadcn Collapsible)
- Footer: [view all →] links to Decisions in right panel

### Tab: Holdings

- Header: "HOLDINGS N positions" + [Analyze All] button (right)
- Table with divide-y divide-zinc-800, no outer border
- Columns: 股票名稱+代碼 / 均價 / 現價 / 市值 / 未實現P&L / %
- Positive P&L: text-emerald-400
- Negative P&L: text-red-400
- All prices/amounts: Geist Mono
- Click row → fills AI Panel input with symbol + focuses panel

### Tab: History

- Filter bar: symbol select / date range / action (BUY/SELL/ALL)
- Table with divide-y divide-zinc-800
- Columns: 時間 / 動作 / 股票 / 張數 / 價格 / 金額 / 實現P&L
- BUY badge: bg-blue-500/15 text-blue-400 rounded-sm
- SELL badge: bg-zinc-700 text-zinc-300 rounded-sm
- P&L shown only for SELL rows
- Infinite scroll / load more

## Right Panel — AI Panel (fixed, no tab switching)

Three sections separated by border-t border-zinc-800:

### Section 1: Run Analysis

- Input: stock code autocomplete (from holdings list)
- [Run] button: POST /ai/analyze, returns session_id
- On click from Holdings tab row: auto-fills input

### Section 2: Live Stream

- Connects to WS /ws/ai-stream?session_id={id}&token={jwt}
- Header: session short-id + semantic dot (● analyzing / dim when done)
- Event rows (one per WS message):
  - started: Phosphor icon ⬡ + "started" + symbol + timestamp
  - bull: ↗ icon text-emerald-400 + content
  - bear: ↘ icon text-red-400 + content
  - risk: ⚖ icon text-zinc-400 + content
  - decision: ✓ icon text-blue-400 + action + reason
- Auto-scroll to bottom on new event
- On completed/failed: dot dims, stream closes

### Section 3: Decision Log

- Data: GET /ai/decisions (infinite scroll)
- Each row: timestamp | symbol | action badge | short reason | [▸ expand]
- Expand (shadcn Collapsible): full bull/bear/risk arguments
- Action badges: same rounded-sm system as History tab

## API Endpoints Consumed

| Endpoint | Used by |
|----------|---------|
| WS /ws/quotes | Header ticker |
| GET /portfolio/history | Overview chart |
| GET /ai/decisions | Overview recent + Decision Log |
| POST /ai/analyze | AI Panel Run button |
| WS /ws/ai-stream | AI Panel Live Stream |
| GET /holdings | Holdings tab |
| GET /trades | History tab |

## taste-skill Rules Applied

- No card boxes except where elevation needed — use border-t / divide-y
- No decorative dots — only 2 semantic status dots in header
- No em-dash anywhere
- No AI-purple — accent is blue-500
- No equal-width KPI grid — 28/28/22/22 split
- Geist Mono on ALL numbers, always
- Corner radius unified: rounded-sm (4px) everywhere
- SELL/BUY/HOLD badges all rounded-sm — Shape Consistency Lock
- No section-number eyebrows
- No Inter as default font
- Background: zinc-950 surface-level system, not pure black
