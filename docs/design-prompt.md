# Design Prompt — paste into a design tool / designer LLM

> Paste the entire **PROMPT** block below into Lovable, v0, Galileo AI, Stitch, Uizard, Figma AI, or a designer LLM (Claude, GPT-4o, Gemini). Output: a high-fidelity dashboard UI/UX for the **startup-resources-free** project.
>
> If your tool accepts only short input, use the **SHORT PROMPT** further down.
>
> **NOTE on phasing**: The prompt below describes the FULL spec (v0.2+). The 2-hour ship (v0.1) is a Catalog-only cut: 4 tier chips + provider grid + dark-only + "Works in India" badge + parse-confidence dot + freshness label. Compare/Changes/Verify tabs render disabled with "Coming soon." NO Free-LLM-Chain filter, NO slide-over (inline expand instead), NO Media Benchmark sub-product. Use the **V0.1 SHORT PROMPT** at the very bottom for that scope.

---

## PROMPT (copy from here ⬇)

You are a senior product designer designing a data-rich dashboard. Output: a single-page web application UI in a clean, modern, technical style — think Linear + Vercel dashboard + Grafana, NOT a marketing landing page.

### What the product is

**FreeStack Radar** — a personal-first intelligence dashboard that aggregates **free / discounted / time-limited offerings** from cloud, GPU, AI API, database, hosting, startup-credit, grant, accelerator, and OSS providers. A single founder uses it to find the right free tools for the project they're building right now. **Audience is India-primary** — Indian programs surfaced first, US/global programs accessible-from-India tagged.

The product has TWO sub-products inside one app:

1. **Catalog** (the main view) — browse providers by use-case tier + category + region.
2. **Media Benchmark** (v0.3+) — paste a prompt → see ETA + cost + free-quota + quality across video / image / diagram / voice providers, ranked free-first. Includes a "Storyboard" mode that splits long prompts (e.g. system-design explanations) into scenes for per-scene video gen + ffmpeg merge.

Tech stack (locked): FastAPI backend, Next.js 14 + Tailwind + shadcn/ui frontend, Render hosting, GitHub Actions cron.

The headline differentiator is a **use-case tier filter**: the user picks the tier their project is at, and the dashboard shows only providers that genuinely fit.

### Tier filter — the most important UX element

Four mutually exclusive radio-style chips at the top of the page (large, prominent, distinctive — this is the hero control):

1. **Hobby** — weekend tinkering, throwaway demos
2. **Personal** — small personal site, single user, always-on
3. **Startup MVP** — pre-revenue prototype, 10–1000 users, easy upgrade path
4. **Startup** — paying users, production reliability, free tier as dev/sandbox only

Each chip has a one-line subtitle (the description above) and a count of matching providers. Selected chip is visually dominant. Selecting a chip filters the entire dashboard immediately (no apply button).

### Secondary filters (left sidebar, collapsible)

- **Category** (multi-select): Cloud, GPU, AI APIs, Databases, Storage, Auth, Observability, Domains, Startup Credits, Grants, Accelerators, Perks, OSS, Learning
- **Offer type** (multi-select): always-free, free-credits, free-trial, free-quota, grant, perk, OSS
- **Region**: global / US / EU / India / other (country picker)
- **Eligibility**: any / student / startup / founder / India-resident
- **Status**: active / reduced / ended / unknown
- **Min parse confidence**: high / medium / low (default: high+medium)

### Main content area — three views, switchable via tabs

#### Tab 1: **Catalog** (default)

A responsive grid of provider cards (3 columns desktop, 1 column mobile). Each card:

- Provider logo (left, 48px) + provider name (bold) + category pill
- Offer summary (one sentence, e.g. "Free LLM inference up to 14,400 req/day across Llama-3 + Mixtral")
- Three stat tiles in a row: **Free quota** | **Duration** | **Region**
- Tier-fit badges (small chips: "Hobby ✓", "Personal ✓", "MVP ✓", "Startup ✗")
- Footer row: `Last verified 3 days ago` (with freshness indicator) + `View source ↗` link + a `★ Save` button
- A subtle parse-confidence indicator (green dot = high, amber = medium, red = low + "verify yourself" tooltip)

Cards open a slide-over panel on click with full record detail (eligibility, restrictions, history, links).

Sort options (top-right of grid): Best fit / Most generous / Most recently changed / Alphabetical.

#### Tab 2: **Compare**

