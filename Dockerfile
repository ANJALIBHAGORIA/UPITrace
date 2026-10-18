# Single Cloud Run service: builds the React frontend, then serves it +
# the FastAPI API from one Python process (matches the local dev pattern
# already verified in this repo — api/app.py mounts dist/ and serves it
# under /upitrace, with /api/v1/* handled by the same process).
#
# NOT yet built/deployed to Cloud Run — see docs/implementation_plan.md for
# verification status.

FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY src/main/frontend/package*.json ./
RUN npm ci
COPY src/main/frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY --from=frontend-build /app/frontend/dist ./src/main/frontend/dist

# Deterministic/seeded, no credentials needed — bakes the 10,008-incident
# demo dataset into the image. The RAG index is NOT baked in here: building
# it calls the real Vertex AI embeddings API, which needs ADC credentials
# unavailable at build time. Run it post-deploy (see README's deployment
# section) — until then, /similar-cases falls back to lexical search.
RUN python -m src.main.backend.scripts.generate_synthetic_data

ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn src.main.backend.api.app:app --host 0.0.0.0 --port ${PORT}
