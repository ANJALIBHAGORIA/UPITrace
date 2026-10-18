import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Badge, Card, ErrorState, LoadingState } from "../components/ui"
import { api } from "../lib/api"
import type { Incident } from "../lib/types"

export function IncidentList() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listIncidents()
      .then((data) => setIncidents([...data].sort((a, b) => b.created_at.localeCompare(a.created_at))))
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <ErrorState message={error} />
  if (!incidents) return <LoadingState />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Incidents</h1>
        <Link to="/incidents/new" className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400">
          + New incident
        </Link>
      </div>
      <Card className="divide-y divide-slate-100 p-0 dark:divide-slate-800">
        {incidents.map((inc) => (
          <Link
            key={inc.incident_id}
            to={`/incidents/${inc.incident_id}`}
            className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
          >
            <div>
              <p className="font-medium text-slate-900 dark:text-white">{inc.title}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {inc.incident_id} · {inc.merchant_id} · ₹{inc.amount} · {new Date(inc.created_at).toLocaleString()}
              </p>
            </div>
            <div className="flex gap-2">
              <Badge value={inc.incident_status} />
              {inc.reconciliation_status && <Badge value={inc.reconciliation_status} />}
            </div>
          </Link>
        ))}
      </Card>
    </div>
  )
}
