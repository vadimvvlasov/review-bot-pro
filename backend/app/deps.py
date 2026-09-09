"""Shared FastAPI dependencies."""

from fastapi import Request

from .store import DbStore


def get_store(request: Request) -> DbStore:
    return request.app.state.store
