import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button, Card, ErrorState, SectionTitle } from "../components/ui"
import { api } from "../lib/api"
import type { SampleIncidentSummary } from "../lib/types"

interface FormState {
  title: string
  complaint: string
  transaction_ref: string
  amount: string
  merchant_id: string
}

const EMPTY: FormState = { title: "", complaint: "", transaction_ref: "", amount: "", merchant_id: "" }

export function NewIncident() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState>(EMPTY)
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [samples, setSamples] = useState<SampleIncidentSummary[] | null>(null)

  useEffect(() => {
    api.sampleIncidents().then(setSamples).catch(() => setSamples([]))
  }, [])

  function update<K extends keyof FormState>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function validate(): boolean {
    const next: Partial<Record<keyof FormState, string>> = {}
    if (!form.title.trim()) next.title = "Title is required."
    if (!form.complaint.trim()) next.complaint = "Describe the issue."
    if (!form.merchant_id.trim()) next.merchant_id = "Merchant is required."
    if (!form.amount.trim() || Number.isNaN(Number(form.amount)) || Number(form.amount) <= 0) {
      next.amount = "Enter a valid positive amount."
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    if (!validate()) return
    setSubmitting(true)
    try {
      const incident = await api.createIncident({
        title: form.title, complaint: form.complaint,
        transaction_ref: form.transaction_ref || undefined,
        amount: form.amount, merchant_id: form.merchant_id,
      })
      navigate(`/incidents/${incident.incident_id}`)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create incident.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <SectionTitle>Create a new incident</SectionTitle>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Title" error={errors.title}>
            <input className="input" value={form.title} onChange={(e) => update("title", e.target.value)} />
          </Field>
          <Field label="Issue description" error={errors.complaint}>
            <textarea className="input" rows={3} value={form.complaint} onChange={(e) => update("complaint", e.target.value)} />
          </Field>
          <Field label="Transaction reference (optional)">
            <input className="input" value={form.transaction_ref} onChange={(e) => update("transaction_ref", e.target.value)} />
          </Field>
          <Field label="Amount (₹)" error={errors.amount}>
            <input className="input" value={form.amount} onChange={(e) => update("amount", e.target.value)} />
          </Field>
          <Field label="Merchant" error={errors.merchant_id}>
            <input className="input" value={form.merchant_id} onChange={(e) => update("merchant_id", e.target.value)} />
          </Field>
          {submitError && <ErrorState message={submitError} />}
          <Button type="submit" disabled={submitting}>{submitting ? "Creating…" : "Analyze Incident"}</Button>
        </form>
      </Card>

      <Card>
        <SectionTitle>Or try a sample case</SectionTitle>
        {samples === null && <p className="text-sm text-slate-500">Loading samples…</p>}
        {samples?.length === 0 && <p className="text-sm text-slate-500">No samples available.</p>}
        <div className="flex flex-wrap gap-2">
          {samples?.map((s) => (
            <button
              key={s.incident_id}
              onClick={() => navigate(`/incidents/${s.incident_id}`)}
              className="rounded-lg border border-slate-200 px-3 py-2 text-left text-xs hover:border-indigo-400 hover:bg-indigo-50 dark:border-slate-700 dark:hover:bg-slate-800"
              title={s.title}
            >
              {s.scenario_category.replaceAll("_", " ")}
            </button>
          ))}
        </div>
      </Card>
    </div>
  )
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      {children}
      {error && <span className="mt-1 block text-xs text-rose-600 dark:text-rose-400">{error}</span>}
    </label>
  )
}
