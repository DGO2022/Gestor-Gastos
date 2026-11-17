"""La página web y sus archivos se sirven desde la propia app."""

import re

import pytest

from app.config import CARPETA_WEB

INDEX = (CARPETA_WEB / "index.html").read_text(encoding="utf-8")
ARCHIVOS_ENLAZADOS = sorted(set(re.findall(r'(?:src|href)="(/static/[^"]+)"', INDEX)))


def test_la_raiz_devuelve_la_pagina(cliente):
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "<title>Gestor de gastos</title>" in respuesta.text


def test_la_pagina_enlaza_su_estilo_y_su_script():
    assert "/static/estilos.css" in ARCHIVOS_ENLAZADOS
    assert "/static/app.js" in ARCHIVOS_ENLAZADOS


@pytest.mark.parametrize("ruta", ARCHIVOS_ENLAZADOS)
def test_cada_archivo_que_enlaza_la_pagina_existe(cliente, ruta):
    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 200
    assert respuesta.content


def test_la_pagina_no_depende_de_internet():
    """Sin CDN ni recursos externos: la app funciona sin conexión."""
    assert not re.findall(r'(?:src|href)="(?:https?:)?//', INDEX)


@pytest.mark.parametrize("ruta", ["/", "/static/app.js", "/api/gastos"])
def test_el_navegador_siempre_comprueba_si_hay_version_nueva(cliente, ruta):
    assert cliente.get(ruta).headers["cache-control"] == "no-cache"


def test_un_archivo_que_no_existe_devuelve_404(cliente):
    assert cliente.get("/static/no-existe.js").status_code == 404


def test_no_se_puede_salir_de_la_carpeta_web(cliente):
    respuesta = cliente.get("/static/../config.py")

    assert respuesta.status_code == 404
    assert "ruta_db" not in respuesta.text
