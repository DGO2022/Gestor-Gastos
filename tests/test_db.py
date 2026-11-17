"""La base de datos: se crea sola y protege la integridad de los datos."""

import sqlite3
from contextlib import closing

import pytest

from app import db

INSERTAR = "INSERT INTO gastos (monto_centimos, categoria, fecha) VALUES (?, ?, ?)"


def test_al_arrancar_la_app_se_crea_la_tabla(cliente, ruta_db):
    assert ruta_db.exists()

    with closing(sqlite3.connect(ruta_db)) as conexion:
        columnas = [fila[1] for fila in conexion.execute("PRAGMA table_info(gastos)")]

    assert columnas == ["id", "monto_centimos", "categoria", "fecha", "nota"]


def test_inicializar_dos_veces_no_borra_datos(conexion):
    with conexion:
        conexion.execute(INSERTAR, (1250, "Otros", "2026-01-15"))

    db.inicializar()

    assert conexion.execute("SELECT COUNT(*) FROM gastos").fetchone()[0] == 1


def test_crea_la_carpeta_de_la_base_si_no_existe(tmp_path, monkeypatch):
    ruta = tmp_path / "datos" / "nuevos" / "gastos.db"
    monkeypatch.setenv("GASTOS_DB", str(ruta))

    db.inicializar()

    assert ruta.exists()


@pytest.mark.parametrize("centimos", [0, -500])
def test_la_base_rechaza_montos_que_no_son_positivos(conexion, centimos):
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute(INSERTAR, (centimos, "Otros", "2026-01-15"))


@pytest.mark.parametrize("fecha", ["15/01/2026", "2026-1-5", "ayer", ""])
def test_la_base_rechaza_fechas_mal_formadas(conexion, fecha):
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute(INSERTAR, (1250, "Otros", fecha))


def test_la_nota_es_opcional_y_queda_vacia(conexion):
    with conexion:
        conexion.execute(INSERTAR, (1250, "Otros", "2026-01-15"))

    assert conexion.execute("SELECT nota FROM gastos").fetchone()["nota"] == ""


def test_el_id_de_un_gasto_borrado_no_se_reutiliza(conexion):
    with conexion:
        primero = conexion.execute(INSERTAR, (1250, "Otros", "2026-01-15")).lastrowid
        conexion.execute("DELETE FROM gastos WHERE id = ?", (primero,))
        segundo = conexion.execute(INSERTAR, (990, "Otros", "2026-01-16")).lastrowid

    assert segundo > primero
