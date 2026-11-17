"""Qué datos acepta la API y qué reglas deben cumplir."""

import math
import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from app.config import ANIO_MINIMO, CATEGORIAS, MONTO_MAXIMO, NOTA_MAX_CARACTERES

DOS_DECIMALES = Decimal("0.01")
_NUMERO = re.compile(r"[+-]?[0-9]+(\.[0-9]+)?")
_FECHA_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def hoy() -> date:
    """Fecha actual del equipo. Va en una función para poder fijarla en los tests."""
    return date.today()


def _invalido(mensaje: str) -> PydanticCustomError:
    """Error de validación con un mensaje pensado para mostrarse tal cual al usuario."""
    return PydanticCustomError("dato_invalido", "{mensaje}", {"mensaje": mensaje})


def _a_decimal(valor: object) -> Decimal | None:
    """Convierte a Decimal exacto; devuelve None si no es un número válido."""
    if isinstance(valor, bool):  # en Python, True y False también son int
        return None
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, float):
        # repr() da el número tal como se escribió (19.99), no su binario (19.98999...).
        return Decimal(repr(valor)) if math.isfinite(valor) else None
    if isinstance(valor, str) and _NUMERO.fullmatch(valor.strip()):
        return Decimal(valor.strip())
    return None


class GastoEntrada(BaseModel):
    """Datos para crear o editar un gasto."""

    monto: Decimal
    categoria: str = Field(json_schema_extra={"enum": list(CATEGORIAS)})
    fecha: date
    nota: str = ""

    @field_validator("monto", mode="before")
    @classmethod
    def _validar_monto(cls, valor: object) -> Decimal:
        monto = _a_decimal(valor)
        if monto is None:
            raise _invalido("El monto debe ser un número, por ejemplo 12.50")
        if monto <= 0:
            raise _invalido("El monto debe ser mayor que 0")
        if monto > MONTO_MAXIMO:
            raise _invalido(f"El monto no puede superar {MONTO_MAXIMO:,}")
        if monto != monto.quantize(DOS_DECIMALES):
            raise _invalido("El monto admite como máximo 2 decimales")
        return monto.quantize(DOS_DECIMALES)

    @field_validator("categoria", mode="before")
    @classmethod
    def _validar_categoria(cls, valor: object) -> str:
        if valor not in CATEGORIAS:
            raise _invalido("Elige una categoría de la lista")
        return valor

    @field_validator("fecha", mode="before")
    @classmethod
    def _validar_fecha(cls, valor: object) -> date:
        if not isinstance(valor, str) or not _FECHA_ISO.fullmatch(valor):
            raise _invalido("La fecha debe tener el formato AAAA-MM-DD")
        try:
            fecha = date.fromisoformat(valor)
        except ValueError:
            raise _invalido("Esa fecha no existe en el calendario") from None
        if fecha.year < ANIO_MINIMO:
            raise _invalido(f"La fecha no puede ser anterior al año {ANIO_MINIMO}")
        if fecha > hoy():
            raise _invalido("La fecha no puede ser futura")
        return fecha

    @field_validator("nota", mode="before")
    @classmethod
    def _validar_nota(cls, valor: object) -> str:
        if valor is None:
            return ""
        if not isinstance(valor, str):
            raise _invalido("La nota debe ser un texto")
        nota = valor.strip()
        if len(nota) > NOTA_MAX_CARACTERES:
            raise _invalido(f"La nota no puede superar los {NOTA_MAX_CARACTERES} caracteres")
        return nota


class Gasto(BaseModel):
    """Un gasto guardado, tal como lo devuelve la API."""

    id: int
    monto: float
    categoria: str
    fecha: date
    nota: str


class TotalMes(BaseModel):
    """Lo gastado en un mes ("AAAA-MM")."""

    mes: str
    total: float
    cantidad: int


class TotalCategoria(BaseModel):
    """Lo gastado en una categoría."""

    categoria: str
    total: float
    cantidad: int


class Configuracion(BaseModel):
    """Lo que la web necesita saber para pintar el formulario y los montos."""

    moneda: str
    categorias: list[str]
    nota_max_caracteres: int
    anio_minimo: int


class ErrorDeCampo(BaseModel):
    campo: str
    mensaje: str


class DatosInvalidos(BaseModel):
    """Cuerpo de las respuestas 422: un error por cada dato que no cumple las reglas."""

    detail: list[ErrorDeCampo]
