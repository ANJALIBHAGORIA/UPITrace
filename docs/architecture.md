# UPITrace — Architecture (Phase 1 scope)

## Stack
- Frontend: React + TypeScript + Vite + Tailwind + shadcn/ui (Phase 4 — not started; `node`/`npm` are not installed on this machine, noted as a blocker to resolve before Phase 4).
- Backend: Python 3.9 + FastAPI + Pydantic v2 + Pytest, isolated in `.venv`.
- Cloud (Phase 5): Firebase Hosting, Cloud Run, Firebase Auth, Firestore, Cloud Storage, Vertex AI Gemini + embeddings.

## Repository layout
```
ai_builder_cup/
├── docs/
│   ├── architecture.md
│   └── implementation_plan.md
├── src/main/
│   ├── backend/
│   │   ├── models/          # Pydantic domain models + enums (this phase)
│   │   ├── scripts/         # generate_synthetic_data.py
│   │   ├── data/
│   │   │   ├── synthetic/   # generated incidents/events/evidence (gitignored)
│   │   │   └── evaluation/  # ground truth, kept separate from production data
│   │   └── tests/
│   └── frontend/            # placeholder for Phase 4
├── requirements.txt
├── pytest.ini
├── .env.example
└── .gitignore
```

## Logical flow (target, Phases 2–3)
```
UI (simulator / merchant portal / dashboard)
  → FastAPI (/api/v1)
    → case management + evidence ingestion
    → deterministic reconciliation engine   (Phase 2)
    → investigation orchestrator            (Phase 3)
      → hybrid retrieval (lexical + Vertex AI embeddings)
      → Vertex AI Gemini, structured output
      → citation verification against evidence store
    → action simulator + outcome verification
  → Firestore / Cloud Storage (Phase 5), local JSON for now
```

## Phase 1 scope (this task)
Only the domain models and the synthetic data generator. No API routes, no reconciliation
logic, no Gemini calls yet — those are Phases 2–3 per the implementation plan.

## Key invariants enforced in the models
- Raw source records are kept separate from normalized status (`SourceEvent.source_status` vs
  `normalized_status`); nothing silently upgrades an ambiguous status to a confirmed one.
- `event_time` (when it happened) and `ingested_at` (when we learned about it) are always
  distinct fields.
- `NOT_FOUND` (merchant order) is an explicit state, not a stand-in for "payment failed."
- Every `Citation`/`Finding` references a real `evidence_id`; nothing in the schema allows a
  free-text claim to stand without an evidence pointer (enforcement of "no invented evidence
  IDs" happens in Phase 3 verification code — the model just makes the field mandatory).
- `ActionExecution.execution_mode` is `SIMULATED` by default; `LIVE` is a distinct enum value
  the executor must opt into explicitly (Phase 2+).
- Ground truth (`EvaluationGroundTruth`) lives in `data/evaluation/`, a separate model and a
  separate file from `data/synthetic/`, so the (future) investigation pipeline has no import
  path to it.

## Known gaps / follow-ups
- No `node`/`npm` on this machine → Phase 4 frontend cannot start until that's installed.
- Python is 3.9.6 (system default) — fine for FastAPI/Pydantic v2, isolated via `.venv`.
- Vertex AI / Firebase credentials are not configured — out of scope until Phase 5.
