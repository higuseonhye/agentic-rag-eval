import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-950">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex items-center justify-between">
          <div className="flex flex-col">
            <div className="text-sm font-medium text-zinc-600">ADW Platform</div>
            <h1 className="text-2xl font-semibold tracking-tight">Trace + Evaluation Explorer</h1>
          </div>
          <nav className="flex items-center gap-2">
            <Link
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm font-medium hover:bg-zinc-50"
              href="/traces"
            >
              Traces
            </Link>
            <Link
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm font-medium hover:bg-zinc-50"
              href="/evaluations"
            >
              Evaluations
            </Link>
          </nav>
        </header>

        <main className="mt-10 grid gap-6 md:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 bg-white p-5">
            <div className="text-sm font-medium text-zinc-900">What this UI does</div>
            <p className="mt-2 text-sm leading-6 text-zinc-600">
              Visualize an ADW run as a trajectory graph (React Flow), inspect each{" "}
              <code className="rounded bg-zinc-100 px-1 py-0.5">AgentStep</code>, and view stored process
              metrics & evaluation artifacts.
            </p>
          </div>
          <div className="rounded-xl border border-zinc-200 bg-white p-5">
            <div className="text-sm font-medium text-zinc-900">Next</div>
            <ul className="mt-2 list-disc pl-5 text-sm leading-6 text-zinc-600">
              <li>Trace list + run detail page</li>
              <li>Trajectory graph with collapsible tree</li>
              <li>Evaluation panel per run</li>
            </ul>
          </div>
        </main>
      </div>
    </div>
  );
}
