"""Punto de entrada de la API."""

from fastapi import FastAPI

app = FastAPI(title="Gestor de gastos", version="1.0.0")


@app.get("/api/salud")
def salud() -> dict[str, str]:
    """Comprobación rápida de que el servidor responde."""
    return {"estado": "ok"}
