import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { ActionProposal, AuditRecord, ExecuteActionResult, Incident, VerifyActionResult } from "../lib/types"

// Demo contact directory — NOT verified real support lines, clearly a
// placeholder pattern (standard Indian toll-free format + a support@
// address), same honesty standard as the rest of the app's SYNTHETIC data.
const MERCHANT_CONTACTS: Record<string, { phone: string; email: string }> = {
  IRCTC: { phone: "1800-111-139", email: "care@irctc.co.in" },
  BigBasket: { phone: "1860-123-1000", email: "support@bigbasket.com" },
  Zomato: { phone: "1800-120-0201", email: "support@zomato.com" },
  BookMyShow: { phone: "1860-121-2121", email: "support@bookmyshow.com" },
  Flipkart: { phone: "1800-208-9898", email: "support@flipkart.com" },
  Swiggy: { phone: "1800-208-6677", email: "support@swiggy.in" },
  Myntra: { phone: "1800-208-1800", email: "support@myntra.com" },
  Amazon: { phone: "1800-3000-9009", email: "support@amazon.in" },
  MakeMyTrip: { phone: "1800-102-2747", email: "support@makemytrip.com" },
  PharmEasy: { phone: "1800-121-4177", email: "support@pharmeasy.in" },
  Ola: { phone: "1860-121-2121", email: "support@olacabs.com" },
}
const BANK_CONTACT = { phone: "1800-120-1740", email: "" } // generic UPI/bank helpline placeholder

// General UPI dispute-resolution guidance — the same regardless of incident,
// like a runbook checklist. Not backend/AI-generated; shown for reference
// alongside the real (incident-specific) proposed action above it.
const ALTERNATIVE_ACTIONS = [
  { title: "Verify with bank / UPI provider", badge: "If issue persists", desc: "If still not confirmed after 4 hours, contact your bank with the transaction reference.", contact: "bank" as const },
  { title: "Raise a dispute", badge: "After 24 hours", desc: "Initiate a transaction dispute through your bank or UPI app.", contact: "bank" as const },
  { title: "Check for automatic reversal", badge: "Payment failed", desc: "If the transaction fails, the amount is usually reversed within 3-5 business days.", contact: null },
  { title: "Contact merchant support", badge: "If needed", desc: "Share the transaction details and request manual verification.", contact: "merchant" as const },
]

export function ActionsAndVerification() {
  const { id } = useParams<{ id: string }>()
  const [incident, setIncident] = useState<Incident | null>(null)
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

  // Auto-propose on load so the page isn't empty on first visit.
  useEffect(() => {
    if (!id) return
    api.getIncident(id).then(setIncident).catch(() => {})
    loadAudit()
    propose()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

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

  const merchantContact = incident ? MERCHANT_CONTACTS[incident.merchant_id] : undefined
  const emailSubject = incident ? encodeURIComponent(`Payment issue — ${incident.incident_id} (${incident.transaction_ref ?? ""})`) : ""
  const emailBody = incident
    ? encodeURIComponent(
        `Hi,\n\nI'm following up on a payment issue.\n\nIncident: ${incident.incident_id}\nAmount: ₹${incident.amount}\nTransaction ref: ${incident.transaction_ref ?? "N/A"}\nIssue: ${incident.complaint}\n\nPlease advise on the status.\n\nThanks.`,
      )
    : ""

  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>Recommended Actions</SectionTitle>
        <p className="-mt-3 text-sm text-slate-500">Clear, safe next steps with procedures</p>
      </div>

      {error && <ErrorState message={error} />}
      {!proposal && !error && <EmptyState message="Loading recommended action…" />}

      {proposal && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-5">
          <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-900">🛡️ Next Action (Recommended)</p>
          <div className="mb-4 flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-600 text-xs font-bold text-white">1</span>
            <div>
              <p className="font-semibold text-slate-900">{proposal.action_type.replaceAll("_", " ")}</p>
              <p className="text-sm text-slate-600">{proposal.description}</p>
              <p className="mt-1 text-xs italic text-slate-500">{proposal.rationale}</p>
            </div>
          </div>

          {!execution && !confirming && (
            <Button onClick={() => setConfirming(true)} disabled={busy}>Request execution</Button>
          )}
          {!execution && confirming && (
            <div className="rounded-lg border border-amber-400 bg-white p-3">
              <p className="mb-2 text-sm text-amber-800">
                Confirm: execute <strong>{proposal.action_type.replaceAll("_", " ")}</strong> in SIMULATED mode? No real payment action will occur.
              </p>
              <div className="flex gap-2">
                <Button onClick={execute} disabled={busy}>{busy ? "Executing…" : "Confirm & execute (simulated)"}</Button>
                <Button onClick={() => setConfirming(false)} variant="secondary">Cancel</Button>
              </div>
            </div>
          )}
          {execution && (
            <div className="space-y-3 border-t border-amber-200 pt-3">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-semibold text-slate-700">Execution:</span>
                <Badge value={execution.execution_status ?? "UNKNOWN"} />
                <span className="text-xs text-slate-500">{execution.reason}</span>
              </div>
              {!verification ? (
                <Button onClick={verify} disabled={busy}>{busy ? "Verifying…" : "Verify outcome"}</Button>
              ) : (
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-semibold text-slate-700">Verification result:</span>
                  <Badge value={verification.result} />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div>
        <h3 className="mb-3 font-semibold text-slate-900">Alternative Actions</h3>
        <div className="space-y-2">
          {ALTERNATIVE_ACTIONS.map((a, i) => {
            const contact = a.contact === "merchant" ? merchantContact : a.contact === "bank" ? BANK_CONTACT : undefined
            return (
              <div key={a.title} className="flex items-start gap-3 rounded-lg border border-slate-100 bg-white p-4">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600">{i + 2}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-slate-900">{a.title}</p>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">{a.badge}</span>
                  </div>
                  <p className="text-sm text-slate-500">{a.desc}</p>
                  {contact && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <a href={`tel:${contact.phone}`} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50">
                        📞 Call {a.contact === "merchant" ? incident?.merchant_id : "Bank"} ({contact.phone})
                      </a>
                      {contact.email && (
                        <a
                          href={`mailto:${contact.email}?subject=${emailSubject}&body=${emailBody}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
                        >
                          📧 Email {a.contact === "merchant" ? incident?.merchant_id : "Bank"} Support
                        </a>
                      )}
                    </div>
                  )}
                  {a.contact === "merchant" && !merchantContact && (
                    <p className="mt-1 text-xs text-slate-400">No contact on file for {incident?.merchant_id}.</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        <p className="mt-2 text-xs text-slate-400">Contact details shown are demo placeholders, not verified support lines.</p>
      </div>

      <Card>
        <SectionTitle>Audit history</SectionTitle>
        {audit.length === 0 ? (
          <EmptyState message="No audit entries yet." />
        ) : (
          <ul className="space-y-2 text-sm">
            {audit.map((a) => (
              <li key={a.audit_record_id} className="flex items-center justify-between border-b border-slate-100 pb-2">
                <div>
                  <p className="font-medium text-slate-800">{a.event_type.replaceAll("_", " ")}</p>
                  <p className="text-xs text-slate-500">{a.actor_id} · {new Date(a.timestamp).toLocaleString()}</p>
                </div>
                <span className="text-xs text-slate-500">{a.result}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
