"""Ajustes de la app. Todo lo configurable vive aquí."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def ruta_db() -> Path:
    """Archivo SQLite donde se guardan los gastos.

    Se puede cambiar con la variable de entorno GASTOS_DB. Se lee en cada
    llamada (no al importar) para que los tests usen su propia base de datos.
    """
    return Path(os.environ.get("GASTOS_DB") or RAIZ / "gastos.db")
