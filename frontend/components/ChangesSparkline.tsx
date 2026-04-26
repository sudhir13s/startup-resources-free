import type { Change } from "@/lib/utils";

const WEEKS = 12;
const WIDTH = 320;
const HEIGHT = 48;
const PAD = 4;

function isoWeek(d: Date): string {
  // ISO week key: YYYY-Www. Sufficient for bucketing 12 weeks.
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = (tmp.getUTCDay() + 6) % 7;
  tmp.setUTCDate(tmp.getUTCDate() - dayNum + 3);
  const firstThursday = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 4));
  const week =
    1 +
    Math.round(
      ((tmp.getTime() - firstThursday.getTime()) / 86400000 -
        3 +
        ((firstThursday.getUTCDay() + 6) % 7)) /
        7
    );
  return `${tmp.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

/** Tiny inline-SVG sparkline: stacked reduced (down) + improved (up) per week. */
export function ChangesSparkline({ items }: { items: Change[] }) {
  const buckets = new Map<string, { reduced: number; improved: number }>();
  for (const c of items) {
    const wk = isoWeek(new Date(`${c.snapshot_date}T00:00:00Z`));
    const slot = buckets.get(wk) ?? { reduced: 0, improved: 0 };
    if (c.severity === "reduced" || c.severity === "ended") slot.reduced += 1;
    if (c.severity === "improved" || c.severity === "new") slot.improved += 1;
    buckets.set(wk, slot);
  }

  const keys = Array.from(buckets.keys()).sort();
  const lastN = keys.slice(-WEEKS);
  if (lastN.length === 0) {
    return (
      <div className="text-xs text-fg-subtle">No weekly history yet.</div>
    );
  }

  const max = Math.max(
    1,
    ...lastN.map((k) => {
      const s = buckets.get(k)!;
      return s.reduced + s.improved;
    })
  );
  const barWidth = (WIDTH - 2 * PAD) / lastN.length;

  return (
    <figure className="flex flex-col gap-1">
      <figcaption className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
        Last 12 weeks · {items.length} changes total
      </figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        height={HEIGHT}
        role="img"
        aria-label={`Sparkline of changes over the last ${lastN.length} weeks`}
      >
        {lastN.map((k, i) => {
          const slot = buckets.get(k)!;
          const total = slot.reduced + slot.improved;
          const h = ((HEIGHT - 2 * PAD) * total) / max;
          const reducedH = total > 0 ? (h * slot.reduced) / total : 0;
          const improvedH = h - reducedH;
          const x = PAD + i * barWidth + 1;
          const y = HEIGHT - PAD - h;
          return (
            <g key={k}>
              <rect
                x={x}
                y={y}
                width={barWidth - 2}
                height={improvedH}
                fill="currentColor"
                className="text-ok"
                opacity={0.85}
              />
              <rect
                x={x}
                y={y + improvedH}
                width={barWidth - 2}
                height={reducedH}
                fill="currentColor"
                className="text-bad"
                opacity={0.85}
              />
            </g>
          );
        })}
      </svg>
      <div className="flex items-center gap-3 font-mono text-[10px] text-fg-subtle">
        <span className="inline-flex items-center gap-1">
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 rounded-sm bg-ok"
          />
          improved / new
        </span>
        <span className="inline-flex items-center gap-1">
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 rounded-sm bg-bad"
          />
          reduced / ended
        </span>
      </div>
    </figure>
  );
}