A wide table (sticky header, sticky first column) where the user has pinned 2–6 providers. Columns are field-by-field: free quota, duration, region, sleep policy, signup method, restrictions, tier fit. Differences highlighted in amber. Export-to-CSV button top-right.

#### Tab 3: **Changes** (timeline)

A reverse-chronological feed of "what changed in the last 30 days." Each entry:

- Provider + category
- Field that changed: e.g. `free_quota: 5000 → 1000 req/day`
- Severity badge: 🔻 Reduced / 🔺 Improved / ❌ Ended / ✅ New
- Timestamp + source URL

A small sparkline at the top shows "providers reduced" vs "providers improved" per week for the last 12 weeks.

#### Tab 4: **Verify** (admin/personal)

A queue of records with `parse_confidence: low`. Each row shows: extracted record on the left, source page screenshot on the right, two big buttons: **Confirm** / **Reject**. A keyboard shortcut hint (`y`/`n`).

### Top bar

- Logo + product name (left)
- Primary nav: `Catalog | Media Benchmark | Settings` (top-level, NOT tabs inside Catalog)
- **Search** (center, prominent, ⌘K shortcut) — type "free postgres 10gb" or "AI inference for India," fuzzy-matches across all fields
- **Tier filter** (the four chips described above, immediately under the top bar — actually the second row, but visually the hero)
- Right side: theme toggle (dark default) + "Last updated 2 hours ago" with a green dot if the daily pipeline ran cleanly + "Run now" button (for manual pipeline trigger)

### Media Benchmark section (v0.3+)

A dedicated top-level section, NOT a tab inside Catalog. Sub-tabs:

- **Video gen** | **Image gen** | **Diagram gen** | **Voice gen** | **STT** | **Best free today** | **Storyboard**

Each sub-tab layout:
1. Prompt input (textarea, ⌘Enter to submit). Modality-specific knobs below: resolution / duration / scene count / voice style.
2. **Estimate** button — renders a comparison table:
   `Provider | Model | Free? | Est. Cost | Est. ETA | Quality | Queue | Resolution | Output length`
   Sorted free-first by default (toggle: "Show paid too").
3. **Run on free providers** button — batch-executes; shows progress per provider, displays outputs side-by-side as each finishes.
4. Quota-remaining badges next to each provider row (live from `freellm/quotas.py`).

**Best free today** sub-tab is an always-visible leaderboard ranked by: quota-remaining + median ETA over 7 days + quality tier + last-failure age.

**Storyboard** sub-tab is for long inputs (e.g. system-design explanations). Flow: paste prompt → LLM splits into 3-12 scenes (free text chain) → per-scene video gen (free video chain) → ffmpeg merge → final MP4. Cumulative quota-burn shown as it runs. UI: vertical scene list with thumbnails + ETAs + status; final merged video at top once ready.

Visual style for Media Benchmark matches Catalog (dark, technical, density-focused). Microcopy: "Free first" badge color must match Catalog's "Works in India" pattern for consistency.

### Empty / loading / error states

- **Empty filter result:** large icon + "No free providers match these filters. Try widening Region or lowering parse-confidence." with a "Reset filters" button.
- **Pipeline running:** a soft progress bar in the top bar with "Refreshing 47 providers — currently checking Vercel."
- **Pipeline failed:** red banner with "Last run failed. View logs →" — non-dismissable until acknowledged.
- **Provider with low confidence:** card has an amber border + "We're not sure — verify the source link."

### Visual style

- **Theme:** Dark first (`#0a0a0a` background, `#e5e5e5` text). Light theme available.
- **Accent color:** A single saturated accent — proposed: a vivid teal (`#06b6d4`) for primary actions, with semantic colors green/amber/red for status.
- **Typography:** Inter for UI, JetBrains Mono for numbers and code. Clear hierarchy: `text-2xl/bold` for headers, `text-sm` for body.
- **Density:** Information-dense but breathable. Cards have `p-6`, gaps are `gap-4` to `gap-6`.
- **Animations:** Subtle. Filter changes fade in 150ms. No bounces, no parallax.
- **Iconography:** Lucide icons. Provider logos from public Brandfetch / Clearbit logos (with fallback to first-letter monogram).
- **Inspiration anchors:** Linear (sidebar + density), Vercel dashboard (data cards), Grafana (timeline), Raycast (search), Stripe Atlas (info hierarchy).

### Accessibility (mandatory — WCAG 2.1 AA)

