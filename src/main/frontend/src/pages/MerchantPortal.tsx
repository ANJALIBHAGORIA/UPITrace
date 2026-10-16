import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Badge, Card, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { Incident } from "../lib/types"

// No dedicated /merchant-orders endpoint exists — grouped view over
// /incidents by merchant_id, which is what the merchant portal's "orders
// affected by payment issues" list would actually show in this prototype.
export function MerchantPortal() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [merchant, setMerchant] = useState<string | "ALL">("ALL")

  useEffect(() => {
    api.listIncidents().then(setIncidents).catch((e) => setError(e.message))
  }, [])

  const merchants = useMemo(
    () => (incidents ? Array.from(new Set(incidents.map((i) => i.merchant_id))) : []),
    [incidents],
  )
  const filtered = useMemo(
    () => (incidents ?? []).filter((i) => merchant === "ALL" || i.merchant_id === merchant),
    [incidents, merchant],
  )

  if (error) return <ErrorState message={error} />
  if (!incidents) return <LoadingState />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <SectionTitle>Merchant operations portal</SectionTitle>
        <select className="input w-auto" value={merchant} onChange={(e) => setMerchant(e.target.value)}>
          <option value="ALL">All merchants</option>
          {merchants.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>
      <Card className="divide-y divide-slate-100 p-0 dark:divide-slate-800">
        {filtered.map((inc) => (
          <div key={inc.incident_id} className="flex items-center justify-between gap-4 px-5 py-4">
            <div>
              <p className="font-medium text-slate-900 dark:text-white">{inc.merchant_id} — ₹{inc.amount}</p>
              <p className="text-xs text-slate-500">{inc.transaction_ref ?? "no transaction ref"}</p>
            </div>
            <div className="flex items-center gap-3">
              <Badge value={inc.reconciliation_status ?? "NOT_YET_RECONCILED"} />
              <Link to={`/incidents/${inc.incident_id}`} className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                View incident
              </Link>
            </div>
          </div>
        ))}
      </Card>
    </div>
  )
}
