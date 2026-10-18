import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Button, Card, EmptyState, ErrorState, List, LoadingState, SectionTitle } from "../components/ui"
import { ApiError, api } from "../lib/api"
import type { InvestigationReport } from "../lib/types"

const TABS = ["Summary", "Possible Causes", "Evidence Support", "Next Steps"] as const
type Tab = (typeof TABS)[number]

export function Investigation() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<InvestigationReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>("Summary")

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.getInvestigation(id)
      .then(setReport)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          // No investigation exists for this incident yet — generate one now,
          // same as Overview auto-reconciles and Actions auto-proposes, so
          // landing on this tab never dead-ends on an empty "Run investigation"
          // screen.
          return runInvestigation()
        }
        setError(e.message)
      })
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  async function runInvestigation() {
    if (!id) return
    setRunning(true)
    setError(null)
    try {
      setReport(await api.investigate(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Investigation failed.")
    } finally {
      setRunning(false)
    }
  }

  if (loading || !id) return <LoadingState />

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <div>
          <SectionTitle>AI Analysis (Gemini)</SectionTitle>
          <p className="-mt-3 text-sm text-slate-500">Structured explanation with citations</p>
        </div>
        <div className="flex items-center gap-2">
          {report && <ProvenancePill report={report} />}
          <Button onClick={runInvestigation} disabled={running}>
            {running ? "Investigating…" : report ? "Re-run" : "Run investigation"}
          </Button>
        </div>
      </div>

      {error && <ErrorState message={error} />}
      {!report && !error && <EmptyState message="No investigation has been run yet for this incident." />}

      {report && (
        <div className="mt-4">
          <div className="mb-4 flex gap-1 rounded-lg bg-slate-100 p-1">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  tab === t ? "bg-indigo-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === "Summary" && (
            <div className="space-y-4">
              <Card>
                <SectionTitle>Summary</SectionTitle>
                <p className="text-sm text-slate-800">{report.summary}</p>
              </Card>
              <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
                <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-900">⚠️ Uncertainty Factors</p>
                <ul className="list-inside list-disc space-y-1 text-sm text-amber-800">
                  {report.uncertainty_explanation.split(";").map((part, i) => part.trim() && <li key={i}>{part.trim()}</li>)}
                </ul>
              </div>
              <Card>
                <SectionTitle>Cited Evidence</SectionTitle>
                <div className="flex items-center justify-between">
                  <EvidenceCitations ids={report.citation_ids} incidentId={report.incident_id} />
                  <Link to={`/incidents/${report.incident_id}/evidence`} className="shrink-0 text-sm font-medium text-indigo-600 hover:underline">
                    View Details →
                  </Link>
                </div>
              </Card>
            </div>
          )}

          {tab === "Possible Causes" && (
            <Card>
              <SectionTitle>Competing hypotheses</SectionTitle>
              <List items={report.competing_hypotheses} />
            </Card>
          )}

          {tab === "Evidence Support" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Card>
                <SectionTitle>Supporting evidence</SectionTitle>
                <EvidenceCitations ids={report.supporting_evidence} incidentId={report.incident_id} />
              </Card>
              <Card>
                <SectionTitle>Contradicting evidence</SectionTitle>
                <EvidenceCitations ids={report.contradicting_evidence} incidentId={report.incident_id} />
              </Card>
              <Card className="sm:col-span-2">
                <SectionTitle>Missing evidence</SectionTitle>
                <List items={report.missing_evidence} />
              </Card>
            </div>
          )}

          {tab === "Next Steps" && (
            <div className="space-y-4">
              <Card>
                <SectionTitle>Reasoning</SectionTitle>
                <p className="text-sm text-slate-700">{report.reasoning}</p>
              </Card>
              <Card>
                <SectionTitle>Recommended next action</SectionTitle>
                <p className="text-sm font-medium text-slate-900">{report.recommended_next_action.replaceAll("_", " ")}</p>
                {report.policy_override_applied && (
                  <p className="mt-2 text-xs text-amber-600">
                    ⚠ The provider's original suggestion was overridden by policy — it was not one of the rules engine's permitted actions.
                  </p>
                )}
              </Card>
              {report.unsupported_claims_removed.length > 0 && (
                <Card className="border-rose-200">
                  <SectionTitle>Rejected citations</SectionTitle>
                  <p className="mb-2 text-xs text-slate-500">The AI cited evidence IDs that don't exist — stripped, not trusted.</p>
                  <List items={report.unsupported_claims_removed} />
                </Card>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ProvenancePill({ report }: { report: InvestigationReport }) {
  const style = report.source_mode === "LIVE"
    ? "bg-sky-100 text-sky-700"
    : report.source_mode === "SIMULATED"
      ? "bg-slate-100 text-slate-600"
      : "bg-amber-100 text-amber-700"
  const text = report.source_mode === "LIVE"
    ? "Generated by Gemini (Vertex AI)"
    : report.source_mode === "SIMULATED"
      ? `Simulated (${report.model_identifier})`
      : "AI unavailable — deterministic fallback"
  return <span className={`rounded-full px-3 py-1 text-xs font-medium ${style}`}>{text}</span>
}

function EvidenceCitations({ ids, incidentId }: { ids: string[]; incidentId: string }) {
  if (ids.length === 0) return <EmptyState message="None" />
  return (
    <div className="flex flex-wrap gap-1.5">
      {ids.map((cid) => (
        <Link
          key={cid}
          to={`/incidents/${incidentId}/evidence#evidence-${cid}`}
          className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
        >
          {cid}
        </Link>
      ))}
    </div>
  )
}
