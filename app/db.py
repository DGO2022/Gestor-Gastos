"""Acceso a SQLite: conexión y esquema."""

import sqlite3
from contextlib import closing

from app import config

# Los montos se guardan en céntimos enteros: sumar decimales con coma flotante
# da errores de redondeo (0.1 + 0.2 != 0.3) y con dinero eso no es aceptable.
# AUTOINCREMENT evita que el id de un gasto borrado se reutilice en otro.
ESQUEMA = """
CREATE TABLE IF NOT EXISTS gastos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    monto_centimos INTEGER NOT NULL CHECK (monto_centimos > 0),
    categoria      TEXT    NOT NULL,
    fecha          TEXT    NOT NULL
                   CHECK (fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    nota           TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos (fecha);
"""


def conectar() -> sqlite3.Connection:
    """Abre una conexión nueva. Quien la abre es responsable de cerrarla."""
    # check_same_thread=False: FastAPI puede abrir la conexión en un hilo y
    # usarla en otro dentro de la misma petición. Es seguro porque cada
    # petición tiene su propia conexión y nunca se comparte.
    conexion = sqlite3.connect(config.ruta_db(), check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar() -> None:
    """Crea el archivo y la tabla si aún no existen. Se puede llamar varias veces."""
    config.ruta_db().parent.mkdir(parents=True, exist_ok=True)
    with closing(conectar()) as conexion:
        conexion.executescript(ESQUEMA)
