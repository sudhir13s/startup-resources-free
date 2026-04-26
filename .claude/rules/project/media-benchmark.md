# Project Rule: Media Generation Benchmark Dashboard (v0.3+)

> Locked spec for the second sub-product inside startup-resources-free: a benchmarking + planning dashboard that takes a prompt, estimates ETA + cost + free-quota + quality across video / image / diagram / voice providers, and ranks free options first. NOT in scope for v0.1 (ship-today seed) or v0.2 (agentic pipeline + freellm router). Build only after v0.2 is stable in prod.

## What it is

Given a prompt (text, story, or system-design content), the user picks a modality (video / image / diagram / voice / multi-step storyboard), and the dashboard returns a comparison table:

| Provider | Model | Free? | Est. Cost | Est. ETA | Quality | Queue | Resolution | Output length |
|---|---|---|---|---|---|---|---|---|

Sorted **free-first** by default. Quotas-remaining-today factor into ranking.

## Modalities covered

| Modality | Free providers initially targeted |
|---|---|
| Video gen | Replicate (free quota), fal.ai (free quota), HF Spaces (Stable Video Diffusion, AnimateDiff), local ComfyUI on free GPU (Colab/Kaggle) |
| Image gen | HF Inference (FLUX.1-schnell, SDXL), Replicate free, fal.ai free, Together free image, Pollinations free |
| Diagram gen | LLM-text → Mermaid / Excalidraw JSON → render. Provider = whichever free LLM in `freellm/` succeeds. Visual rendering local, no provider cost. |
| Voice / TTS | HF Inference TTS, ElevenLabs free monthly quota, fal.ai TTS, OpenAI TTS (paid only — gated behind LLM_ALLOW_PAID) |
| STT | Groq Whisper (very fast free), HF Inference Whisper, Gemini audio (free RPD) |
| Storyboard mode | LLM splits text → N scenes → batched calls per scene to one of the above modalities. Aggregator merges. |

## Estimation model

Per provider per modality, the catalog (`freellm/providers.py`) carries calibration data:

```python
class EtaCalibration(BaseModel):
    provider: str
    model: str
    modality: Modality
    base_seconds: float                # baseline: minimal prompt, default settings
    seconds_per_output_second: float   # for video / audio
    seconds_per_megapixel: float       # for image
    seconds_per_token: float           # for text
    queue_factor: float                # multiplier when queue depth > N
    last_calibrated: date              # we re-measure monthly via smoke-test
```

ETA formula (video example):
```
eta_seconds = base_seconds
            + seconds_per_output_second * requested_duration_s
            + complexity_multiplier(prompt_token_count, has_motion_keywords)
            + queue_factor_now()
```

Cost is `cost_per_unit * units` where `unit` is provider-specific (per-second-of-video, per-megapixel-image, per-1k-tokens). For free-tier providers, cost is `0.0` until quota exhausts; the dashboard shows quota-remaining alongside.

Calibration is auto-refreshed monthly via a smoke-test agent: `freellm/calibrate.py` sends a tiny job to each provider, measures wall-clock + queue, writes back to the catalog.

## UI placement (LOCKED)

This is its own top-level navigation section, NOT a tab inside the catalog. Two-level nav:

- **Catalog** (the v0.1 ship)
- **Media Benchmark** (the new section)
  - Sub-tabs: Video gen | Image gen | Diagram gen | Voice gen | STT | Best free today | Storyboard
- **Settings**

Each sub-tab has the same shape:
1. Prompt input (textarea, ⌘Enter to submit).
2. Knobs (resolution, duration, scene count, etc. — modality-specific).
3. "Estimate" button → renders the comparison table.
4. "Run on free providers" button → batch executes across free options, shows actual results when each finishes.
5. Results board with side-by-side outputs.

## "Best free models today" sub-tab

Always-visible leaderboard. Per modality, ranked by:
1. Quota remaining today.
2. Median ETA over the last 7 days.
3. Quality tier (curated, 1-5 scale).
4. Last-failure age (recently failed providers demoted).

Uses the same per-provider quota state from `freellm/quotas.py`.

## Storyboard mode

For long inputs (system-design explanations, stories), an LLM in the `freellm/` text chain splits the prompt into scenes (3-12 typical). Each scene is dispatched as its own video / image generation. A merge step (ffmpeg locally) stitches outputs into one video.

```
User input: "Explain Netflix system design with animations"
  ↓
LLM scene-split (free text chain)
  ↓
Scene 1: "Users open the Netflix app, send request to CDN edge"
Scene 2: "Edge routes to API gateway, gateway hits load balancer"
Scene 3: "Microservices fan out, write to Cassandra + read-through to S3"
...
  ↓
Per-scene video generation (free video chain)
  ↓
ffmpeg concat → MP4 output
```

Cost: $0 if all scenes hit free quotas. Dashboard shows cumulative quota burn.

## Routing: leverages existing `freellm/`

The benchmark UI does NOT introduce a new router. It calls `freellm/`:

```python
from freellm import call_video_gen, estimate_cost_and_eta, Plan

plan: Plan = estimate_cost_and_eta(
    modality="video_gen",
    prompt="...",
    duration_s=10,
    resolution="720p",
)
# plan.options == [{provider, model, eta_s, cost_usd, free_quota_remaining}, ...]
# Sorted free-first by default.

result = await call_video_gen(prompt="...", duration_s=10, resolution="720p", task_name="benchmark-demo-1")
```

`estimate_cost_and_eta` is a new public method added to `freellm/` in v0.3 — uses the calibration data described above. Dashboard renders `plan.options` as the comparison table.

## API contract (FastAPI, v0.3+)

```
POST /api/benchmark/estimate
  body: { modality, prompt, knobs }
  → { options: [...], best_free: { provider, model, eta_s } | null }

POST /api/benchmark/run
  body: { modality, prompt, knobs, providers: [...]? }
  → SSE stream of per-provider progress events + final outputs

GET  /api/benchmark/leaderboard?modality=
  → live "best free today" rankings

POST /api/benchmark/storyboard
  body: { prompt, modality_per_scene, target_total_duration_s }
  → SSE stream: scene-split → per-scene generation → merge → final URL
```

Outputs are stored under `data/benchmark_runs/<run_id>/` with a 7-day TTL (gitignored). User can pin a run to keep it longer.

## What this depends on (build order)

- `freellm/` text + image_gen + video_gen + voice + STT chains MUST be working (v0.2).
- Quota tracking MUST be persistent (v0.2).
- Calibration agent (`freellm/calibrate.py`) is NEW in v0.3 — runs monthly via GH Actions cron.
- ffmpeg installed in Render service (or local-only for v0.3 scope).

## Anti-patterns (block in review)

- Hardcoded ETAs in code. Calibration data lives in `freellm/providers.py` only.
- Costs in any unit other than USD. Convert at ingest if a provider quotes elsewhere.
- Bypassing `freellm/` to call a provider directly from the benchmark code.
- Synchronous `subprocess.run("ffmpeg ...")` in a request handler. Always async + offloaded.
- Auto-running paid models without `LLM_ALLOW_PAID=1`.
- Caching estimates longer than 1 hour without invalidating on quota state changes.

## Out of scope (forever, until user re-scopes)

- Side-by-side video diffusion model TRAINING.
- Local-only mode requiring user GPU (consumer GPUs are out of MVP scope; revisit if user has Colab/Kaggle wired).
- Anything that requires uploading user video for ingest (privacy + hosting cost).
