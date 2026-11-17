"""Ajustes y reglas de negocio. Todo lo configurable vive aquí."""

import os
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Lista cerrada: así los gráficos no se fragmentan por erratas
# ("comida", "Comida", "comidas"...). Para añadir una categoría, edita esta lista.
CATEGORIAS = (
    "Alimentación",
    "Transporte",
    "Vivienda",
    "Servicios",
    "Salud",
    "Educación",
    "Ocio",
    "Ropa",
    "Otros",
)

MONTO_MAXIMO = Decimal("99999999.99")
NOTA_MAX_CARACTERES = 200
ANIO_MINIMO = 2000  # frena erratas como 0202-11-17


def ruta_db() -> Path:
    """Archivo SQLite donde se guardan los gastos.

    Se puede cambiar con la variable de entorno GASTOS_DB. Se lee en cada
    llamada (no al importar) para que los tests usen su propia base de datos.
    """
    return Path(os.environ.get("GASTOS_DB") or RAIZ / "gastos.db")
