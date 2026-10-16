# UPITrace

AI-assisted investigation for UPI payment incidents where the customer-facing status,
provider/gateway records, bank evidence, notification logs, and merchant order status may
be incomplete or contradictory.

UPITrace correlates available records, builds an evidence timeline, applies deterministic
reconciliation rules, retrieves relevant runbooks and similar cases, and (when Vertex AI is
configured) uses Gemini to produce an evidence-grounded investigation with verified
citations. It is a decision-support tool, not a live payment processor — every connector is
explicitly `SIMULATED` unless a real, authorized integration is configured.

## Status

| Phase | What | Status |
|---|---|---|
| 1 | Domain models + synthetic data generator (36 incidents, 12 scenario categories) | Done |
| 2 | FastAPI + deterministic reconciliation engine + 9 agent tool connectors | Done |
| 3 | Investigation orchestrator + citation verification + policy checks + Vertex AI provider | Done (Vertex AI untested — no GCP credentials on dev machine) |
| 4 | React + TypeScript + Vite + Tailwind frontend, all 9 screens | Done |
| 5 | Cloud deployment (Firebase Hosting, Cloud Run, Firestore) | Not started |

See `docs/architecture.md` and `docs/implementation_plan.md` for details, including the
honestly-labelled simplifications and known gaps at each phase.

## Running locally

### Backend

```bash
cd ai_builder_cup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Generate the synthetic dataset (required — not committed to git)
python -m src.main.backend.scripts.generate_synthetic_data

# Run tests
pytest -q

# Run the API
uvicorn src.main.backend.api.app:app --port 8001 --reload
```

### Frontend

```bash
cd src/main/frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8001` (see `vite.config.ts`) — adjust the
port there if you run the backend elsewhere.

### Evaluation

```bash
python -m src.main.backend.scripts.evaluate_investigation
```

Runs the spec-section-10 metrics using the deterministic `FakeAIProvider` (no Vertex AI
credentials are configured in this environment — see `docs/implementation_plan.md`'s Phase 3
notes before citing these numbers as real Gemini performance).

## Configuration

Copy `.env.example` to `.env` and fill in real values for Phase 5 (cloud) work. Never commit
`.env`.

## Project layout

```
ai_builder_cup/
├── docs/                        # architecture.md, implementation_plan.md
├── requirements.txt
├── .env.example
└── src/main/
    ├── backend/
    │   ├── models/              # Pydantic domain models
    │   ├── scripts/             # synthetic data generator, evaluation harness
    │   ├── reconciliation/      # deterministic rules engine
    │   ├── tools/                # 9 agent tool connectors (all SIMULATED)
    │   ├── ai/                  # fake + real (Vertex Gemini) AI providers
    │   ├── retrieval/           # hybrid lexical + local similarity retrieval
    │   ├── investigation/       # orchestrator, citation verification
    │   ├── api/                 # FastAPI app and routes
    │   └── tests/
    └── frontend/                # React + TypeScript + Vite + Tailwind
```
