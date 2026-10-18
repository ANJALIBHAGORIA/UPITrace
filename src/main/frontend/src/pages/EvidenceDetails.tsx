import { useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { EvidenceRecord } from "../lib/types"

const CATEGORIES = ["UPI App", "Bank", "Gateway", "Merchant"] as const

function categorize(sourceSystem: string): (typeof CATEGORIES)[number] {
  const s = sourceSystem.toLowerCase()
  if (s.includes("bank")) return "Bank"
  if (s.includes("gateway") || s.includes("upi") || s.includes("npci")) return "Gateway"
  if (s.includes("platform") || s.includes("portal") || s.includes("merchant") || s.includes("support")) return "Merchant"
  return "UPI App"
}

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  VERIFIED: { label: "Confirmed", cls: "bg-emerald-100 text-emerald-700" },
  UNVERIFIED: { label: "Unverified", cls: "bg-slate-100 text-slate-600" },
  CONFLICTED: { label: "Conflicted", cls: "bg-rose-100 text-rose-700" },
  NOT_APPLICABLE: { label: "N/A", cls: "bg-slate-100 text-slate-500" },
}

export function EvidenceDetails() {
  const { id } = useParams<{ id: string }>()
  const [evidence, setEvidence] = useState<EvidenceRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<string>("ALL")
  const [selected, setSelected] = useState<EvidenceRecord | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!id) return
    api.getEvidence(id).then((data) => {
      setEvidence(data)
      setSelected(data[0] ?? null)
    }).catch((e) => setError(e.message))
  }, [id])

  const counts = useMemo(() => {
    const c: Record<string, number> = { "UPI App": 0, Bank: 0, Gateway: 0, Merchant: 0 }
    for (const e of evidence ?? []) c[categorize(e.source_system)]++
    return c
  }, [evidence])

  const filtered = useMemo(
    () => (evidence ?? []).filter((e) => activeTab === "ALL" || categorize(e.source_system) === activeTab),
    [evidence, activeTab],
  )

  function copyJson() {
    navigator.clipboard?.writeText(JSON.stringify(selected, null, 2)).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  if (error) return <ErrorState message={error} />
  if (!evidence || !id) return <LoadingState />

  const status = selected ? (STATUS_LABEL[selected.verification_status] ?? { label: selected.verification_status, cls: "bg-slate-100 text-slate-600" }) : null

  return (
    <div>
      <SectionTitle>Evidence details</SectionTitle>
      <p className="-mt-3 mb-4 text-sm text-slate-500">Detailed record from each source system</p>

      <div className="mb-4 flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setActiveTab(c)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium ${
              activeTab === c ? "border-indigo-400 bg-indigo-50 text-indigo-700" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {c} ({counts[c] ?? 0})
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
                onClick={() => setSelected(e)}
                className={`block w-full rounded-lg border p-3 text-left text-sm ${
                  selected?.evidence_id === e.evidence_id ? "border-indigo-400 bg-indigo-50" : "border-slate-200 bg-white hover:border-indigo-300"
                }`}
              >
                <p className="font-mono text-xs text-slate-400">{e.evidence_id}</p>
                <p className="font-medium text-slate-900">{e.title}</p>
              </button>
            ))}
          </div>

          {selected && status && (
            <div className="space-y-4 md:col-span-2">
              <Card>
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 font-semibold text-slate-900">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100">📋</span>
                    {selected.title}
                  </h3>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.cls}`}>{status.label}</span>
                </div>
                <dl className="grid grid-cols-2 gap-y-2 text-sm">
                  <Row label="Source" value={selected.source_system.replaceAll("_", " ")} />
                  <Row label="Evidence type" value={selected.evidence_type.replaceAll("_", " ")} />
                  <Row label="Details" value={selected.content} full />
                  <Row label="Timestamp" value={new Date(selected.ingested_at).toLocaleString()} />
                  <Row label="Source mode" value={selected.source_mode} />
                </dl>
              </Card>

              <Card>
                <div className="mb-2 flex items-center justify-between">
                  <SectionTitle>Raw Response (JSON)</SectionTitle>
                  <button onClick={copyJson} className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50">
                    📋 {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
                <pre className="overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                  {JSON.stringify(selected, null, 2)}
                </pre>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Row({ label, value, full }: { label: string; value: string; full?: boolean }) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <dt className="text-xs font-medium text-slate-400">{label}</dt>
      <dd className="text-slate-800">{value}</dd>
    </div>
  )
}
