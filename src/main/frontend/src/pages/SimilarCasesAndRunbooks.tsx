import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Badge, Card, EmptyState, ErrorState, LoadingState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { Incident, Runbook, SimilarCase } from "../lib/types"

export function SimilarCasesAndRunbooks() {
  const { id } = useParams<{ id: string }>()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [cases, setCases] = useState<SimilarCase[] | null>(null)
  const [runbooks, setRunbooks] = useState<Runbook[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([api.getIncident(id), api.similarCases(id)])
      .then(([inc, sc]) => {
        setIncident(inc)
        setCases(sc)
        return api.listRunbooks(inc.reconciliation_status ?? undefined)
      })
      .then(setRunbooks)
      .catch((e) => setError(e.message))
  }, [id])

  if (error) return <ErrorState message={error} />
  if (!incident || !cases || !runbooks || !id) return <LoadingState />

  return (
    <div>
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <SectionTitle>Similar incidents</SectionTitle>
          {cases.length > 0 && (
            <p className="mb-3 text-xs text-slate-400">
              {cases[0].method === "semantic_rag"
                ? "Semantic search — Gemini embeddings + cosine similarity over the RAG index."
                : "Lexical (word-overlap) similarity — no RAG index built yet, see docs/architecture.md."}
            </p>
          )}
          {cases.length === 0 ? (
            <EmptyState message="No sufficiently similar incidents found." />
          ) : (
            <ul className="space-y-3">
              {cases.map((c) => (
                <li key={c.incident_id} className="rounded-xl border-l-4 border-indigo-400 bg-white p-4 shadow-sm">
                  <div className="mb-1 flex items-center justify-between">
                    <Link to={`/incidents/${c.incident_id}`} className="text-sm font-semibold text-indigo-600 hover:underline">
                      Case #{c.incident_id}
                    </Link>
                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                      {Math.round(c.similarity_score * 100)}% similar
                    </span>
                  </div>
                  <p className="font-semibold text-slate-900">{c.title}</p>
                  {c.shared_terms.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {c.shared_terms.slice(0, 4).map((t) => (
                        <span key={t} className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">{t}</span>
                      ))}
                    </div>
                  )}
                  <Link to={`/incidents/${c.incident_id}`} className="mt-2 inline-block text-xs font-medium text-indigo-600 hover:underline">
                    View Case →
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <SectionTitle>Relevant runbooks</SectionTitle>
          {runbooks.length === 0 ? (
            <EmptyState message="No matching runbooks." />
          ) : (
            <ul className="space-y-3">
              {runbooks.map((rb) => (
                <li key={rb.runbook_id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-medium text-slate-900 dark:text-white">{rb.title}</span>
                    <Badge value={rb.source} />
                  </div>
                  <p className="mb-2 text-sm text-slate-600 dark:text-slate-300">{rb.content}</p>
                  <div className="flex flex-wrap gap-1">
                    {rb.scenario_tags.map((tag) => <Badge key={tag} value={tag} />)}
                  </div>
                  {rb.sections.length > 0 && (
                    <p className="mt-2 text-xs text-slate-400">Sections: {rb.sections.join(" · ")}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
