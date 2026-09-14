# Autonomous Merchandise Discovery

This repository contains the modular MVP for discovering merchandise niches, validating them with public evidence, generating concepts, and producing artwork candidates for human review.

## Current chunk

Chunks one through eight establish the complete deterministic funnel through human approval. Chunk 9
adds bounded retries, durable stage logs, stage-version provenance, a continuous worker mode, and
live run-detail polling. The default runtime still uses local fixture providers; no external AI or
research API is called.

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
`OPENAI_API_KEY` enables OpenAI web search and structured outputs for Stages 6, 9, 10, and 13, while
`XAI_API_KEY` enables the configured xAI image model for Stage 15. Missing keys continue to use the
fixture provider. Token costs are estimated from the configured OpenAI rates; xAI image costs are
estimated from the configured per-image rate.

When `MONGODB_URI` is present in `.env`, starting Streamlit performs the same health check and
initialization automatically. MongoDB databases are created lazily, so the app creates an
`_app_metadata` infrastructure collection and the workflow indexes; the configured database then
appears in Compass or `show dbs`.

The current client demo defaults to `MVP_STOP_AFTER_STAGE=1`. Stage 1 is executed and the run is
persisted as `paused` so later stages do not run until the client approves expanding the funnel.
The stop boundary is shared by Streamlit and the worker.

Copy `.env.example` to `.env` when local credentials are needed. Real credentials belong in environment variables or a local Streamlit secrets file; they must not be committed.

## Design rules

- `entrypoints` contains Streamlit and worker adapters only.
- `application` owns use cases and workflow orchestration.
- `domain/stages` contains one module per pipeline stage.
- `infrastructure/mongo/repositories` is the only place for MongoDB queries.
- `infrastructure/providers` is the only place for external AI and research API clients.
- Stage logic must not import Streamlit, MongoDB clients, or provider SDKs directly.
