"""Piezas compartidas por todos los tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def cliente():
    """Cliente HTTP que habla con la app sin levantar un servidor real."""
    with TestClient(app) as cliente:
        yield cliente
