// Thin typed fetch wrapper over the FastAPI backend. Every function here
// hits a real route from src/main/backend/api/app.py — nothing is mocked.
import type {
  ActionProposal,
  AuditRecord,
  EvidenceRecord,
  ExecuteActionResult,
  Incident,
  InvestigationReport,
  ReconciliationResult,
  Runbook,
  SampleIncidentSummary,
  SimilarCase,
  SourceEvent,
  VerifyActionResult,
} from "./types"

const BASE = "/api/v1"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  listIncidents: (status?: string) =>
    request<Incident[]>(`/incidents${status ? `?status=${status}` : ""}`),

  getIncident: (id: string) => request<Incident>(`/incidents/${id}`),

  createIncident: (payload: {
    title: string
    complaint: string
    transaction_ref?: string
    amount: string
    currency?: string
    merchant_id: string
  }) => request<Incident>("/incidents", { method: "POST", body: JSON.stringify(payload) }),

  sampleIncidents: () => request<SampleIncidentSummary[]>("/sample-incidents"),

  getEvents: (id: string) => request<SourceEvent[]>(`/incidents/${id}/events`),

  getEvidence: (id: string) => request<EvidenceRecord[]>(`/incidents/${id}/evidence`),

  reconcile: (id: string) =>
    request<ReconciliationResult>(`/incidents/${id}/reconcile`, { method: "POST" }),

  investigate: (id: string) =>
    request<InvestigationReport>(`/incidents/${id}/investigate`, { method: "POST" }),

  getInvestigation: (id: string) =>
    request<InvestigationReport>(`/incidents/${id}/investigation`),

  similarCases: (id: string) => request<SimilarCase[]>(`/incidents/${id}/similar-cases`),

  listRunbooks: (tag?: string) =>
    request<Runbook[]>(`/runbooks${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`),

  proposeAction: (incidentId: string, actorId = "ui_user") =>
    request<ActionProposal>(`/incidents/${incidentId}/actions/propose`, {
      method: "POST",
      body: JSON.stringify({ actor_id: actorId }),
    }),

  executeAction: (actionId: string, actorId: string, idempotencyKey: string) =>
    request<ExecuteActionResult>(`/actions/${actionId}/execute`, {
      method: "POST",
      body: JSON.stringify({ actor_id: actorId, idempotency_key: idempotencyKey }),
    }),

  verifyAction: (actionId: string, expectedResult: string) =>
    request<VerifyActionResult>(`/actions/${actionId}/verify`, {
      method: "POST",
      body: JSON.stringify({ expected_result: expectedResult }),
    }),

  getAudit: (id: string) => request<AuditRecord[]>(`/incidents/${id}/audit`),
}
