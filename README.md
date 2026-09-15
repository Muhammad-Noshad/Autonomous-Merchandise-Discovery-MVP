# Autonomous Merchandise Discovery

This repository contains the modular MVP for discovering merchandise niches, validating them with public evidence, generating concepts, and producing artwork candidates for human review.

## Current chunk

Chunks one through eight establish the complete funnel through human approval. Chunk 9 adds bounded
retries, durable stage logs, stage-version provenance, continuous worker mode, and live run-detail
polling. Chunk 10 adds opt-in live provider calls, usage accounting, and AI-assisted Stage 2 identity
expansion plus Stage 3 intersection generation. The default runtime remains fixture-backed unless
`MVP_PROVIDER_MODE=live` and the required API key are configured.

## Local setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
streamlit run app.py
```

Run tests with:

```powershell
pytest
```

Verify a configured MongoDB deployment with:

```powershell
python scripts/check_mongodb.py
```

To permanently clear the entire configured MongoDB database, run:

```powershell
python scripts/clear_database.py
```

The command shows the target database and requires typing its exact name. For a deliberate
non-interactive reset, use `python scripts/clear_database.py --yes` only after verifying `.env`.

Process one queued run with:

```powershell
python worker.py --once
```

Keep the worker polling for new runs with:

```powershell
python worker.py --loop --poll-interval 2
```

Set `MVP_MAX_STAGE_ATTEMPTS` in `.env` to change the retry ceiling. A failed stage is retried when
the worker is run again until that ceiling is reached; after that, the run remains failed and is no
longer reclaimed automatically.

Set `MVP_PROVIDER_MODE=live` only when you intend to spend API credits. In live mode,
`OPENAI_API_KEY` enables OpenAI structured outputs for Stages 2–4, 7–10, and 13, plus OpenAI web
search for Stage 6. Stages 1 and 5 remain deterministic, while Stage 8 uses AI only for its
bounded qualitative components and calculates evidence strength and the final total locally.
`OPENAI_API_KEY` also enables the batched structured comparison in Stage 12. Stage 16 artwork
critique remains deterministic for the MVP. `XAI_API_KEY` enables the configured xAI image model
for Stage 15. Missing keys
continue to use the fixture provider or deterministic fallback. Token costs are estimated from the
configured OpenAI rates; Stage 6 also adds `OPENAI_WEB_SEARCH_PRICE_PER_CALL` (default `$0.01`,
derived from `$10 per 1,000 calls`); xAI image costs are estimated from the configured per-image rate.
Live Stage 15 binaries are downloaded into `ARTWORK_STORAGE_DIR` (default `.artifacts`) behind an
object-storage boundary; fixture artwork remains reference-only and does not perform network I/O.

When `MONGODB_URI` is present in `.env`, starting Streamlit performs the same health check and
initialization automatically. MongoDB databases are created lazily, so the app creates an
`_app_metadata` infrastructure collection and the workflow indexes; the configured database then
appears in Compass or `show dbs`.

At runtime startup, an empty MongoDB `seeds` collection is populated from
`data/seed_knowledge.json`. Existing seed records are preserved and are not overwritten by later
application starts.

The current client demo defaults to `MVP_STOP_AFTER_STAGE=1`. Stage 1 is executed and the run is
persisted as `paused` so later stages do not run until the client approves expanding the funnel.
When a run is created from Streamlit, a process-local background runner advances it independently
of the visible page; the Run Detail view reads and polls the durable MongoDB state. The stop
boundary is shared by Streamlit and the worker.

Copy `.env.example` to `.env` when local credentials are needed. Real credentials belong in environment variables or a local Streamlit secrets file; they must not be committed.

## Design rules

- `entrypoints` contains Streamlit and worker adapters only.
- `application` owns use cases and workflow orchestration.
- `domain/stages` contains one module per pipeline stage.
- `infrastructure/mongo/repositories` is the only place for MongoDB queries.
- `infrastructure/providers` is the only place for external AI and research API clients.
- Stage logic must not import Streamlit, MongoDB clients, or provider SDKs directly.
