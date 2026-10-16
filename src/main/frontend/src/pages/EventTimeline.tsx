import { useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { IncidentSubNav } from "../components/IncidentSubNav"
import { Badge, Card, EmptyState, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { SourceEvent } from "../lib/types"

export function EventTimeline() {
  const { id } = useParams<{ id: string }>()
  const [events, setEvents] = useState<SourceEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sourceFilter, setSourceFilter] = useState<string | "ALL">("ALL")
  const [selected, setSelected] = useState<SourceEvent | null>(null)

  useEffect(() => {
    if (!id) return
    api.getEvents(id).then((data) => {
      setEvents([...data].sort((a, b) => a.event_time.localeCompare(b.event_time)))
    }).catch((e) => setError(e.message))
  }, [id])

  const sources = useMemo(
    () => (events ? Array.from(new Set(events.map((e) => e.source_system))) : []),
    [events],
  )
  const filtered = useMemo(
    () => (events ?? []).filter((e) => sourceFilter === "ALL" || e.source_system === sourceFilter),
    [events, sourceFilter],
  )

  if (error) return <ErrorState message={error} />
  if (!events || !id) return <LoadingState />

  return (
    <div>
      <IncidentSubNav id={id} />
      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <SectionTitle>Cross-platform event timeline</SectionTitle>
            <select
              className="input w-auto"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="ALL">All sources</option>
              {sources.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {filtered.length === 0 ? (
            <EmptyState message="No events recorded for this incident — that is itself a finding, not just empty data." />
          ) : (
            <ol className="relative space-y-4 border-l border-slate-200 pl-6 dark:border-slate-800">
              {filtered.map((e) => (
                <li key={e.event_id}>
                  <button
                    onClick={() => setSelected(e)}
                    className={`block w-full rounded-lg border p-3 text-left text-sm ${
                      selected?.event_id === e.event_id
                        ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/30"
                        : "border-slate-200 bg-white hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-900"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-900 dark:text-white">{e.event_type}</span>
                      <Badge value={e.verification_status} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {e.source_system} · event: {new Date(e.event_time).toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      ingested: {new Date(e.ingested_at).toLocaleString()}
                    </p>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </div>

        <Card>
          <SectionTitle>Event detail</SectionTitle>
          {!selected ? (
            <EmptyState message="Select an event to inspect its raw record." />
          ) : (
            <div className="space-y-2 text-sm">
              <Row label="Event ID" value={selected.event_id} />
              <Row label="Source status" value={selected.source_status} />
              <Row label="Normalized status" value={selected.normalized_status} />
              <Row
                label="Note"
                value={
                  selected.normalized_status === "NOT_FOUND"
                    ? "Absence of a record — NOT proof the underlying transaction failed."
                    : "—"
                }
              />
              {selected.correlation_ids?.length > 0 && (
                <Row label="Correlation IDs" value={selected.correlation_ids.join(", ")} />
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="text-slate-800 dark:text-slate-200">{value}</p>
    </div>
  )
}
