import Link from "next/link";

export default function EvaluationsPage() {
  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-950">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-zinc-600">ADW Platform</div>
            <h1 className="text-2xl font-semibold tracking-tight">Evaluations</h1>
          </div>
          <Link className="text-sm font-medium text-zinc-700 hover:text-zinc-950" href="/">
            Home
          </Link>
        </header>

        <div className="mt-6 rounded-xl border border-zinc-200 bg-white p-5">
          <div className="text-sm font-semibold text-zinc-900">Run-scoped evaluations</div>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            MVP stores process-aware metrics per run in Postgres. Next step: list runs here and render the
            evaluation artifacts (process metrics + optional DeepEval judge output).
          </p>
          <div className="mt-4 text-sm text-zinc-600">
            Use <code className="rounded bg-zinc-100 px-1 py-0.5">/api/evaluations/&lt;run_id&gt;</code>
          </div>
        </div>
      </div>
    </div>
  );
}

