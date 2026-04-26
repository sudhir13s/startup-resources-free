"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export type Modality =
  | "video"
  | "image"
  | "diagram"
  | "voice"
  | "stt"
  | "best-free"
  | "storyboard";

const TABS: { key: Modality; label: string; description: string }[] = [
  {
    key: "best-free",
    label: "Best free today",
    description:
      "Always-on leaderboard. Per modality: quota remaining + median ETA + quality + last-failure age.",
  },
  {
    key: "video",
    label: "Video gen",
    description:
      "Replicate, fal.ai, HF Spaces (Stable Video Diffusion / AnimateDiff). Free quotas + paid fallback.",
  },
  {
    key: "image",
    label: "Image gen",
    description:
      "FLUX.1-schnell + SDXL via HF, Replicate, fal.ai, Together, Pollinations.",
  },
  {
    key: "diagram",
    label: "Diagram gen",
    description:
      "Free LLM text → Mermaid / Excalidraw JSON → render. Visual rendering local; no provider cost.",
  },
  {
    key: "voice",
    label: "Voice gen (TTS)",
    description:
      "HF Inference TTS, ElevenLabs free monthly quota, fal.ai TTS.",
  },
  {
    key: "stt",
    label: "Speech-to-Text",
    description:
      "Groq Whisper (very fast free), HF Inference Whisper, Gemini audio (free RPD).",
  },
  {
    key: "storyboard",
    label: "Storyboard",
    description:
      "Long input → LLM scene-split → per-scene video gen → ffmpeg concat → final MP4.",
  },
];

const DEFAULT_MODALITY: Modality = "best-free";

export function MediaBenchmarkShell() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const m = (searchParams.get("modality") ?? DEFAULT_MODALITY) as Modality;
  const active = TABS.find((t) => t.key === m) ?? TABS[0];

  const setModality = (key: Modality) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("modality", key);
    router.push(`/media-benchmark?${params.toString()}`);
  };

  return (
    <div className="flex flex-col gap-5">
      <nav
        role="tablist"
        aria-label="Media modalities"
        className="-mx-4 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0"
      >
        {TABS.map((t) => {
          const isActive = t.key === active.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setModality(t.key)}
              className={cn(
                "shrink-0 rounded-md border px-3 py-1.5 text-xs transition-colors",
                isActive
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border bg-bg-surface text-fg-muted hover:bg-bg-tile"
              )}
            >
              {t.label}
            </button>
          );
        })}
      </nav>

      <section
        role="tabpanel"
        aria-label={active.label}
        className="flex flex-col gap-4"
      >
        <header className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-semibold tracking-tight text-fg">
              {active.label}
            </h2>
            <p className="text-sm text-fg-muted">{active.description}</p>
          </div>
          <span className="rounded-full border border-warn/40 bg-warn/10 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-warn">
            v0.3 · scaffold
          </span>
        </header>

        <div className="flex flex-col gap-4 rounded-xl border border-dashed border-border bg-bg-surface p-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent/10 text-accent">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="flex flex-col gap-0.5">
              <h3 className="text-base font-semibold text-fg">
                Locked spec, runtime arrives in v0.3
              </h3>
              <p className="text-xs text-fg-subtle">
                Full design: <code className="font-mono">.claude/rules/project/media-benchmark.md</code>
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Card title="Inputs the page will accept">
              <ul className="list-disc pl-4 text-fg-muted">
                <li>Free-text prompt</li>
                <li>Modality knobs (resolution / duration / scenes / voice)</li>
                <li>System-design content (storyboard mode)</li>
              </ul>
            </Card>
            <Card title="Outputs the page will render">
              <ul className="list-disc pl-4 text-fg-muted">
                <li>Comparison table: provider · cost · ETA · quality · queue</li>
                <li>Side-by-side outputs for batch run</li>
                <li>Quota-remaining badge per row</li>
                <li>Free-first ranking (toggle to show paid)</li>
              </ul>
            </Card>
          </div>

          <Card title="What needs to land first">
            <ul className="list-disc pl-4 text-fg-muted">
              <li>
                <span className="font-medium text-fg">freellm runtime</span> — the
                stub <code className="font-mono">call_image_gen / call_video_gen / call_tts / call_stt</code>{" "}
                today raise NotImplementedError. v0.2b wires LiteLLM
                multimodal calls behind these.
              </li>
              <li>
                <span className="font-medium text-fg">User-supplied API keys</span> —
                at least <code className="font-mono">REPLICATE_API_TOKEN</code> or{" "}
                <code className="font-mono">FAL_API_KEY</code> for image / video,{" "}
                <code className="font-mono">GROQ_API_KEY</code> for STT,{" "}
                <code className="font-mono">ELEVENLABS_API_KEY</code> or{" "}
                <code className="font-mono">HF_TOKEN</code> for TTS.
              </li>
              <li>
                <span className="font-medium text-fg">ffmpeg in the API container</span> —
                storyboard merge needs an ffmpeg binary in the Render image.
                Adds ~50 MB to the build; one-line apt-install.
              </li>
              <li>
                <span className="font-medium text-fg">Calibration agent</span> —
                <code className="font-mono">freellm/calibrate.py</code> runs
                monthly via GH Actions cron, populates per-provider
                ETA/quality calibration data the comparison table uses.
              </li>
            </ul>
          </Card>

          <p className="text-xs text-fg-subtle">
            Until those land, this tab renders as a documentation surface.
            Routes already work — <code className="font-mono">/media-benchmark?modality={active.key}</code>{" "}
            is shareable.
          </p>
        </div>
      </section>
    </div>
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-border bg-bg-base p-4 text-xs">
      <h4 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
        {title}
      </h4>
      {children}
    </div>
  );
}
