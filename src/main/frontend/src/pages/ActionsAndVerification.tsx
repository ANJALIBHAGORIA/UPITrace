import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { IncidentSubNav } from "../components/IncidentSubNav"
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { ActionProposal, AuditRecord, ExecuteActionResult, VerifyActionResult } from "../lib/types"

export function ActionsAndVerification() {
  const { id } = useParams<{ id: string }>()
  const [proposal, setProposal] = useState<ActionProposal | null>(null)
  const [execution, setExecution] = useState<ExecuteActionResult | null>(null)
  const [verification, setVerification] = useState<VerifyActionResult | null>(null)
  const [audit, setAudit] = useState<AuditRecord[]>([])
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function loadAudit() {
    if (id) api.getAudit(id).then(setAudit).catch(() => {})
  }

  useEffect(loadAudit, [id])

  async function propose() {
    if (!id) return
    setBusy(true); setError(null)
    try {
      const p = await api.proposeAction(id)
      setProposal(p)
      setExecution(null)
      setVerification(null)
      loadAudit()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to propose action.")
    } finally {
      setBusy(false)
    }
  }

  async function execute() {
    if (!proposal) return
    setBusy(true); setError(null)
    try {
      const key = `ui-${proposal.action_id}-${Date.now()}`
      const result = await api.executeAction(proposal.action_id, "ui_user", key)
      setExecution(result)
      setConfirming(false)
      loadAudit()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Execution failed.")
    } finally {
      setBusy(false)
    }
  }

  async function verify() {
    if (!proposal) return
    setBusy(true); setError(null)
    try {
      const result = await api.verifyAction(proposal.action_id, proposal.action_type)
      setVerification(result)
      loadAudit()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification failed.")
    } finally {
      setBusy(false)
    }
  }

  if (!id) return <LoadingState />

  return (
    <div>
      <IncidentSubNav id={id} />
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <SectionTitle>Actions &amp; verification</SectionTitle>
          <Button onClick={propose} disabled={busy}>{proposal ? "Propose again" : "Propose action"}</Button>
        </div>

        {error && <ErrorState message={error} />}

        {!proposal && !error && <EmptyState message="No action proposed yet for this incident." />}

        {proposal && (
          <Card>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 dark:text-white">{proposal.action_type.replaceAll("_", " ")}</h3>
              <Badge value={proposal.status} />
            </div>
            <p className="mb-1 text-sm text-slate-700 dark:text-slate-300">{proposal.description}</p>
            <p className="mb-3 text-xs italic text-slate-500">{proposal.rationale}</p>
            <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
              <span className="font-semibold">Requires human approval:</span>
              <span>{proposal.requires_human_approval ? "Yes" : "No"}</span>
            </div>

            {!execution && (
              <div>
                {!confirming ? (
                  <Button onClick={() => setConfirming(true)} disabled={busy}>Request execution</Button>
                ) : (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/30">
                    <p className="mb-2 text-sm text-amber-800 dark:text-amber-300">
                      Confirm: execute <strong>{proposal.action_type.replaceAll("_", " ")}</strong> in
                      SIMULATED mode? No real payment action will occur.
                    </p>
                    <div className="flex gap-2">
                      <Button onClick={execute} disabled={busy} variant="primary">
                        {busy ? "Executing…" : "Confirm & execute (simulated)"}
                      </Button>
                      <Button onClick={() => setConfirming(false)} variant="secondary">Cancel</Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {execution && (
              <div className="space-y-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-semibold">Execution:</span>
                  <Badge value={execution.execution_status ?? "UNKNOWN"} />
                  <span className="text-xs text-slate-500">{execution.reason}</span>
                </div>
                {!verification ? (
                  <Button onClick={verify} disabled={busy}>{busy ? "Verifying…" : "Verify outcome"}</Button>
                ) : (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-semibold">Verification result:</span>
                    <Badge value={verification.result} />
                  </div>
                )}
              </div>
            )}
          </Card>
        )}

        <Card>
          <SectionTitle>Audit history</SectionTitle>
          {audit.length === 0 ? (
            <EmptyState message="No audit entries yet." />
          ) : (
            <ul className="space-y-2 text-sm">
              {audit.map((a) => (
                <li key={a.audit_record_id} className="flex items-center justify-between border-b border-slate-100 pb-2 dark:border-slate-800">
                  <div>
                    <p className="font-medium text-slate-800 dark:text-slate-200">{a.event_type.replaceAll("_", " ")}</p>
                    <p className="text-xs text-slate-500">{a.actor_id} · {new Date(a.timestamp).toLocaleString()}</p>
                  </div>
                  <span className="text-xs text-slate-500">{a.result}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
