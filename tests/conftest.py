"""Piezas compartidas por todos los tests."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import db, esquemas
from app.main import app

HOY = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """Congela "hoy" para que ningún test dependa del día en que se ejecuta."""
    monkeypatch.setattr(esquemas, "hoy", lambda: HOY)


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


@pytest.fixture
def crear(cliente):
    """Crea un gasto válido por la API; cada test cambia solo lo que le interesa."""

    def _crear(**cambios) -> dict:
        datos = {
            "monto": "25.50",
            "categoria": "Alimentación",
            "fecha": "2026-06-10",
            "nota": "Almuerzo",
        } | cambios
        respuesta = cliente.post("/api/gastos", json=datos)
        assert respuesta.status_code == 201, respuesta.text
        return respuesta.json()

    return _crear
