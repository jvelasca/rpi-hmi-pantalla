"""Fixtures compartidas para todos los tests del backend."""

import os

# Forzar enable_admin_api=True en tests para que los routers /admin/*
# se incluyan. Debe ejecutarse ANTES de importar backend.app.main.
# NOTA: No seteamos ADMIN_API_KEY aqui — el fixture set_api_key en
# test_integration.py se encarga de mutar settings.admin_api_key.
os.environ["ENABLE_ADMIN_API"] = "true"

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.state_manager import StateManager, state_manager


@pytest.fixture
def client():
    """Cliente de test sincrono."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Cliente de test asincrono (httpx)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_state():
    """Resetea el StateManager antes de cada test."""
    state_manager.set_led(False)
    StateManager.__init__(state_manager)  # type: ignore
    yield
