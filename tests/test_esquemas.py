"""Reglas de validación de un gasto, probadas sin pasar por HTTP.

En los tests "hoy" siempre es 2026-06-15 (lo fija conftest.py).
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.config import CATEGORIAS
from app.esquemas import GastoEntrada

VALIDO = {"monto": "25.50", "categoria": "Alimentación", "fecha": "2026-06-10", "nota": "Almuerzo"}


def validar(**cambios) -> GastoEntrada:
    return GastoEntrada.model_validate(VALIDO | cambios)


def mensaje_de_error(**cambios) -> str:
    """Valida un gasto con un único dato malo y devuelve el mensaje de ese error."""
    with pytest.raises(ValidationError) as info:
        validar(**cambios)
    errores = info.value.errors()
    assert len(errores) == 1, errores
    assert errores[0]["loc"] == tuple(cambios), errores
    return errores[0]["msg"]


def test_un_gasto_valido_queda_normalizado():
    gasto = validar()

    assert gasto.monto == Decimal("25.50")
    assert gasto.categoria == "Alimentación"
    assert gasto.fecha == date(2026, 6, 10)
    assert gasto.nota == "Almuerzo"


# --- monto ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (10, "10.00"),
        (10.5, "10.50"),
        ("10.50", "10.50"),
        (" 10.5 ", "10.50"),
        ("12.500", "12.50"),
        ("+7", "7.00"),
        ("0.01", "0.01"),
        ("99999999.99", "99999999.99"),
    ],
)
def test_monto_acepta_numeros_y_textos_numericos(entrada, esperado):
    monto = validar(monto=entrada).monto

    assert monto == Decimal(esperado)
    assert str(monto) == esperado  # siempre con 2 decimales


@pytest.mark.parametrize(("entrada", "esperado"), [(19.99, "19.99"), (0.1, "0.10"), (1.15, "1.15")])
def test_monto_decimal_de_json_no_pierde_precision(entrada, esperado):
    assert str(validar(monto=entrada).monto) == esperado


@pytest.mark.parametrize("entrada", [0, 0.0, "0", "0.00", -5, -0.01, "-5", "-0"])
def test_monto_debe_ser_mayor_que_cero(entrada):
    assert mensaje_de_error(monto=entrada) == "El monto debe ser mayor que 0"


@pytest.mark.parametrize(
    "entrada",
    [
        "abc",
        "",
        "   ",
        "12,50",
        "1e3",
        "1_000",
        ".5",
        "5.",
        "١٢",
        "NaN",
        "Infinity",
        None,
        True,
        False,
        [],
        {},
        [10],
        float("nan"),
        float("inf"),
    ],
)
def test_monto_debe_ser_un_numero(entrada):
    assert mensaje_de_error(monto=entrada) == "El monto debe ser un número, por ejemplo 12.50"


@pytest.mark.parametrize("entrada", ["10.999", "0.001", 10.005, 1e-7, "25.5000001"])
def test_monto_admite_como_maximo_dos_decimales(entrada):
    assert mensaje_de_error(monto=entrada) == "El monto admite como máximo 2 decimales"


@pytest.mark.parametrize("entrada", ["100000000", "99999999.991", 1e12, 1e300, 10**400, "9" * 5000])
def test_monto_tiene_un_tope(entrada):
    assert mensaje_de_error(monto=entrada) == "El monto no puede superar 99,999,999.99"


# --- categoría -----------------------------------------------------------


@pytest.mark.parametrize("categoria", CATEGORIAS)
def test_categoria_acepta_las_de_la_lista(categoria):
    assert validar(categoria=categoria).categoria == categoria


@pytest.mark.parametrize("entrada", ["Comida", "alimentación", " Salud ", "", None, 5, ["Salud"]])
def test_categoria_fuera_de_la_lista_se_rechaza(entrada):
    mensaje = mensaje_de_error(categoria=entrada)

    assert mensaje.startswith("Categoría no válida. Opciones: Alimentación, Transporte")
    assert mensaje.endswith("Otros")


# --- fecha ---------------------------------------------------------------


@pytest.mark.parametrize("entrada", ["2026-06-15", "2026-06-14", "2024-02-29", "2000-01-01"])
def test_fecha_acepta_desde_el_anio_2000_hasta_hoy(entrada):
    assert validar(fecha=entrada).fecha == date.fromisoformat(entrada)


@pytest.mark.parametrize("entrada", ["2026-06-16", "2026-07-01", "2027-01-01", "9999-12-31"])
def test_fecha_no_puede_ser_futura(entrada):
    assert mensaje_de_error(fecha=entrada) == "La fecha no puede ser futura"


@pytest.mark.parametrize("entrada", ["1999-12-31", "0202-11-17", "0001-01-01"])
def test_fecha_no_puede_ser_anterior_al_2000(entrada):
    assert mensaje_de_error(fecha=entrada) == "La fecha no puede ser anterior al año 2000"


@pytest.mark.parametrize(
    "entrada",
    [
        "15/06/2026",
        "2026-6-1",
        "20260610",
        "2026-06-10T10:00:00",
        " 2026-06-10",
        "2026-W24-1",
        "ayer",
        "",
        None,
        20260610,
        1781049600,
        True,
        ["2026-06-10"],
    ],
)
def test_fecha_exige_formato_iso(entrada):
    assert mensaje_de_error(fecha=entrada) == "La fecha debe tener el formato AAAA-MM-DD"


@pytest.mark.parametrize(
    "entrada", ["2026-02-30", "2025-02-29", "2026-13-01", "2026-00-10", "0000-01-01"]
)
def test_fecha_debe_existir_en_el_calendario(entrada):
    assert mensaje_de_error(fecha=entrada) == "Esa fecha no existe en el calendario"


# --- nota ----------------------------------------------------------------


def test_nota_es_opcional():
    sin_nota = {clave: valor for clave, valor in VALIDO.items() if clave != "nota"}

    assert GastoEntrada.model_validate(sin_nota).nota == ""


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(None, ""), ("", ""), ("   ", ""), ("  Taxi al centro \n", "Taxi al centro")],
)
def test_nota_se_limpia_de_espacios_sobrantes(entrada, esperado):
    assert validar(nota=entrada).nota == esperado


def test_nota_admite_hasta_200_caracteres():
    assert validar(nota="x" * 200).nota == "x" * 200
    assert (
        validar(nota="  " + "ñ" * 200 + "  ").nota == "ñ" * 200
    )  # los espacios de los bordes no cuentan


def test_nota_de_mas_de_200_caracteres_se_rechaza():
    assert mensaje_de_error(nota="x" * 201) == "La nota no puede superar los 200 caracteres"


@pytest.mark.parametrize("entrada", [123, 1.5, True, ["nota"], {"texto": "nota"}])
def test_nota_debe_ser_texto(entrada):
    assert mensaje_de_error(nota=entrada) == "La nota debe ser un texto"


# --- el gasto completo ---------------------------------------------------


@pytest.mark.parametrize("campo", ["monto", "categoria", "fecha"])
def test_monto_categoria_y_fecha_son_obligatorios(campo):
    incompleto = {clave: valor for clave, valor in VALIDO.items() if clave != campo}

    with pytest.raises(ValidationError) as info:
        GastoEntrada.model_validate(incompleto)

    (error,) = info.value.errors()
    assert error["loc"] == (campo,)
    assert error["type"] == "missing"


def test_se_informan_todos_los_errores_a_la_vez():
    with pytest.raises(ValidationError) as info:
        validar(monto=-1, categoria="Comida", fecha="mañana", nota=5)

    assert {error["loc"][0] for error in info.value.errors()} == {
        "monto",
        "categoria",
        "fecha",
        "nota",
    }


def test_los_campos_desconocidos_se_ignoran():
    gasto = validar(id=99, moneda="USD")

    assert gasto.model_dump().keys() == {"monto", "categoria", "fecha", "nota"}
