"""Los resúmenes que alimentan los gráficos: total por mes y por categoría.

En los tests "hoy" siempre es 2026-06-15 (lo fija conftest.py).
"""

import pytest

MENSUAL = "/api/resumen/mensual"
CATEGORIAS = "/api/resumen/categorias"


# --- total por mes -------------------------------------------------------


def test_mensual_devuelve_los_12_meses_aunque_no_haya_gastos(cliente):
    respuesta = cliente.get(MENSUAL, params={"anio": 2026})

    assert respuesta.status_code == 200
    assert respuesta.json() == [
        {"mes": f"2026-{numero:02d}", "total": 0.0, "cantidad": 0} for numero in range(1, 13)
    ]


def test_mensual_suma_los_gastos_de_cada_mes(cliente, crear):
    crear(fecha="2026-01-01", monto="10.10")
    crear(fecha="2026-01-31", monto="20.20")
    crear(fecha="2026-03-15", monto="5")
    crear(fecha="2025-12-31", monto="999")  # otro año: no debe contar

    meses = {mes["mes"]: mes for mes in cliente.get(MENSUAL, params={"anio": 2026}).json()}

    assert meses["2026-01"] == {"mes": "2026-01", "total": 30.3, "cantidad": 2}
    assert meses["2026-03"] == {"mes": "2026-03", "total": 5.0, "cantidad": 1}
    assert sum(mes["cantidad"] for mes in meses.values()) == 3


def test_mensual_separa_los_anios(cliente, crear):
    crear(fecha="2025-12-31", monto="999")
    crear(fecha="2026-01-01", monto="1")

    diciembre_2025 = cliente.get(MENSUAL, params={"anio": 2025}).json()[11]

    assert diciembre_2025 == {"mes": "2025-12", "total": 999.0, "cantidad": 1}


def test_mensual_sin_anio_usa_el_actual(cliente, crear):
    crear(fecha="2026-06-10", monto="7")
    crear(fecha="2025-06-10", monto="100")

    meses = cliente.get(MENSUAL).json()

    assert [mes["mes"] for mes in meses] == [f"2026-{numero:02d}" for numero in range(1, 13)]
    assert meses[5] == {"mes": "2026-06", "total": 7.0, "cantidad": 1}


def test_los_totales_no_arrastran_errores_de_redondeo(cliente, crear):
    # Con coma flotante, 0.1 + 0.2 da 0.30000000000000004. Sumando céntimos enteros, no.
    crear(fecha="2026-06-01", monto=0.1, categoria="Otros")
    crear(fecha="2026-06-02", monto=0.2, categoria="Otros")

    junio = cliente.get(MENSUAL, params={"anio": 2026}).json()[5]
    (otros,) = cliente.get(CATEGORIAS, params={"mes": "2026-06"}).json()

    assert junio["total"] == 0.3
    assert otros["total"] == 0.3


@pytest.mark.parametrize("anio", ["1999", "10000", "-2026", "abc", "2026.5", ""])
def test_mensual_con_un_anio_no_valido_devuelve_422(cliente, anio):
    respuesta = cliente.get(MENSUAL, params={"anio": anio})

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": [{"campo": "anio", "mensaje": "El año debe ser un número entre 2000 y 9999"}]
    }


# --- total por categoría -------------------------------------------------


def test_categorias_sin_gastos_devuelve_una_lista_vacia(cliente):
    respuesta = cliente.get(CATEGORIAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_categorias_suma_y_ordena_de_mayor_a_menor(cliente, crear):
    crear(categoria="Transporte", monto="15")
    crear(categoria="Alimentación", monto="40.50")
    crear(categoria="Alimentación", monto="9.75")
    crear(categoria="Ocio", monto="120")

    assert cliente.get(CATEGORIAS).json() == [
        {"categoria": "Ocio", "total": 120.0, "cantidad": 1},
        {"categoria": "Alimentación", "total": 50.25, "cantidad": 2},
        {"categoria": "Transporte", "total": 15.0, "cantidad": 1},
    ]


def test_categorias_con_el_mismo_total_salen_en_orden_alfabetico(cliente, crear):
    crear(categoria="Salud", monto="30")
    crear(categoria="Ocio", monto="30")

    assert [fila["categoria"] for fila in cliente.get(CATEGORIAS).json()] == ["Ocio", "Salud"]


def test_categorias_por_mes_incluye_solo_ese_mes(cliente, crear):
    crear(fecha="2026-04-30", categoria="Ropa", monto="80")
    crear(fecha="2026-05-01", categoria="Salud", monto="20")
    crear(fecha="2026-05-31", categoria="Salud", monto="5")
    crear(fecha="2026-06-01", categoria="Ocio", monto="60")

    respuesta = cliente.get(CATEGORIAS, params={"mes": "2026-05"})

    assert respuesta.json() == [{"categoria": "Salud", "total": 25.0, "cantidad": 2}]


def test_categorias_sin_mes_suma_todo_el_historial(cliente, crear):
    crear(fecha="2025-01-10", categoria="Salud", monto="10")
    crear(fecha="2026-06-10", categoria="Salud", monto="15")

    assert cliente.get(CATEGORIAS).json() == [{"categoria": "Salud", "total": 25.0, "cantidad": 2}]


@pytest.mark.parametrize("mes", ["2026-13", "2026-6", "junio", ""])
def test_categorias_con_un_mes_mal_escrito_devuelve_422(cliente, mes):
    respuesta = cliente.get(CATEGORIAS, params={"mes": mes})

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"][0]["campo"] == "mes"


# --- coherencia ----------------------------------------------------------


def test_los_resumenes_reflejan_ediciones_y_borrados(cliente, crear):
    editado = crear(fecha="2026-06-10", categoria="Ocio", monto="50")
    borrado = crear(fecha="2026-06-11", categoria="Ocio", monto="30")
    crear(fecha="2026-06-12", categoria="Ocio", monto="20")

    cliente.put(
        f"/api/gastos/{editado['id']}",
        json={"monto": "45", "categoria": "Salud", "fecha": "2026-05-10"},
    )
    cliente.delete(f"/api/gastos/{borrado['id']}")

    meses = cliente.get(MENSUAL, params={"anio": 2026}).json()
    assert meses[4] == {"mes": "2026-05", "total": 45.0, "cantidad": 1}
    assert meses[5] == {"mes": "2026-06", "total": 20.0, "cantidad": 1}
    assert cliente.get(CATEGORIAS, params={"mes": "2026-06"}).json() == [
        {"categoria": "Ocio", "total": 20.0, "cantidad": 1}
    ]


def test_el_listado_y_los_dos_resumenes_cuadran_entre_si(cliente, crear):
    for monto, categoria in [("19.99", "Ocio"), ("0.01", "Otros"), ("1234.56", "Vivienda")]:
        crear(fecha="2026-06-10", monto=monto, categoria=categoria)

    centimos_listado = sum(
        round(gasto["monto"] * 100)
        for gasto in cliente.get("/api/gastos", params={"mes": "2026-06"}).json()
    )
    junio = cliente.get(MENSUAL, params={"anio": 2026}).json()[5]
    por_categoria = cliente.get(CATEGORIAS, params={"mes": "2026-06"}).json()

    assert centimos_listado == 125456
    assert junio["total"] == 1254.56
    assert round(sum(fila["total"] for fila in por_categoria), 2) == 1254.56
