import { useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { IncidentSubNav } from "../components/IncidentSubNav"
import { Badge, Card, EmptyState, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { EvidenceRecord } from "../lib/types"

export function EvidenceDetails() {
  const { id } = useParams<{ id: string }>()
  const [evidence, setEvidence] = useState<EvidenceRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<string>("ALL")
  const [selected, setSelected] = useState<EvidenceRecord | null>(null)
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    if (!id) return
    api.getEvidence(id).then((data) => {
      setEvidence(data)
      setSelected(data[0] ?? null)
    }).catch((e) => setError(e.message))
  }, [id])

  const sourceSystems = useMemo(
    () => (evidence ? Array.from(new Set(evidence.map((e) => e.source_system))) : []),
    [evidence],
  )
  const filtered = useMemo(
    () => (evidence ?? []).filter((e) => activeTab === "ALL" || e.source_system === activeTab),
    [evidence, activeTab],
  )

  if (error) return <ErrorState message={error} />
  if (!evidence || !id) return <LoadingState />

  return (
    <div>
      <IncidentSubNav id={id} />
      <SectionTitle>Evidence details</SectionTitle>

      <div className="mb-4 flex flex-wrap gap-2">
        {["ALL", ...sourceSystems].map((s) => (
          <button
            key={s}
            onClick={() => setActiveTab(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              activeTab === s
                ? "bg-indigo-600 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
            }`}
          >
            {s === "ALL" ? `All (${evidence.length})` : s}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState message="No evidence from this source." />
      ) : (
        <div className="grid gap-6 md:grid-cols-3">
          <div className="space-y-2 md:col-span-1">
            {filtered.map((e) => (
              <button
                key={e.evidence_id}
                id={`evidence-${e.evidence_id}`}
                onClick={() => { setSelected(e); setShowRaw(false) }}
                className={`block w-full rounded-lg border p-3 text-left text-sm ${
                  selected?.evidence_id === e.evidence_id
                    ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/30"
                    : "border-slate-200 bg-white hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-900"
                }`}
              >
                <p className="font-mono text-xs text-slate-400">{e.evidence_id}</p>
                <p className="font-medium text-slate-900 dark:text-white">{e.title}</p>
              </button>
            ))}
          </div>

          <Card className="md:col-span-2">
            {!selected ? (
              <EmptyState message="Select an evidence record." />
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-slate-900 dark:text-white">{selected.title}</h3>
                  <Badge value={selected.verification_status} />
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-300">{selected.content}</p>
                <dl className="grid grid-cols-2 gap-2 text-xs">
                  <dt className="font-semibold text-slate-500">Source system</dt>
                  <dd className="text-slate-700 dark:text-slate-300">{selected.source_system}</dd>
                  <dt className="font-semibold text-slate-500">Evidence type</dt>
                  <dd className="text-slate-700 dark:text-slate-300">{selected.evidence_type}</dd>
                  <dt className="font-semibold text-slate-500">Source mode</dt>
                  <dd><Badge value={selected.source_mode} /></dd>
                  <dt className="font-semibold text-slate-500">Ingested at</dt>
                  <dd className="text-slate-700 dark:text-slate-300">{new Date(selected.ingested_at).toLocaleString()}</dd>
                </dl>
                <button
                  onClick={() => setShowRaw((v) => !v)}
                  className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                >
                  {showRaw ? "Hide raw JSON" : "Show raw JSON"}
                </button>
                {showRaw && (
                  <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                    {JSON.stringify(selected, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
