import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { IncidentSubNav } from "../components/IncidentSubNav"
import { Badge, Button, Card, EmptyState, ErrorState, List, LoadingState, SectionTitle } from "../components/ui"
import { ApiError, api } from "../lib/api"
import type { InvestigationReport } from "../lib/types"

export function Investigation() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<InvestigationReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api.getInvestigation(id)
      .then(setReport)
      .catch((e) => { if (!(e instanceof ApiError && e.status === 404)) setError(e.message) })
      .finally(() => setLoading(false))
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
      <IncidentSubNav id={id} />
      <div className="mb-4 flex items-center justify-between">
        <SectionTitle>AI investigation</SectionTitle>
        <Button onClick={runInvestigation} disabled={running}>
          {running ? "Investigating…" : report ? "Re-run investigation" : "Run investigation"}
        </Button>
      </div>

      {error && <ErrorState message={error} />}

      {!report && !error && (
        <EmptyState message="No investigation has been run yet for this incident." />
      )}

      {report && (
        <div className="space-y-6">
          <ProvenanceBanner report={report} />

          <Card>
            <SectionTitle>Summary</SectionTitle>
            <p className="text-sm text-slate-800 dark:text-slate-200">{report.summary}</p>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <SectionTitle>Competing hypotheses</SectionTitle>
              <List items={report.competing_hypotheses} />
            </Card>
            <Card>
              <SectionTitle>Missing evidence</SectionTitle>
              <List items={report.missing_evidence} />
            </Card>
            <Card>
              <SectionTitle>Supporting evidence</SectionTitle>
              <EvidenceCitations ids={report.supporting_evidence} incidentId={report.incident_id} />
            </Card>
            <Card>
              <SectionTitle>Contradicting evidence</SectionTitle>
              <EvidenceCitations ids={report.contradicting_evidence} incidentId={report.incident_id} />
            </Card>
          </div>

          <Card>
            <SectionTitle>Reasoning</SectionTitle>
            <p className="mb-3 text-sm text-slate-700 dark:text-slate-300">{report.reasoning}</p>
            <p className="text-xs font-semibold text-slate-500">Uncertainty</p>
            <p className="text-sm text-slate-700 dark:text-slate-300">{report.uncertainty_explanation}</p>
          </Card>

          <Card>
            <div className="mb-2 flex items-center justify-between">
              <SectionTitle>Recommended next action</SectionTitle>
              {report.unresolved_status && <Badge value="UNRESOLVED" />}
            </div>
            <p className="text-sm font-medium text-slate-900 dark:text-white">
              {report.recommended_next_action.replaceAll("_", " ")}
            </p>
            {report.policy_override_applied && (
              <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                ⚠ The provider's original suggestion was overridden by policy — it was not one
                of the deterministic rules engine's permitted actions.
              </p>
            )}
          </Card>

          {report.unsupported_claims_removed.length > 0 && (
            <Card className="border-rose-200 dark:border-rose-900">
              <SectionTitle>Rejected citations</SectionTitle>
              <p className="mb-2 text-xs text-slate-500">
                The AI cited the following evidence IDs, but they don't exist in this
                incident's actual evidence — they were stripped, not trusted.
              </p>
              <List items={report.unsupported_claims_removed} />
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

function ProvenanceBanner({ report }: { report: InvestigationReport }) {
  if (report.source_mode === "UNAVAILABLE") {
    return (
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
        <strong>AI unavailable.</strong> This is the deterministic reconciliation-based
        fallback, not a Gemini-generated answer (model: {report.model_identifier}).
      </div>
    )
  }
  if (report.source_mode === "SIMULATED") {
    return (
      <div className="rounded-lg border border-sky-300 bg-sky-50 p-3 text-sm text-sky-800 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
        Generated by a <strong>simulated</strong> provider ({report.model_identifier}) for
        testing/demo — not a live Gemini call.
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
      Generated by <strong>Vertex AI Gemini</strong> ({report.model_identifier}).
    </div>
  )
}

function EvidenceCitations({ ids, incidentId }: { ids: string[]; incidentId: string }) {
  if (ids.length === 0) return <EmptyState message="None" />
  return (
    <ul className="flex flex-wrap gap-1">
      {ids.map((cid) => (
        <li key={cid}>
          <Link
            to={`/incidents/${incidentId}/evidence#evidence-${cid}`}
            className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700 hover:bg-indigo-100 dark:bg-slate-800 dark:text-slate-300"
          >
            {cid}
          </Link>
        </li>
      ))}
    </ul>
  )
}
