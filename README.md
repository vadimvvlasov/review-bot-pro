# Review-Reply Bot ("Reputation Manager")

AI-powered MVP that helps local businesses (cafes, auto shops, salons) manage
and reply to customer reviews. Owners import reviews, generate context-aware
draft replies with one click (via LLM structured output — reply text,
sentiment, tags), steer/edit them, and approve.

Built with **FastAPI + SQLite** (backend) and **React/Vite** (frontend) as
part of AI Dev Tools Zoomcamp 2026.

## Quickstart

```sh
make install   # install backend + frontend deps
make dev       # run backend (:8000) + frontend together
make test      # run backend + frontend test suites
```

See `make help` for all available targets.

## Docs

- [`docs/spec.md`](docs/spec.md) — full product spec: data model, API
  contracts, acceptance criteria, testing strategy, milestone roadmap.
- [`openapi.yaml`](openapi.yaml) — API contract.
- [`AGENTS.md`](AGENTS.md) — backend dev conventions (uv, SOLID, 50-line
  function limit).

## Status

Backend scaffolding in progress (FastAPI app, auth, core routes). See
Milestone Roadmap in `docs/spec.md` §8 for current stage.