- Tier-filter chips: keyboard-navigable, focus ring visible, ARIA `role="radiogroup"`.
- Color is never the sole signal — every status carries an icon AND a label.
- Contrast ≥ 4.5:1 for body text, ≥ 3:1 for large text.
- All interactive elements have `aria-label` if they're icon-only.
- Slide-over panels trap focus when open; Esc closes.
- Skip-to-content link for keyboard users.
- The "Confirm/Reject" verify queue supports keyboard shortcuts (y/n) AND tooltips that show those shortcuts.

### Responsive behavior

- Desktop (≥ 1280px): sidebar visible, 3-column grid.
- Tablet (768–1279px): sidebar collapses to a drawer, 2-column grid.
- Mobile (< 768px): sidebar is bottom-sheet, 1-column grid, tier-filter chips horizontal-scroll.

### Microcopy guidelines

- Plain, technical, no marketing fluff. "Free quota" not "Generous offer."
- Numbers always with units (`14,400 req/day` not `14400`).
- Date display: relative for < 7 days ("3 days ago"), absolute thereafter.
- Verbs in buttons: "Save," "Compare," "Verify," "Run now." Not "Click here."
- Empty states have one specific suggestion, not generic encouragement.

### Output

Generate:

1. The full single-page dashboard (Catalog tab default).
2. The Changes tab.
3. The Verify queue tab.
4. The slide-over panel (provider detail).
5. Mobile layouts of the same.
6. A small design-system spec: color tokens, type scale, spacing scale, component variants (button, card, chip, badge, table row, slide-over, banner).

Use Tailwind class names if generating React/HTML. If generating Figma frames, group by tab. Export tokens as CSS custom properties.

### What NOT to do

- No marketing hero, no "Sign up free" CTA — this is a dashboard, not a landing page.
- No carousel, no animated illustrations, no gradients used as primary surfaces.
- No emojis as functional icons (only as inline status badges where they help).
- No fake testimonials or pricing tables.
- No generic stock photos.
- No "AI-generated by ___" footer or watermark.
- No color-only signals — every status has a label.

---

## SHORT PROMPT (for tools with strict input limits)

> Design a dark-mode, information-dense dashboard called **FreeStack Radar**. It aggregates free-tier offerings (cloud, GPU, AI APIs, databases, hosting, credits, grants, OSS).
>
> **Hero control**: four prominent radio chips at the top — `Hobby`, `Personal`, `Startup MVP`, `Startup` — that filter the whole dashboard by intended project tier. Each chip shows a count.
>
> **Layout**: left sidebar (category, offer-type, region, eligibility, parse-confidence filters), top bar (logo, ⌘K search, tier chips, "Last updated" + "Run now"), main area with four tabs: **Catalog** (3-column grid of provider cards with tier-fit badges and freshness/confidence indicators), **Compare** (sticky table for pinned providers), **Changes** (reverse-chrono timeline of free-tier changes with severity badges + 12-week sparkline), **Verify** (queue of low-confidence records with Confirm/Reject keyboard shortcuts).
>
> **Style**: Linear + Vercel + Grafana inspiration. Dark `#0a0a0a` bg, `#06b6d4` accent. Inter + JetBrains Mono. Lucide icons. Tailwind. WCAG AA. No marketing fluff.
>
> Generate desktop + mobile layouts for all tabs, plus a slide-over provider-detail panel, plus design tokens (color, type, spacing).

---

## How to use this prompt

| Tool | What to paste |
|---|---|
| **v0.dev (Vercel)** | Long PROMPT. Iterate on each tab separately if it truncates. |
| **Lovable** | Long PROMPT. It builds full apps — ask for SQLite + Streamlit if you want it to also wire up backend (but our backend is Python, so prefer it design-only). |
| **Galileo AI / Uizard** | Short PROMPT. They prefer concise descriptions. |
| **Figma AI** | Short PROMPT. Then iterate per-tab. |
| **Designer LLM (Claude / GPT-4o / Gemini)** | Long PROMPT. Ask for HTML+Tailwind output if you want to see it rendered immediately. |
| **Stitch (Google)** | Short PROMPT. Stitch likes one-screen-at-a-time prompts; run it 4× (once per tab). |

After generating, iterate on:
- The tier-filter chip aesthetic (this is THE differentiator — get it right).
- The provider card density (too sparse looks like a marketing site; too dense overwhelms).
- The Changes tab — this is the second-most-important view and easy to get wrong.
- Mobile tier-filter behavior.

When you're happy, save outputs in `docs/designs/<YYYY-MM-DD>-<tool>-<short-name>/` per the dated-artifacts rule.
