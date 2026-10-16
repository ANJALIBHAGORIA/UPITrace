# UPITrace — Implementation Plan

## Phases
1. **Synthetic data + domain models** (current) — typed Pydantic models, reproducible generator
   (≥30 incidents, 12 scenario categories), validation tests.
2. **FastAPI + simulator connectors + reconciliation engine** — `/api/v1` routes, deterministic
   rules engine independent of any LLM, audit logging, API tests.
3. **Vertex AI / Gemini + hybrid RAG** — investigation orchestrator, citation verification
   against the evidence store, evaluation harness against the ground-truth dataset.
4. **Full connected UI** — React/TS/Vite frontend for all 9 screens (A–I from the spec).
5. **Cloud deployment** — Firebase Hosting, Cloud Run, Firestore, Vertex AI config, smoke tests.

Each phase only starts once the previous phase's acceptance criteria pass.

## Phase 2 status: DONE
- Deterministic reconciliation engine (`reconciliation/engine.py`), 8 named rules (R1-R8),
  priority-ordered, independent of any LLM.
- All 9 agent tool contracts implemented as SIMULATED connectors over the in-memory store
  (`tools/service.py`), with typed I/O (`tools/schemas.py`). `propose_resolution` is a
  deterministic stand-in labelled as such — Gemini-authored proposals are Phase 3.
- FastAPI app (`api/app.py`) with all routes from spec section 7, backed by `store.py`
  (in-memory stand-in for Firestore) and `audit.py` (every mutating route writes an
  `AuditRecord`).
- 39 new tests (`test_reconciliation.py`, `test_tools.py`, `test_api.py`), including a
  full cross-check that every one of the 36 Phase 1 incidents reconciles to its
  ground-truth classification, and real FastAPI `TestClient` calls (not mocked).
- Verified commands:
  ```bash
  python -m pytest src/main/backend/tests -q        # 68 passed
  uvicorn src.main.backend.api.app:app --reload      # boots, loads 36 incidents
  curl localhost:8000/health                         # {"status":"ok","incidents_loaded":36}
  ```
- One real bug caught and fixed by the test suite: `request_action`'s idempotency check
  ran after the status gate, so replaying an idempotency key on an already-executed action
  was incorrectly rejected instead of returning the prior execution. Fixed by checking
  idempotency first.
- Known simplification: `similar-cases` uses lexical (Jaccard word-overlap) similarity with
  real, computed scores — not the hybrid lexical+semantic retrieval with Vertex AI embeddings
  promised for Phase 3.

## Phase 3 status: DONE (with one unresolved infrastructure gap)
- `ai/fake_provider.py` — deterministic, non-LLM provider for tests, derives everything
  from the already-computed `ReconciliationResult`. `ai/vertex_provider.py` — real
  implementation, fails closed (`AIProviderUnavailable`) at every point it can't
  genuinely produce a Gemini response (missing project/model config, missing SDK,
  auth failure, non-JSON output, missing fields).
- `investigation/orchestrator.py` implements all 13 steps from spec section 8.
  Confirmed via manual run: with no GCP credentials on this machine, `/investigate`
  returns a full report with `ai_used=False`, `source_mode=UNAVAILABLE`,
  `model_identifier="none (deterministic fallback)"` — never a fabricated answer.
- `investigation/citation_verification.py` strips any citation ID not present in the
  incident's own evidence/runbooks and reports what was removed
  (`unsupported_claims_removed`) — verified with a deliberately "lying" fake provider
  in `test_orchestrator_strips_invented_citations_from_a_misbehaving_provider`.
- Policy check (step 12): `recommended_next_action` must be one of the reconciliation
  engine's own `permitted_checks` whenever that list is non-empty; otherwise it's
  overridden and `policy_override_applied=True` — verified with a deliberately
  "reckless" fake provider recommending `tell_customer_refund_is_complete` on a
  REVERSAL_MISSING_OR_PENDING incident; the orchestrator overrode it to
  `query_reversal_status`.
- `retrieval/hybrid.py` combines lexical (Jaccard) + a **local term-frequency cosine
  proxy** — explicitly NOT real embeddings (no Vertex AI access). This is the single
  swap-in point for real Vertex AI embeddings later.
- `scripts/evaluate_investigation.py` runs the spec section 10 metrics
  (reconciliation accuracy, safe-action rate, correct-abstention rate, citation
  validity, latency) using `FakeAIProvider`. Actual run: 36/36 reconciliation
  accuracy, 100% citation validity, 3/3 correct abstentions — **but this measures
  the orchestrator's own plumbing, not real Gemini quality**, and the script's own
  output says so.
