"""La API de gastos de punta a punta: petición HTTP -> validación -> SQLite -> respuesta."""

import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app.main import app

# --- crear ---------------------------------------------------------------


def test_crear_devuelve_201_y_el_gasto_guardado(cliente):
    respuesta = cliente.post(
        "/api/gastos",
        json={"monto": 25.5, "categoria": "Alimentación", "fecha": "2026-06-10", "nota": " Menú "},
    )

    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id": 1,
        "monto": 25.5,
        "categoria": "Alimentación",
        "fecha": "2026-06-10",
        "nota": "Menú",
    }


def test_crear_sin_nota_la_deja_vacia(cliente):
    respuesta = cliente.post(
        "/api/gastos", json={"monto": "8", "categoria": "Transporte", "fecha": "2026-06-10"}
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["nota"] == ""


@pytest.mark.parametrize(
    ("monto", "centimos"), [(19.99, 1999), ("19.99", 1999), (0.1, 10), (1234567.89, 123456789)]
)
def test_el_monto_se_guarda_en_centimos_exactos(crear, ruta_db, monto, centimos):
    gasto = crear(monto=monto)

    with closing(sqlite3.connect(ruta_db)) as conexion:
        guardado = conexion.execute("SELECT monto_centimos FROM gastos").fetchone()[0]

    assert guardado == centimos
    assert gasto["monto"] == centimos / 100


def test_los_gastos_siguen_ahi_al_reiniciar_la_app(crear, ruta_db):
    creado = crear(nota="Persistente")

    with TestClient(app) as otra_sesion:
        assert otra_sesion.get("/api/gastos").json() == [creado]


# --- validación por HTTP -------------------------------------------------


def test_datos_invalidos_devuelven_422_con_campo_y_mensaje(cliente):
    respuesta = cliente.post(
        "/api/gastos", json={"monto": -5, "categoria": "Alimentación", "fecha": "2026-06-16"}
    )

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": [
            {"campo": "monto", "mensaje": "El monto debe ser mayor que 0"},
            {"campo": "fecha", "mensaje": "La fecha no puede ser futura"},
        ]
    }


def test_un_campo_obligatorio_ausente_devuelve_422(cliente):
    respuesta = cliente.post("/api/gastos", json={"monto": 10, "categoria": "Otros"})

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": [{"campo": "fecha", "mensaje": "Este campo es obligatorio"}]
    }


@pytest.mark.parametrize(
    "peticion",
    [
        {"content": "esto no es JSON", "headers": {"Content-Type": "application/json"}},
        {"content": '{"monto": 10,', "headers": {"Content-Type": "application/json"}},
        {"json": [1, 2, 3]},
        {"json": "texto"},
        {"json": None},
        {},
    ],
    ids=["texto", "json-cortado", "lista", "cadena", "null", "sin-cuerpo"],
)
def test_un_cuerpo_que_no_es_un_objeto_json_devuelve_422(cliente, peticion):
    respuesta = cliente.post("/api/gastos", **peticion)

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": [
            {
                "campo": "cuerpo",
                "mensaje": "Se esperaba un objeto JSON con monto, categoria, fecha y nota",
            }
        ]
    }


def test_un_numero_gigante_no_rompe_el_servidor(cliente):
    cuerpo = '{"monto": ' + "9" * 5000 + ', "categoria": "Otros", "fecha": "2026-06-10"}'

    respuesta = cliente.post(
        "/api/gastos", content=cuerpo, headers={"Content-Type": "application/json"}
    )

    assert 400 <= respuesta.status_code < 500  # error del cliente, nunca un 500


def test_un_gasto_invalido_no_se_guarda(cliente):
    cliente.post("/api/gastos", json={"monto": 0, "categoria": "Otros", "fecha": "2026-06-10"})

    assert cliente.get("/api/gastos").json() == []


# --- consultar uno -------------------------------------------------------


def test_obtener_un_gasto_por_su_id(cliente, crear):
    creado = crear()

    respuesta = cliente.get(f"/api/gastos/{creado['id']}")

    assert respuesta.status_code == 200
    assert respuesta.json() == creado


def test_obtener_un_gasto_que_no_existe_devuelve_404(cliente):
    respuesta = cliente.get("/api/gastos/999")

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Gasto no encontrado"}


@pytest.mark.parametrize("gasto_id", ["abc", "0", "-1", "1.5", str(2**63), "9" * 40])
def test_un_id_que_no_es_entero_positivo_devuelve_422(cliente, gasto_id):
    respuesta = cliente.get(f"/api/gastos/{gasto_id}")

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": [
            {"campo": "gasto_id", "mensaje": "El id del gasto debe ser un número entero positivo"}
        ]
    }


# --- listar --------------------------------------------------------------


def test_listar_sin_gastos_devuelve_una_lista_vacia(cliente):
    respuesta = cliente.get("/api/gastos")

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_listar_va_del_mas_reciente_al_mas_antiguo(cliente, crear):
    crear(fecha="2026-05-20", nota="antiguo")
    crear(fecha="2026-06-10", nota="reciente, creado primero")
    crear(fecha="2026-06-10", nota="reciente, creado después")

    notas = [gasto["nota"] for gasto in cliente.get("/api/gastos").json()]

    assert notas == ["reciente, creado después", "reciente, creado primero", "antiguo"]


def test_listar_por_mes_incluye_solo_ese_mes(cliente, crear):
    crear(fecha="2026-04-30", nota="abril, último día")
    crear(fecha="2026-05-01", nota="mayo, primer día")
    crear(fecha="2026-05-31", nota="mayo, último día")
    crear(fecha="2026-06-01", nota="junio, primer día")
    crear(fecha="2025-05-15", nota="mayo del año anterior")

    respuesta = cliente.get("/api/gastos", params={"mes": "2026-05"})

    assert respuesta.status_code == 200
    assert [gasto["nota"] for gasto in respuesta.json()] == ["mayo, último día", "mayo, primer día"]


def test_listar_un_mes_sin_gastos_devuelve_una_lista_vacia(cliente, crear):
    crear(fecha="2026-06-10")

    assert cliente.get("/api/gastos", params={"mes": "2026-02"}).json() == []


@pytest.mark.parametrize("mes", ["2026-13", "2026-00", "2026-6", "junio", "2026-06-10", "2026", ""])
def test_listar_con_un_mes_mal_escrito_devuelve_422(cliente, mes):
    respuesta = cliente.get("/api/gastos", params={"mes": mes})

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": [{"campo": "mes", "mensaje": "El mes debe tener el formato AAAA-MM"}]
    }
