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

  // Basic vertical layout by step_index (MVP)
  const sorted = [...steps].sort((a, b) => a.step_index - b.step_index);
  const idxById = new Map(sorted.map((s, i) => [s.step_id, i]));
  for (const n of nodes) {
    const i = idxById.get(n.id) ?? 0;
    const step = (n.data as any).step as AgentStep;
    const x = step.step_type === "retrieval" ? 40 : step.step_type === "evaluation" ? 340 : 180;
    n.position = { x, y: i * 90 };
  }

  return { nodes, edges };
}

export default function TraceRunPage({ params }: { params: { runId: string } }) {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [run, setRun] = useState<any>(null);
  const [selected, setSelected] = useState<AgentStep | null>(null);

  useEffect(() => {
    void (async () => {
      const res = await fetch(`http://localhost:8000/api/traces/${params.runId}`);
      if (!res.ok) return;
      const data = (await res.json()) as { run: any; steps: AgentStep[] };
      setRun(data.run);
      setSteps(data.steps ?? []);
    })();
  }, [params.runId]);

  const graph = useMemo(() => buildGraph(steps), [steps]);

  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-950">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-zinc-600">Trace run</div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {params.runId.slice(0, 8)}…{" "}
              <span className="ml-2 text-sm font-medium text-zinc-600">{run?.route_label}</span>
            </h1>
          </div>
          <a className="text-sm font-medium text-zinc-700 hover:text-zinc-950" href="/traces">
            Back
          </a>
        </header>

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="rounded-xl border border-zinc-200 bg-white p-3 lg:col-span-2">
            <div className="h-[70vh]">
              <ReactFlow
                nodes={graph.nodes}
                edges={graph.edges}
                onNodeClick={(_, node) => setSelected((node.data as any).step as AgentStep)}
                fitView
              >
                <Background />
                <Controls />
              </ReactFlow>
            </div>
          </div>
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
        </div>
      </div>
    </div>
  );
}

