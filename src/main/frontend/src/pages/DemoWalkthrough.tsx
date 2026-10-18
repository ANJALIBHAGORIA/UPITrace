import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { MerchantCard, PhoneCard, PhoneSuccessState } from "../components/PhoneAndMerchantCards"
import { Button, ErrorState, LoadingState } from "../components/ui"
import { api } from "../lib/api"
import type { Incident } from "../lib/types"

// Ties the two "simulator" sides to ONE real incident (read-only replay of
// historical data), as opposed to /demo (LiveDemo) which is interactive and
// not yet tied to any incident.
export function DemoWalkthrough() {
  const { id } = useParams<{ id: string }>()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [peers, setPeers] = useState<Incident[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([api.getIncident(id), api.listIncidents()])
      .then(([inc, all]) => {
        setIncident(inc)
        setPeers(all.filter((i) => i.merchant_id === inc.merchant_id && i.incident_id !== inc.incident_id).slice(0, 3))
      })
      .catch((e) => setError(e.message))
  }, [id])

  if (error) return <ErrorState message={error} />
  if (!incident || !id) return <LoadingState />

  return (
    <div>
      <p className="mb-4 text-sm text-slate-500">
        Same payment, two perspectives — this is the actual problem before any investigation happens.
      </p>
      <div className="grid gap-6 md:grid-cols-2">
        <PhoneCard>
          <PhoneSuccessState
            amount={incident.amount} merchant={incident.merchant_id}
            utr={incident.transaction_ref ?? "—"} time={new Date(incident.created_at).toLocaleString()}
          />
        </PhoneCard>
        <MerchantCard
          merchant={incident.merchant_id}
          orderConfirmed={incident.reconciliation_status === "CONFIRMED"}
          rows={[
            { amount: incident.amount, paymentId: incident.transaction_ref ?? "—", statusLabel: incident.incident_status, highlight: true },
            ...peers.map((p) => ({ amount: p.amount, paymentId: p.transaction_ref ?? "—", statusLabel: p.incident_status })),
          ]}
        />
      </div>

      <div className="mt-6 text-center">
        <Link to={`/incidents/${id}`}>
          <Button>Investigate this payment in UPITrace →</Button>
        </Link>
      </div>
    </div>
  )
}
