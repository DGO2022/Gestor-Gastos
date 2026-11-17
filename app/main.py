"""Punto de entrada de la API."""

import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import db, esquemas
from app.config import ANIO_MINIMO
from app.esquemas import DatosInvalidos, Gasto, GastoEntrada, TotalCategoria, TotalMes


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    """Prepara la base de datos antes de atender la primera petición."""
    db.inicializar()
    yield


app = FastAPI(
    title="Gestor de gastos",
    version="1.0.0",
    lifespan=ciclo_de_vida,
    responses={422: {"model": DatosInvalidos, "description": "Datos inválidos"}},
)

# Tipos reutilizables para los parámetros de las rutas.
Conexion = Annotated[sqlite3.Connection, Depends(db.obtener_conexion)]
IdGasto = Annotated[int, Path(ge=1, le=2**63 - 1)]  # el mayor entero que admite SQLite
Mes = Annotated[
    str | None,
    Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$", description="Mes en formato AAAA-MM"),
]
Anio = Annotated[int | None, Query(ge=ANIO_MINIMO, le=9999, description="Año; si falta, el actual")]


# --- Errores -------------------------------------------------------------

CUERPO = "cuerpo"
MENSAJES = {
    CUERPO: "Se esperaba un objeto JSON con monto, categoria, fecha y nota",
    "gasto_id": "El id del gasto debe ser un número entero positivo",
    "mes": "El mes debe tener el formato AAAA-MM",
    "anio": f"El año debe ser un número entre {ANIO_MINIMO} y 9999",
}


@app.exception_handler(RequestValidationError)
async def datos_invalidos(_: Request, error: RequestValidationError) -> JSONResponse:
    """Responde 422 con una lista de {campo, mensaje} en español, lista para mostrar."""
    detalle = []
    for fallo in error.errors():
        lugar = fallo["loc"]  # p. ej. ("body", "monto") o ("query", "mes")
        campo = lugar[1] if len(lugar) > 1 and isinstance(lugar[1], str) else CUERPO
        if fallo["type"] == "dato_invalido":  # una regla de app/esquemas.py
            mensaje = fallo["msg"]
        elif fallo["type"] == "missing" and campo != CUERPO:
            mensaje = "Este campo es obligatorio"
        else:
            mensaje = MENSAJES.get(campo, "Valor no válido")
        detalle.append({"campo": campo, "mensaje": mensaje})
    return JSONResponse(status_code=422, content={"detail": detalle})


def _o_404(gasto: dict | None) -> dict:
    if gasto is None:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return gasto


# --- Rutas ---------------------------------------------------------------


@app.get("/api/salud")
def salud() -> dict[str, str]:
    """Comprobación rápida de que el servidor responde."""
    return {"estado": "ok"}


@app.get("/api/gastos", response_model=list[Gasto])
def listar_gastos(conexion: Conexion, mes: Mes = None):
    """Gastos del más reciente al más antiguo. Con `mes`, solo los de ese mes."""
    return db.listar_gastos(conexion, mes)


@app.post("/api/gastos", response_model=Gasto, status_code=201)
def crear_gasto(gasto: GastoEntrada, conexion: Conexion):
    return db.crear_gasto(conexion, gasto)


@app.get("/api/gastos/{gasto_id}", response_model=Gasto)
def obtener_gasto(gasto_id: IdGasto, conexion: Conexion):
    return _o_404(db.obtener_gasto(conexion, gasto_id))


@app.put("/api/gastos/{gasto_id}", response_model=Gasto)
def actualizar_gasto(gasto_id: IdGasto, gasto: GastoEntrada, conexion: Conexion):
    """Reemplaza el gasto completo: se envían los mismos datos que al crearlo."""
    return _o_404(db.actualizar_gasto(conexion, gasto_id, gasto))


@app.delete("/api/gastos/{gasto_id}", status_code=204)
def borrar_gasto(gasto_id: IdGasto, conexion: Conexion) -> None:
    if not db.borrar_gasto(conexion, gasto_id):
        raise HTTPException(status_code=404, detail="Gasto no encontrado")


@app.get("/api/resumen/mensual", response_model=list[TotalMes])
def resumen_mensual(conexion: Conexion, anio: Anio = None):
    """Total gastado en cada uno de los 12 meses del año (el actual si no se indica)."""
    return db.resumen_mensual(conexion, anio or esquemas.hoy().year)


@app.get("/api/resumen/categorias", response_model=list[TotalCategoria])
def resumen_por_categoria(conexion: Conexion, mes: Mes = None):
    """Total gastado por categoría, de mayor a menor. Con `mes`, solo el de ese mes."""
    return db.resumen_por_categoria(conexion, mes)
