import { TopBar } from "@/components/TopBar";
import { MediaBenchmarkShell } from "@/components/MediaBenchmarkShell";

export const dynamic = "force-dynamic";

export default function MediaBenchmarkPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-6">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              Media Benchmark
            </h1>
            <p className="text-sm text-fg-muted">
              Paste a prompt → see ETA + cost + free-quota + quality
              across video, image, diagram, voice, and STT providers,
              ranked free-first. Storyboard mode auto-splits long
              prompts into scenes.
            </p>
          </header>

          <MediaBenchmarkShell />
        </div>
      </main>
    </div>
  );
}
