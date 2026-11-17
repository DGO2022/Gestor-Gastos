"""Ajustes que la web lee al cargar."""

import pytest

from app.config import CATEGORIAS


def test_config_expone_las_reglas_que_necesita_la_web(cliente):
    respuesta = cliente.get("/api/config")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "moneda": "S/",
        "categorias": list(CATEGORIAS),
        "nota_max_caracteres": 200,
        "anio_minimo": 2000,
    }


@pytest.mark.parametrize(
    ("variable", "esperado"),
    [("$", "$"), ("  €  ", "€"), ("Bs.", "Bs."), ("", "S/"), ("   ", "S/")],
)
def test_la_moneda_se_cambia_con_una_variable_de_entorno(cliente, monkeypatch, variable, esperado):
    monkeypatch.setenv("GASTOS_MONEDA", variable)

    assert cliente.get("/api/config").json()["moneda"] == esperado


def test_todas_las_categorias_de_config_se_pueden_usar(cliente, crear):
    for categoria in cliente.get("/api/config").json()["categorias"]:
        assert crear(categoria=categoria)["categoria"] == categoria
