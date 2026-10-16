import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Badge, Card, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { Incident } from "../lib/types"

// There's no dedicated /payment-attempts endpoint in the API — this view
// renders the payment-receipt side of each incident using the fields
// Incident already carries (transaction_ref, amount, merchant_id, status).
export function CustomerSimulator() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listIncidents().then(setIncidents).catch((e) => setError(e.message))
  }, [])

  if (error) return <ErrorState message={error} />
  if (!incidents) return <LoadingState />

  return (
    <div className="space-y-4">
      <SectionTitle>Customer UPI app — simulated receipts</SectionTitle>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {incidents.map((inc) => (
          <Card key={inc.incident_id} className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">UPI Payment</span>
              <Badge value={inc.incident_status} />
            </div>
            <p className="text-lg font-semibold text-slate-900 dark:text-white">₹{inc.amount}</p>
            <p className="text-sm text-slate-600 dark:text-slate-300">Paid to {inc.merchant_id}</p>
            {inc.transaction_ref && (
              <p className="font-mono text-xs text-slate-400">UTR: {inc.transaction_ref}</p>
            )}
            <p className="text-xs text-slate-400">{new Date(inc.created_at).toLocaleString()}</p>
            <Link
              to={`/incidents/${inc.incident_id}`}
              className="inline-block text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Investigate this payment →
            </Link>
          </Card>
        ))}
      </div>
    </div>
  )
}
