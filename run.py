"""Arranca el gestor de gastos con un solo comando:  python run.py

La primera vez crea un entorno virtual (.venv) e instala las dependencias.
Las siguientes veces arranca directamente.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ENTORNO = RAIZ / ".venv"
PYTHON = ENTORNO / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUISITOS = RAIZ / "requirements.txt"
MARCA = ENTORNO / "requisitos-instalados.txt"  # huella del requirements.txt ya instalado
VERSION_MINIMA = (3, 11)


def leer_opciones() -> argparse.Namespace:
    opciones = argparse.ArgumentParser(description="Arranca el gestor de gastos personales.")
    opciones.add_argument("--puerto", type=int, default=8000, help="puerto del servidor (8000)")
    opciones.add_argument("--moneda", help='símbolo de la moneda, por ejemplo "$" o "€" (S/)')
    return opciones.parse_args()


def preparar_entorno() -> None:
    """Crea .venv e instala las dependencias; no hace nada si ya están al día."""
    huella = hashlib.sha256(REQUISITOS.read_bytes()).hexdigest()
    if PYTHON.exists() and MARCA.exists() and MARCA.read_text().strip() == huella:
        return
    if not PYTHON.exists():
        print("Creando el entorno virtual (.venv)...")
        venv.create(ENTORNO, with_pip=True)
    print("Instalando dependencias (solo la primera vez)...")
    pip = [str(PYTHON), "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    subprocess.check_call([*pip, "-r", str(REQUISITOS)])
    MARCA.write_text(huella)


def main() -> int:
    if sys.version_info < VERSION_MINIMA:
        minima = ".".join(map(str, VERSION_MINIMA))
        print(f"Se necesita Python {minima} o superior (este es {sys.version.split()[0]}).")
        return 1
    opciones = leer_opciones()

    try:
        preparar_entorno()
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"\nNo se pudo preparar el entorno: {error}")
        print("- Revisa la conexión a internet (hace falta solo la primera vez).")
        print("- En Debian/Ubuntu puede faltar un paquete: sudo apt install python3-venv")
        print("- Si sigue fallando, borra la carpeta .venv y vuelve a ejecutar este comando.")
        return 1

    ajustes = os.environ.copy()
    if opciones.moneda:
        ajustes["GASTOS_MONEDA"] = opciones.moneda
    direccion = f"http://127.0.0.1:{opciones.puerto}"
    print(f"\nGestor de gastos listo en {direccion}  (Ctrl+C para detenerlo)\n")

    # 127.0.0.1: la app no tiene usuarios ni contraseña, así que solo se abre a este equipo.
    uvicorn = [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1"]
    servidor = subprocess.Popen([*uvicorn, "--port", str(opciones.puerto)], cwd=RAIZ, env=ajustes)
    try:
        codigo = servidor.wait()
    except KeyboardInterrupt:
        return servidor.wait()  # el servidor también recibe el Ctrl+C: se espera a que cierre bien
    if codigo != 0:
        print(f"\nEl servidor se detuvo con un error. Si el puerto {opciones.puerto} está ocupado,")
        print(f"prueba con otro:  python run.py --puerto {opciones.puerto + 1}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
