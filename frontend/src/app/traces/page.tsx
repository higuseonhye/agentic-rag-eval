import Link from "next/link";

type TraceRun = {
  run_id: string;
  created_at: string;
  workflow_name: string;
  route_label: string;
  user_request: string;
};

async function getRuns(): Promise<TraceRun[]> {
  const res = await fetch("http://localhost:8000/api/traces?limit=50", {
    cache: "no-store",
  });
  if (!res.ok) return [];
  const data = (await res.json()) as { runs: TraceRun[] };
  return data.runs ?? [];
}

export default async function TracesPage() {
  const runs = await getRuns();

  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-950">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-zinc-600">ADW Platform</div>
            <h1 className="text-2xl font-semibold tracking-tight">Traces</h1>
          </div>
          <Link className="text-sm font-medium text-zinc-700 hover:text-zinc-950" href="/">
            Home
          </Link>
        </header>

        <div className="mt-6 overflow-hidden rounded-xl border border-zinc-200 bg-white">
          <div className="grid grid-cols-12 gap-2 border-b border-zinc-200 px-4 py-3 text-xs font-semibold text-zinc-600">
            <div className="col-span-3">Created</div>
            <div className="col-span-2">Route</div>
            <div className="col-span-3">Workflow</div>
            <div className="col-span-4">Request</div>
          </div>
          {runs.length === 0 ? (
            <div className="px-4 py-8 text-sm text-zinc-600">
              No runs yet. Start the backend and POST to{" "}
              <code className="rounded bg-zinc-100 px-1 py-0.5">/api/runs</code>.
            </div>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {runs.map((r) => (
                <li key={r.run_id} className="px-4 py-3 hover:bg-zinc-50">
                  <Link href={`/traces/${r.run_id}`} className="grid grid-cols-12 gap-2">
                    <div className="col-span-3 text-xs text-zinc-600">{r.created_at}</div>
                    <div className="col-span-2 text-xs font-medium">{r.route_label}</div>
                    <div className="col-span-3 text-xs text-zinc-700">{r.workflow_name}</div>
                    <div className="col-span-4 truncate text-xs text-zinc-700">{r.user_request}</div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