- 13 new tests (`test_investigation.py`), 83 total, all passing: `python -m pytest
  src/main/backend/tests -q`.
- **Unresolved gap**: `pip install google-cloud-aiplatform` stalled for several
  minutes with almost no CPU progress in this sandbox (likely a slow/blocked network
  path) and was killed rather than left hanging. The SDK is therefore **not actually
  installed** — `vertex_provider.py` is correct, reviewed code that has never been
  exercised against a real import of `vertexai`. Before Phase 5 cloud work, retry the
  install from a network path that isn't sandboxed, or install via Cloud Build/Cloud
  Shell instead of this machine, and add a test that actually exercises
  `VertexGeminiProvider` end-to-end against a real (or recorded) Gemini call.

## Phase 4 status: DONE (core flow); two labelled simplifications
- **Infrastructure unblocked**: Node.js was not installed on this machine (noted as a
  blocker in Phase 1). Installed via Homebrew (`brew install node`) — now Node v26.12.0 /
  npm 11.20.0.
- Scaffolded with the official `npm create vite@latest -- --template react-ts` into
  `src/main/frontend`, then added Tailwind CSS v4 (`@tailwindcss/vite` plugin, no separate
  config file needed) and `react-router-dom`.
- All 9 screens (A-I) implemented as real, routed pages under `src/pages/`, each wired to
  the real FastAPI backend via `src/lib/api.ts` (no mocked data) — not a static mockup.
  Vite's dev-server proxy (`/api` → `http://127.0.0.1:8000`) avoids CORS in development.
- Verified: `npm run build` succeeds with zero TypeScript errors and zero warnings.
- Verified end-to-end through the actual dev-server proxy (not just the backend directly):
  create incident → reconcile → investigate (correctly shows `ai_used: false,
  source_mode: UNAVAILABLE` banner) → propose action → execute (simulated, with an explicit
  human-confirmation step in the UI) → verify → audit trail shows all 7 events in order.
- **Labelled simplification 1**: there's no dedicated `/payment-attempts` or
  `/merchant-orders` list endpoint in the API (not in spec section 7's route list either),
  so Screens A (customer simulator) and B (merchant portal) render views over
  `/api/v1/incidents` instead — which already carries transaction_ref/amount/merchant_id/
  status. Commented in both files; not presented as more than it is.
- **Labelled simplification 2**: no shadcn/ui CLI-generated components (would need an
  interactive `shadcn init`) — built a small hand-rolled Tailwind component set instead
  (`src/components/ui.tsx`: Card, Badge, Button, List, Loading/Error/Empty states),
  styled consistently across all 9 screens.
- Not yet done: this was a one-shot manual smoke test via curl through the proxy, not a
  real browser click-through — no visual/screenshot verification was performed.

## Phase 1 acceptance criteria
- [ ] Domain models for: Incident, PaymentAttempt, MerchantOrder, SourceEvent, EvidenceRecord,
      NotificationRecord, Runbook, Finding/Citation, ActionProposal/ActionExecution, AuditRecord,
      plus `EvaluationGroundTruth` kept in a separate module/data directory.
- [ ] All enums (`IncidentStatus`, `ReconciliationStatus`, `SourceMode`, `OrderStatus`,
      `VerificationStatus`, etc.) match the spec's suggested values.
- [ ] `generate_synthetic_data.py` is deterministic given a fixed seed (default 42) and produces
      ≥30 incidents covering all 12 listed scenario categories at least once.
- [ ] Generated incidents reference valid, internally-consistent IDs (every `evidence_id` on an
      incident resolves to a real evidence record; every `payment_attempt_id` referenced by an
      order/incident exists, etc.).
- [ ] Ground truth is written to `data/evaluation/` and is not importable from anything that
      would later act as the "production" investigation path.
- [ ] `pytest` passes locally from `src/main/backend` using the project `.venv`.

## Commands (actual, verified on this machine)
```bash
cd /Users/anjalibhagoria/Documents/sicode/ai_builder_cup
source .venv/bin/activate
python -m src.main.backend.scripts.generate_synthetic_data   # writes data/synthetic + data/evaluation
pytest src/main/backend/tests -q
```
(Run from the project root so the `src.main.backend` package resolves; see `pytest.ini` /
`conftest.py` for path setup.)

## Explicit non-goals for Phase 1
- No FastAPI routes yet (Phase 2).
- No reconciliation logic yet — the generator encodes *intended* reconciliation classification
  as part of ground truth, but nothing computes it from evidence yet.
- No Gemini/Vertex AI calls (Phase 3).
- No frontend code (Phase 4) — blocked on installing Node/npm on this machine.
