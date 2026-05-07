"use client";

import type { Edge, Node } from "reactflow";
import React, { useEffect, useMemo, useState } from "react";
import ReactFlow, { Background, Controls } from "reactflow";

import "reactflow/dist/style.css";

type AgentStep = {
  step_id: string;
  parent_step_id: string | null;
  run_id: string;
  step_index: number;
  step_type: string;
  name: string | null;
  input: unknown;
  output: unknown;
  latency_ms: number | null;
  token_usage: unknown;
  score: unknown;
  error: string | null;
  created_at: string;
};

type EvalRow = {
  eval_id: string;
  eval_type: string;
  metrics: unknown;
  error: string | null;
  created_at: string;
};

function buildGraph(steps: AgentStep[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  for (const s of steps) {
    nodes.push({
      id: s.step_id,
      position: { x: 0, y: 0 },
      data: {
        label: `${s.step_index}. ${s.step_type}${s.name ? `:${s.name}` : ""}`,
        step: s,
      },
      type: "default",
    });
    if (s.parent_step_id) {
      edges.push({
        id: `${s.parent_step_id}->${s.step_id}`,
        source: s.parent_step_id,
        target: s.step_id,
        animated: s.step_type === "retrieval",
      });
    }
  }

  const sorted = [...steps].sort((a, b) => a.step_index - b.step_index);
  const idxById = new Map(sorted.map((s, i) => [s.step_id, i]));
  for (const n of nodes) {
    const i = idxById.get(n.id) ?? 0;
    const step = (n.data as { step: AgentStep }).step;
    const x = step.step_type === "retrieval" ? 40 : step.step_type === "evaluation" ? 340 : 180;
    n.position = { x, y: i * 90 };
  }

  return { nodes, edges };
}

type MemoryListItem = {
  memory_id: string;
  kind: string;
  title: string | null;
  status: string;
  provenance_run_id: string | null;
  created_at: string;
};

type KnowledgeUnitRow = {
  unit_id: string;
  title: string;
  unit_type: string;
  provenance_run_id: string | null;
};

export default function TraceRunPage({ params }: { params: { runId: string } }) {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [run, setRun] = useState<Record<string, unknown> | null>(null);
  const [selected, setSelected] = useState<AgentStep | null>(null);
  const [evaluations, setEvaluations] = useState<EvalRow[]>([]);
  const [tab, setTab] = useState<"trace" | "memory" | "replay" | "artifacts" | "knowledge">("trace");
  const [memoryItems, setMemoryItems] = useState<MemoryListItem[]>([]);
  const [knowledgeUnits, setKnowledgeUnits] = useState<KnowledgeUnitRow[]>([]);
  const [replayBusy, setReplayBusy] = useState(false);
  const [replayInfo, setReplayInfo] = useState<unknown>(null);

  useEffect(() => {
    void (async () => {
      const [tRes, eRes, mRes, kRes] = await Promise.all([
        fetch(`http://localhost:8000/api/traces/${params.runId}`),
        fetch(`http://localhost:8000/api/evaluations/${params.runId}`),
        fetch(`http://localhost:8000/api/memory?limit=200`),
        fetch(`http://localhost:8000/api/knowledge/units?limit=200`),
      ]);
      if (tRes.ok) {
        const data = (await tRes.json()) as { run: Record<string, unknown>; steps: AgentStep[] };
        setRun(data.run);
        setSteps(data.steps ?? []);
      }
      if (eRes.ok) {
        const ed = (await eRes.json()) as { evaluations: EvalRow[] };
        setEvaluations(ed.evaluations ?? []);
      }
      if (mRes.ok) {
        const md = (await mRes.json()) as { items: MemoryListItem[] };
        setMemoryItems(md.items ?? []);
      }
      if (kRes.ok) {
        const kd = (await kRes.json()) as { units: KnowledgeUnitRow[] };
        setKnowledgeUnits(kd.units ?? []);
      }
    })();
  }, [params.runId]);

  const graph = useMemo(() => buildGraph(steps), [steps]);

  const retrievalSteps = useMemo(
    () => steps.filter((s) => s.step_type === "retrieval"),
    [steps],
  );

  const memoryForRun = useMemo(
    () => memoryItems.filter((m) => m.provenance_run_id === params.runId),
    [memoryItems, params.runId],
  );

  const knowledgeForRun = useMemo(
    () => knowledgeUnits.filter((u) => u.provenance_run_id === params.runId),
    [knowledgeUnits, params.runId],
  );

  const memorySteps = useMemo(
    () => steps.filter((s) => s.step_type === "memory"),
    [steps],
  );

  const rerankDeltas = useMemo(() => {
    return retrievalSteps.map((s) => {
      const out = s.output as Record<string, unknown> | undefined;
      const diag = out?.diagnostics as Record<string, unknown> | undefined;
      const pre = (diag?.pre_rerank_top_ids as string[] | undefined) ?? [];
      const post =
        ((out?.results as Array<{ chunk_id?: string }> | undefined) ?? []).map(
          (r) => r.chunk_id ?? "",
        ) ?? [];
      const moved =
        pre.length && post.length
          ? pre.filter((id, i) => post[i] !== id).length
          : 0;
      return { step_index: s.step_index, pre, post, moved };
    });
  }, [retrievalSteps]);

  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-950">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-zinc-600">Trace run</div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {params.runId.slice(0, 8)}…{" "}
              <span className="ml-2 text-sm font-medium text-zinc-600">
                {run?.route_label as string}
              </span>
            </h1>
          </div>
          <a className="text-sm font-medium text-zinc-700 hover:text-zinc-950" href="/traces">
            Back
          </a>
        </header>

        <div className="mt-4 flex flex-wrap gap-2">
          {(
            [
              ["trace", "Trace"],
              ["memory", "Memory"],
              ["knowledge", "Knowledge units"],
              ["replay", "Replay"],
              ["artifacts", "Artifacts"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                tab === id ? "bg-zinc-900 text-white" : "bg-zinc-200 text-zinc-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "memory" ? (
          <section className="mt-6 rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-zinc-900">Memory (provenance + trace)</h2>
            <p className="mt-2 text-xs text-zinc-600">
              Memory items linked to this run + memory steps recorded in the trace.
            </p>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div>
                <div className="text-xs font-semibold text-zinc-800">MemoryItems for this run</div>
                {memoryForRun.length === 0 ? (
                  <p className="mt-2 text-xs text-zinc-600">No MemoryItems with matching provenance_run_id.</p>
                ) : (
                  <ul className="mt-2 space-y-2 text-xs">
                    {memoryForRun.map((m) => (
                      <li key={m.memory_id} className="rounded border border-zinc-100 p-2">
                        <div className="font-medium">{m.title ?? m.kind}</div>
                        <div className="text-zinc-600">{m.memory_id}</div>
                        <div className="text-zinc-500">status: {m.status}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <div className="text-xs font-semibold text-zinc-800">Trace steps (step_type=memory)</div>
                {memorySteps.length === 0 ? (
                  <p className="mt-2 text-xs text-zinc-600">No memory steps on this trace.</p>
                ) : (
                  <ul className="mt-2 space-y-2 text-xs">
                    {memorySteps.map((s) => (
                      <li key={s.step_id} className="rounded border border-zinc-100 p-2">
                        <div className="font-medium">
                          #{s.step_index} {s.name}
                        </div>
                        <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-zinc-600">
                          {JSON.stringify({ input: s.input, output: s.output }, null, 2)}
                        </pre>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>
        ) : null}

        {tab === "knowledge" ? (
          <section className="mt-6 rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-zinc-900">Knowledge units</h2>
            {knowledgeForRun.length === 0 ? (
              <p className="mt-2 text-xs text-zinc-600">
                No compiled KnowledgeUnits with provenance_run_id matching this run.
              </p>
            ) : (
              <ul className="mt-3 space-y-2 text-xs">
                {knowledgeForRun.map((u) => (
                  <li key={u.unit_id} className="rounded border border-zinc-100 p-2">
                    <div className="font-medium">{u.title}</div>
                    <div className="text-zinc-600">{u.unit_id}</div>
                    <div className="text-zinc-500">type: {u.unit_type}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}

        {tab === "replay" ? (
          <section className="mt-6 rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-zinc-900">Replay / regression</h2>
            <p className="mt-2 text-xs text-zinc-600">
              Re-executes the ADW workflow with the same user_request and stores a diff evaluation artifact on the new
              run.
            </p>
            <button
              type="button"
              disabled={replayBusy}
              className="mt-3 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
              onClick={() =>
                void (async () => {
                  try {
                    setReplayBusy(true);
                    const res = await fetch(`http://localhost:8000/api/replay/from-run/${params.runId}`, {
                      method: "POST",
                      headers: { "content-type": "application/json" },
                      body: JSON.stringify({}),
                    });
                    const body = await res.json();
                    setReplayInfo(body);
                  } finally {
                    setReplayBusy(false);
                  }
                })()
              }
            >
              {replayBusy ? "Replaying…" : "Replay this run"}
            </button>
            {replayInfo ? (
              <pre className="mt-3 max-h-80 overflow-auto rounded border border-zinc-200 p-2 text-xs">
                {JSON.stringify(replayInfo, null, 2)}
              </pre>
            ) : null}
          </section>
        ) : null}

        {tab === "artifacts" ? (
          <section className="mt-6 rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-zinc-900">Multimodal artifacts (video-lite)</h2>
            <p className="mt-2 text-xs text-zinc-600">
              Upload and transcript indexing happen via{" "}
              <span className="font-mono">POST /api/artifacts/video</span> and{" "}
              <span className="font-mono">POST /api/artifacts/transcript/{"{artifact_id}"}</span>. This panel is a
              placeholder hook for a dedicated artifact viewer.
            </p>
          </section>
        ) : null}

        <div className={`mt-6 grid gap-4 lg:grid-cols-2 ${tab !== "trace" ? "hidden" : ""}`}>
          <section className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-zinc-900">Retrieval timeline</h2>
            {retrievalSteps.length === 0 ? (
              <p className="mt-2 text-xs text-zinc-600">No retrieval steps (e.g. L0 no retrieval).</p>
            ) : (
              <ul className="mt-2 space-y-2 text-xs">
                {retrievalSteps.map((s) => {
                  const out = s.output as Record<string, unknown> | undefined;
                  const diag = out?.diagnostics as Record<string, unknown> | undefined;
                  const isSel = selected?.step_id === s.step_id;
                  return (
                    <li
                      key={s.step_id}
                      className={`rounded border border-zinc-100 p-2 ${isSel ? "ring-1 ring-zinc-400" : ""}`}
                    >
                      <button
                        type="button"
                        className="text-left font-medium text-zinc-800"
                        onClick={() => setSelected(s)}
                      >
                        #{s.step_index} {s.name}
                      </button>
                      <div className="mt-1 text-zinc-600">
                        cov:{" "}
                        {String(
                          (s.score as Record<string, unknown> | null)?.coverage_score ?? "-",
                        )}{" "}
                        · ms: {s.latency_ms ?? "-"}
                      </div>
                      {diag?.dense_backend ? (
                        <div className="text-zinc-500">dense: {String(diag.dense_backend)}</div>
                      ) : null}
                      {diag?.graph_skipped ? (
                        <div className="text-zinc-500">graph: {String(diag.graph_skipped)}</div>
                      ) : null}
                      {(diag?.graph_neighbor_ids as string[] | undefined)?.length ? (
                        <div className="text-zinc-500">
                          graph chunks:{" "}
                          {(diag?.graph_neighbor_ids as string[]).join(", ")}{" "}
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-zinc-900">Rerank delta (pre vs post order)</h2>
            {rerankDeltas.length === 0 ? (
              <p className="mt-2 text-xs text-zinc-600">No retrieval iterations.</p>
            ) : (
              <ul className="mt-2 space-y-2 text-xs font-mono">
                {rerankDeltas.map((d) => (
                  <li key={d.step_index} className="rounded border border-zinc-100 p-2">
                    <div className="font-sans font-medium text-zinc-800">Step #{d.step_index}</div>
                    <div className="mt-1 break-all text-zinc-600">
                      pre: {d.pre.slice(0, 5).join(" → ") || "—"}
                    </div>
                    <div className="break-all text-zinc-600">
                      post: {d.post.slice(0, 5).join(" → ") || "—"}
                    </div>
                    <div className="text-zinc-500">positions_changed≈{d.moved}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <div className={`mt-6 grid gap-6 lg:grid-cols-3 ${tab !== "trace" ? "hidden" : ""}`}>
          <div className="rounded-xl border border-zinc-200 bg-white p-3 lg:col-span-2">
            <div className="h-[60vh]">
              <ReactFlow
                nodes={graph.nodes}
                edges={graph.edges}
                onNodeClick={(_, node) =>
                  setSelected((node.data as { step: AgentStep }).step)
                }
                fitView
              >
                <Background />
                <Controls />
              </ReactFlow>
            </div>
          </div>
          <div className="space-y-4">
            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <div className="text-sm font-semibold text-zinc-900">Step detail</div>
              {selected ? (
                <div className="mt-3 space-y-3 text-xs text-zinc-700">
                  <div className="font-mono">{selected.step_id}</div>
                  <div>
                    <span className="font-semibold">Type:</span> {selected.step_type}
                  </div>
                  {selected.name ? (
                    <div>
                      <span className="font-semibold">Name:</span> {selected.name}
                    </div>
                  ) : null}
                  <div>
                    <span className="font-semibold">Latency:</span> {selected.latency_ms ?? "-"} ms
                  </div>
                  {selected.error ? (
                    <div className="rounded bg-red-50 p-2 text-red-700">{selected.error}</div>
                  ) : null}
                  <details className="rounded border border-zinc-200 p-2">
                    <summary className="cursor-pointer font-semibold">Input</summary>
                    <pre className="mt-2 overflow-auto whitespace-pre-wrap">
                      {JSON.stringify(selected.input, null, 2)}
                    </pre>
                  </details>
                  <details className="rounded border border-zinc-200 p-2" open>
                    <summary className="cursor-pointer font-semibold">Output</summary>
                    <pre className="mt-2 overflow-auto whitespace-pre-wrap">
                      {JSON.stringify(selected.output, null, 2)}
                    </pre>
                  </details>
                </div>
              ) : (
                <div className="mt-2 text-sm text-zinc-600">Click a node to inspect.</div>
              )}
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <div className="text-sm font-semibold text-zinc-900">Evaluations</div>
              {evaluations.length === 0 ? (
                <p className="mt-2 text-xs text-zinc-600">No evaluation rows stored.</p>
              ) : (
                <ul className="mt-2 space-y-2 text-xs">
                  {evaluations.map((ev) => (
                    <li key={ev.eval_id} className="rounded border border-zinc-100 p-2">
                      <div className="font-medium">{ev.eval_type}</div>
                      <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-zinc-600">
                        {JSON.stringify(ev.metrics, null, 2)}
                      </pre>
                      {ev.error ? (
                        <div className="mt-1 text-red-600">{ev.error}</div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
