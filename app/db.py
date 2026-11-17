"""Acceso a SQLite: conexión, esquema y consultas."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing

from app import config
from app.esquemas import GastoEntrada

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


def obtener_conexion() -> Iterator[sqlite3.Connection]:
    """Dependencia de FastAPI: una conexión por petición, que siempre se cierra."""
    conexion = conectar()
    try:
        yield conexion
    finally:
        conexion.close()


# --- Consultas -----------------------------------------------------------

_COLUMNAS = "id, monto_centimos, categoria, fecha, nota"


def _a_gasto(fila: sqlite3.Row) -> dict:
    """Fila de la tabla -> gasto como lo devuelve la API (monto en unidades, no céntimos)."""
    return {
        "id": fila["id"],
        "monto": fila["monto_centimos"] / 100,
        "categoria": fila["categoria"],
        "fecha": fila["fecha"],
        "nota": fila["nota"],
    }


def _a_fila(gasto: GastoEntrada) -> tuple[int, str, str, str]:
    """Gasto ya validado -> valores listos para guardar (monto en céntimos)."""
    return int(gasto.monto * 100), gasto.categoria, gasto.fecha.isoformat(), gasto.nota


def _filtro_mes(mes: str | None) -> tuple[str, tuple[str, ...]]:
    """Condición SQL para quedarse con un mes "AAAA-MM" (o con todo si no se indica)."""
    if mes is None:
        return "", ()
    # Las fechas ISO se ordenan igual como texto que como fecha, y así se usa el índice.
    return " WHERE fecha BETWEEN ? AND ?", (f"{mes}-01", f"{mes}-31")


def listar_gastos(conexion: sqlite3.Connection, mes: str | None = None) -> list[dict]:
    """Gastos del más reciente al más antiguo, opcionalmente de un solo mes."""
    donde, parametros = _filtro_mes(mes)
    filas = conexion.execute(
        f"SELECT {_COLUMNAS} FROM gastos{donde} ORDER BY fecha DESC, id DESC", parametros
    )
    return [_a_gasto(fila) for fila in filas]


def obtener_gasto(conexion: sqlite3.Connection, gasto_id: int) -> dict | None:
    fila = conexion.execute(f"SELECT {_COLUMNAS} FROM gastos WHERE id = ?", (gasto_id,)).fetchone()
    return _a_gasto(fila) if fila else None


def crear_gasto(conexion: sqlite3.Connection, gasto: GastoEntrada) -> dict:
    with conexion:  # confirma la transacción, o la deshace si algo falla
        cursor = conexion.execute(
            "INSERT INTO gastos (monto_centimos, categoria, fecha, nota) VALUES (?, ?, ?, ?)",
            _a_fila(gasto),
        )
    return obtener_gasto(conexion, cursor.lastrowid)
