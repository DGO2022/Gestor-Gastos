"""Piezas compartidas por todos los tests."""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def ruta_db(tmp_path, monkeypatch):
    """Cada test usa su propio archivo SQLite, vacío y temporal."""
    ruta = tmp_path / "gastos-test.db"
    monkeypatch.setenv("GASTOS_DB", str(ruta))
    return ruta


@pytest.fixture
def cliente(ruta_db):
    """Cliente HTTP que habla con la app sin levantar un servidor real."""
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def conexion(ruta_db):
    """Conexión directa a la base de datos de pruebas, con la tabla ya creada."""
    db.inicializar()
    conexion = db.conectar()
    yield conexion
    conexion.close()
