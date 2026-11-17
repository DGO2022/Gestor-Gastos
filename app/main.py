"""Punto de entrada de la API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    """Prepara la base de datos antes de atender la primera petición."""
    db.inicializar()
    yield


app = FastAPI(title="Gestor de gastos", version="1.0.0", lifespan=ciclo_de_vida)


@app.get("/api/salud")
def salud() -> dict[str, str]:
    """Comprobación rápida de que el servidor responde."""
    return {"estado": "ok"}
