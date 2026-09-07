"""Shared FastAPI dependencies."""

from fastapi import Request

from .store import InMemoryStore


def get_store(request: Request) -> InMemoryStore:
    return request.app.state.store
