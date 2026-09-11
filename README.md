# Autonomous Merchandise Discovery

This repository contains the modular MVP for discovering merchandise niches, validating them with public evidence, generating concepts, and producing artwork candidates for human review.

## Current chunk

Chunks one and two establish the project boundaries, fixture-backed Streamlit entrypoint, MongoDB persistence contracts, and repository layer. The workflow stages, MongoDB queries, and provider implementations remain intentionally isolated so they can be implemented and moved independently.

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

When `MONGODB_URI` is present in `.env`, starting Streamlit performs the same health check and
initialization automatically. MongoDB databases are created lazily, so the app creates an
`_app_metadata` infrastructure collection and the workflow indexes; the configured database then
appears in Compass or `show dbs`.

Copy `.env.example` to `.env` when local credentials are needed. Real credentials belong in environment variables or a local Streamlit secrets file; they must not be committed.

## Design rules

- `entrypoints` contains Streamlit and worker adapters only.
- `application` owns use cases and workflow orchestration.
- `domain/stages` contains one module per pipeline stage.
- `infrastructure/mongo/repositories` is the only place for MongoDB queries.
- `infrastructure/providers` is the only place for external AI and research API clients.
- Stage logic must not import Streamlit, MongoDB clients, or provider SDKs directly.
