import { useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { SourceEvent } from "../lib/types"

const STATUS_STYLE: Record<string, { label: string; pill: string; dot: string; icon: string; iconBg: string }> = {
  CONFIRMED: { label: "Confirmed", pill: "bg-emerald-100 text-emerald-700", dot: "bg-emerald-500", icon: "🏦", iconBg: "bg-emerald-500" },
  OBSERVED: { label: "Observed", pill: "bg-sky-100 text-sky-700", dot: "bg-sky-500", icon: "📡", iconBg: "bg-sky-500" },
  PENDING: { label: "Pending", pill: "bg-amber-100 text-amber-700", dot: "bg-amber-500", icon: "⏳", iconBg: "bg-amber-500" },
  MISSING: { label: "Missing", pill: "bg-rose-100 text-rose-700", dot: "bg-violet-500", icon: "📵", iconBg: "bg-violet-500" },
  NOT_FOUND: { label: "Not Found", pill: "bg-slate-100 text-slate-600", dot: "bg-slate-300", icon: "🔍", iconBg: "bg-slate-400" },
  CONFLICTED: { label: "Conflicted", pill: "bg-rose-100 text-rose-700", dot: "bg-rose-500", icon: "⚠️", iconBg: "bg-rose-500" },
  UNRESOLVED: { label: "Unresolved", pill: "bg-slate-100 text-slate-600", dot: "bg-slate-300", icon: "❓", iconBg: "bg-slate-400" },
}

const EVENT_LABELS: Record<string, { title: string; desc: (e: SourceEvent) => string }> = {
  DEBIT_CONFIRMED: { title: "Payer Debit Successful", desc: (e) => `₹${e.amount ?? ""} debited from payer account.` },
  PAYMENT_REQUEST_RECEIVED: { title: "Payment Request Received", desc: () => "UPI request received and processed." },
  GATEWAY_STATUS: { title: "Gateway Status: Pending", desc: () => "Transaction marked as pending." },
  MERCHANT_CALLBACK: { title: "Callback Not Received", desc: () => "No payment confirmation callback received." },
  ORDER_LOOKUP: { title: "Merchant Order Confirmation", desc: () => "No order found in the provided records." },
}

function styleFor(e: SourceEvent) {
  return STATUS_STYLE[e.normalized_status] ?? { label: e.normalized_status, pill: "bg-slate-100 text-slate-600", dot: "bg-slate-300", icon: "•", iconBg: "bg-slate-400" }
}

function labelFor(e: SourceEvent) {
  return EVENT_LABELS[e.event_type] ?? { title: e.event_type.replaceAll("_", " "), desc: () => `${e.source_system} reported ${e.source_status}.` }
}

export function EventTimeline() {
  const { id } = useParams<{ id: string }>()
  const [events, setEvents] = useState<SourceEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sourceFilter, setSourceFilter] = useState<string | "ALL">("ALL")
  const [view, setView] = useState<"timeline" | "table">("timeline")
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
      <div className="mb-4 flex items-center justify-between">
        <div>
          <SectionTitle>Cross-platform event timeline</SectionTitle>
          <p className="-mt-3 text-sm text-slate-500">Chronological view from multiple sources</p>
        </div>
        <div className="flex gap-2">
          <select className="input w-auto" value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
            <option value="ALL">All sources</option>
            {sources.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <div className="flex overflow-hidden rounded-lg border border-slate-200">
            <button onClick={() => setView("timeline")} className={`px-3 py-1.5 text-sm font-medium ${view === "timeline" ? "bg-indigo-600 text-white" : "bg-white text-slate-600"}`}>Timeline</button>
            <button onClick={() => setView("table")} className={`px-3 py-1.5 text-sm font-medium ${view === "table" ? "bg-indigo-600 text-white" : "bg-white text-slate-600"}`}>Table</button>
          </div>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState message="No events recorded for this incident — that is itself a finding, not just empty data." />
      ) : (
        <div className="grid gap-6 md:grid-cols-3">
          <div className="md:col-span-2">
            {view === "timeline" ? (
              <ol className="relative space-y-5 border-l-2 border-slate-100 pl-8">
                {filtered.map((e) => {
                  const s = styleFor(e)
                  const l = labelFor(e)
                  return (
                    <li key={e.event_id} className="relative">
                      <span className={`absolute -left-[41px] top-0 flex h-8 w-8 items-center justify-center rounded-full text-sm text-white ${s.iconBg}`}>{s.icon}</span>
                      <div className="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
                        <div>
                          <p className="text-xs font-medium text-slate-400">{new Date(e.event_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                          <p className="font-semibold text-slate-900">{l.title}</p>
                          <p className="text-xs text-slate-500">{e.source_system.replaceAll("_", " ")}</p>
                          <p className="mt-1 text-sm text-slate-500">{l.desc(e)}</p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-2">
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${s.pill}`}>{s.label}</span>
                          <button onClick={() => setSelected(e)} className="text-xs font-medium text-indigo-600 hover:underline">View</button>
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ol>
            ) : (
              <Card className="overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-100 text-xs text-slate-400">
                    <tr><th className="p-3">Time</th><th className="p-3">Event</th><th className="p-3">Source</th><th className="p-3">Status</th></tr>
                  </thead>
                  <tbody>
                    {filtered.map((e) => {
                      const s = styleFor(e); const l = labelFor(e)
                      return (
                        <tr key={e.event_id} className="cursor-pointer border-b border-slate-50 hover:bg-slate-50" onClick={() => setSelected(e)}>
                          <td className="p-3 text-slate-400">{new Date(e.event_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                          <td className="p-3 font-medium text-slate-900">{l.title}</td>
                          <td className="p-3 text-slate-500">{e.source_system.replaceAll("_", " ")}</td>
                          <td className="p-3"><span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${s.pill}`}>{s.label}</span></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </Card>
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
                {selected.normalized_status === "NOT_FOUND" && (
                  <Row label="Note" value="Absence of a record — NOT proof the underlying transaction failed." />
                )}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="text-slate-800">{value}</p>
    </div>
  )
}
