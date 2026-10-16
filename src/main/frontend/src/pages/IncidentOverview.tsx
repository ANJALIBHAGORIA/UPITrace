import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { IncidentSubNav } from "../components/IncidentSubNav"
import { Badge, Button, Card, ErrorState, List, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { Incident, ReconciliationResult } from "../lib/types"

export function IncidentOverview() {
  const { id } = useParams<{ id: string }>()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [reconciliation, setReconciliation] = useState<ReconciliationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  function load() {
    if (!id) return
    api.getIncident(id).then(setIncident).catch((e) => setError(e.message))
  }

  useEffect(load, [id])

  async function runReconciliation() {
    if (!id) return
    setRunning(true)
    setError(null)
    try {
      const result = await api.reconcile(id)
      setReconciliation(result)
      load() // refresh incident.reconciliation_status
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reconciliation failed.")
    } finally {
      setRunning(false)
    }
  }

  if (error) return <ErrorState message={error} />
  if (!incident || !id) return <LoadingState />

  return (
    <div>
      <IncidentSubNav id={id} />
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">{incident.title}</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {incident.incident_id} · {incident.merchant_id} · ₹{incident.amount} {incident.currency}
            </p>
          </div>
          <div className="flex gap-2">
            <Badge value={incident.incident_status} />
            {incident.reconciliation_status && <Badge value={incident.reconciliation_status} />}
          </div>
        </div>

        <Card>
          <SectionTitle>Complaint</SectionTitle>
          <p className="text-sm text-slate-700 dark:text-slate-300">{incident.complaint}</p>
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <SectionTitle>Deterministic reconciliation</SectionTitle>
            <Button onClick={runReconciliation} disabled={running}>
              {running ? "Running…" : "Run reconciliation"}
            </Button>
          </div>
          {!reconciliation && !incident.reconciliation_status && (
            <p className="text-sm italic text-slate-400">Not yet reconciled. Click "Run reconciliation".</p>
          )}
          {reconciliation && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1 text-xs font-semibold text-slate-500">Confirmed facts</p>
                <List items={reconciliation.confirmed_facts} />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold text-slate-500">Conflicts</p>
                <List items={reconciliation.conflicts} />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold text-slate-500">Missing evidence</p>
                <List items={reconciliation.missing_evidence} />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold text-slate-500">Recommended next step</p>
                <List items={reconciliation.permitted_checks} />
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
