import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Button, Card, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { Incident, ReconciliationResult } from "../lib/types"

const STATUS_BANNER: Record<string, { icon: string; label: string; box: string; title: string; text: (r: ReconciliationResult) => string }> = {
  CONFIRMED: { icon: "✅", label: "Confirmed", box: "border-emerald-300 bg-emerald-50", title: "text-emerald-900", text: () => "Payment and merchant order both confirmed. No open questions." },
  PENDING: { icon: "⏳", label: "Pending", box: "border-amber-300 bg-amber-50", title: "text-amber-900", text: () => "Payment is still pending at the provider. No conclusion is possible yet." },
  STATUS_MISMATCH: { icon: "⚠️", label: "Status Mismatch", box: "border-rose-300 bg-rose-50", title: "text-rose-900", text: () => "Two or more sources disagree about the outcome of this payment." },
  MERCHANT_CONFIRMATION_MISSING: { icon: "🏧", label: "Unresolved", box: "border-amber-300 bg-amber-50", title: "text-amber-900", text: () => "Payment debited from payer account, but merchant order not confirmed. Final outcome is unverified." },
  INSUFFICIENT_EVIDENCE: { icon: "❓", label: "Insufficient Evidence", box: "border-slate-300 bg-slate-50", title: "text-slate-900", text: () => "Available records do not contain enough information to reach a conclusion." },
  POSSIBLE_DUPLICATE: { icon: "🔁", label: "Possible Duplicate", box: "border-fuchsia-300 bg-fuchsia-50", title: "text-fuchsia-900", text: () => "More than one record could represent the same underlying payment." },
  REVERSAL_UNVERIFIED: { icon: "↩️", label: "Reversal Unverified", box: "border-amber-300 bg-amber-50", title: "text-amber-900", text: () => "A refund/reversal is expected, but there is no confirmation it has happened." },
  UNRESOLVED: { icon: "❓", label: "Unresolved", box: "border-slate-300 bg-slate-50", title: "text-slate-900", text: () => "No deterministic rule matched this evidence combination; needs manual review." },
}

export function IncidentOverview() {
  const { id } = useParams<{ id: string }>()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [reconciliation, setReconciliation] = useState<ReconciliationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [copied, setCopied] = useState(false)

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
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reconciliation failed.")
    } finally {
      setRunning(false)
    }
  }

  // Auto-run whenever this page mounts without a result in local state —
  // not just on an incident's very first visit. Switching tabs unmounts this
  // component (resetting `reconciliation` to null) even though the incident
  // itself may already carry a reconciliation_status from a prior visit;
  // gating on that status left the page stuck on "Running reconciliation…"
  // forever after a tab switch. Reconciliation is cheap/deterministic, so
  // re-running it on every mount is safe.
  useEffect(() => {
    if (incident && !reconciliation) runReconciliation()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident])

  function share() {
    navigator.clipboard?.writeText(window.location.href).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  if (error) return <ErrorState message={error} />
  if (!incident || !id) return <LoadingState />

  const banner = reconciliation ? STATUS_BANNER[reconciliation.classification] : undefined
  const findings = reconciliation ? [
    ...reconciliation.confirmed_facts.map((f) => ({ label: f, tag: "Confirmed", tagClass: "bg-emerald-100 text-emerald-800", circle: "bg-emerald-500" })),
    ...reconciliation.missing_evidence.map((f) => ({ label: f, tag: "Missing", tagClass: "bg-rose-100 text-rose-800", circle: "bg-amber-500" })),
    ...reconciliation.conflicts.map((f) => ({ label: f, tag: "Conflict", tagClass: "bg-amber-100 text-amber-800", circle: "bg-amber-500" })),
  ] : []

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Incident: {incident.incident_id}</h1>
          <p className="text-sm text-slate-500">Created {new Date(incident.created_at).toLocaleString()}</p>
        </div>
        <button onClick={share} className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
          🔗 {copied ? "Copied!" : "Share"}
        </button>
      </div>

      {banner && (
        <div className={`flex items-start gap-3 rounded-xl border p-4 ${banner.box}`}>
          <span className="text-xl">{banner.icon}</span>
          <div>
            <p className={`font-semibold ${banner.title}`}>{banner.label}</p>
            <p className="text-sm text-slate-600">{banner.text(reconciliation!)}</p>
          </div>
        </div>
      )}

      <Card>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Field label="Amount" value={`₹${incident.amount}`} />
          <Field label="Date & Time" value={new Date(incident.created_at).toLocaleString()} />
          <Field label="Merchant" value={incident.merchant_id} />
          <Field label="Payment Method" value="UPI" />
        </div>
      </Card>

      <Card>
        <SectionTitle>Complaint</SectionTitle>
        <p className="text-sm text-slate-700">{incident.complaint}</p>
      </Card>

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle>Key findings</SectionTitle>
          <Button onClick={runReconciliation} disabled={running} variant="secondary">
            {running ? "Running…" : "Re-run reconciliation"}
          </Button>
        </div>
        {!reconciliation ? (
          <p className="text-sm italic text-slate-400">Running reconciliation…</p>
        ) : (
          <div className="space-y-4">
            <ul className="space-y-2">
              {findings.length === 0 && (
                <Finding n={1} label="No findings beyond the classification itself" tag="Unverified" tagClass="bg-slate-200 text-slate-700" circle="bg-slate-400" />
              )}
              {findings.map((f, i) => <Finding key={i} n={i + 1} {...f} />)}
            </ul>

            {reconciliation.permitted_checks.length > 0 && (
              <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
                <p className="mb-1 flex items-center gap-2 text-sm font-semibold text-amber-900">🛡️ Recommended Next Action</p>
                <p className="mb-3 text-sm text-amber-800">{reconciliation.permitted_checks[0].replaceAll("_", " ")}</p>
                <Link to={`/incidents/${id}/investigation`}>
                  <Button>View Detailed Analysis →</Button>
                </Link>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-400">{label}</p>
      <p className="font-semibold text-slate-800">{value}</p>
    </div>
  )
}

function Finding({ n, label, tag, tagClass, circle }: { n: number; label: string; tag: string; tagClass: string; circle: string }) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2.5">
      <div className="flex items-center gap-3">
        <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${circle}`}>{n}</span>
        <span className="text-sm text-slate-700">{label.replaceAll("_", " ")}</span>
      </div>
      <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${tagClass}`}>{tag}</span>
    </li>
  )
}
