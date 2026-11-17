"use strict";

/* Gestor de gastos: el navegador solo pinta. Las reglas y las sumas las hace el backend. */

const $ = (id) => document.getElementById(id);

const estado = {
  moneda: "",
  mesMinimo: "2000-01",
  mes: mesDeHoy(), // mes que se muestra, "AAAA-MM"
  editando: null, // id del gasto que se está editando, o null
  gastos: [],
};

// --- Fechas y formato ------------------------------------------------------

function dosDigitos(numero) {
  return String(numero).padStart(2, "0");
}

/** Hoy como "AAAA-MM-DD" en hora local. (toISOString() da la fecha UTC, que de noche ya es mañana.) */
function hoy() {
  const fecha = new Date();
  return `${fecha.getFullYear()}-${dosDigitos(fecha.getMonth() + 1)}-${dosDigitos(fecha.getDate())}`;
}

function mesDeHoy() {
  return hoy().slice(0, 7);
}

/** "2026-12" + 1 -> "2027-01". */
function moverMes(mes, pasos) {
  const [anio, numero] = mes.split("-").map(Number);
  const indice = anio * 12 + (numero - 1) + pasos;
  return `${Math.floor(indice / 12)}-${dosDigitos((indice % 12) + 1)}`;
}

const formatoMes = new Intl.DateTimeFormat("es", { month: "long", year: "numeric" });

/** "2026-11" -> "noviembre de 2026". */
function nombreDeMes(mes) {
  const [anio, numero] = mes.split("-").map(Number);
  return formatoMes.format(new Date(anio, numero - 1, 1));
}

function conMayuscula(texto) {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** "2026-11-05" -> "05/11/2026". Sin pasar por Date, que la movería de día según la zona horaria. */
function fechaLegible(fecha) {
  const [anio, mes, dia] = fecha.split("-");
  return `${dia}/${mes}/${anio}`;
}

const formatoNumero = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 1234.5 -> "S/ 1,234.50" (los separadores siguen el idioma del navegador). */
function dinero(monto) {
  return `${estado.moneda} ${formatoNumero.format(monto)}`;
}

function cuantosGastos(cantidad) {
  if (cantidad === 0) return "sin gastos";
  return cantidad === 1 ? "1 gasto" : `${cantidad} gastos`;
}

// --- Comunicación con la API -----------------------------------------------

class ErrorDeApi extends Error {
  /** `detalle` es un texto (404, red...) o la lista [{campo, mensaje}] de un 422. */
  constructor(detalle) {
    super(typeof detalle === "string" ? detalle : "Revisa los datos marcados.");
    this.campos = Array.isArray(detalle) ? detalle : [];
  }
}

async function api(metodo, ruta, cuerpo) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      method: metodo,
      headers: cuerpo ? { "Content-Type": "application/json" } : undefined,
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ErrorDeApi("No se pudo conectar con el servidor. ¿Sigue en marcha?");
  }
  if (respuesta.status === 204) return null;
  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    throw new ErrorDeApi(datos?.detail ?? `El servidor respondió con un error (${respuesta.status}).`);
  }
  return datos;
}

// --- Avisos y errores ------------------------------------------------------

function avisar(texto, tipo = "ok") {
  $("aviso").textContent = texto;
  $("aviso").className = texto ? `aviso ${tipo}` : "aviso";
}

function limpiarErrores() {
  for (const campo of ["monto", "categoria", "fecha", "nota"]) {
    $(`error-${campo}`).textContent = "";
    $(campo).removeAttribute("aria-invalid");
  }
}

/** Pone cada error del backend bajo su campo; lo que no sea de un campo va al aviso general. */
function mostrarError(error) {
  if (!(error instanceof ErrorDeApi)) throw error; // fallo de programación: que se vea en la consola
  const generales = [];
  for (const { campo, mensaje } of error.campos) {
    const destino = $(`error-${campo}`);
    if (destino) {
      destino.textContent = mensaje;
      $(campo).setAttribute("aria-invalid", "true");
    } else {
      generales.push(mensaje);
    }
  }
  avisar(generales.length ? generales.join(" ") : error.message, "error");
  document.querySelector("#formulario [aria-invalid='true']")?.focus();
}

// --- Pintar ----------------------------------------------------------------

/** Crea un elemento. El texto siempre entra por textContent: nunca se interpreta como HTML. */
function el(etiqueta, propiedades = {}, ...hijos) {
  const nodo = Object.assign(document.createElement(etiqueta), propiedades);
  nodo.append(...hijos);
  return nodo;
}

function pintarMes(resumenDelMes) {
  const esMesActual = estado.mes === mesDeHoy();
  $("mes-titulo").textContent = conMayuscula(nombreDeMes(estado.mes));
  $("mes-anterior").setAttribute("aria-disabled", String(estado.mes <= estado.mesMinimo));
  $("mes-siguiente").setAttribute("aria-disabled", String(esMesActual));
  $("mes-actual").hidden = esMesActual;
  $("total-mes").textContent = dinero(resumenDelMes.total);
  $("total-detalle").textContent = `${cuantosGastos(resumenDelMes.cantidad)} en ${nombreDeMes(estado.mes)}`;
}

function pintarGastos() {
  $("lista-gastos").replaceChildren(...estado.gastos.map(filaDeGasto));
  $("tabla-gastos").hidden = estado.gastos.length === 0;
  $("vacio-gastos").hidden = estado.gastos.length > 0;
}

function filaDeGasto(gasto) {
  const descripcion = `${gasto.categoria}, ${dinero(gasto.monto)}, ${fechaLegible(gasto.fecha)}`;
  const editar = el("button", { type: "button", className: "enlace", textContent: "Editar" });
  editar.setAttribute("aria-label", `Editar gasto: ${descripcion}`);
  editar.addEventListener("click", () => empezarEdicion(gasto));
  const borrar = el("button", { type: "button", className: "enlace peligro", textContent: "Borrar" });
  borrar.setAttribute("aria-label", `Borrar gasto: ${descripcion}`);
  borrar.addEventListener("click", () => borrarGasto(gasto));

  return el(
    "tr",
    { className: gasto.id === estado.editando ? "editando" : "" },
    el("td", { className: "fecha", textContent: fechaLegible(gasto.fecha) }),
    el("td", { className: "categoria", textContent: gasto.categoria }),
    el("td", { className: "nota", textContent: gasto.nota }),
    el("td", { className: "numero", textContent: dinero(gasto.monto) }),
    el("td", { className: "acciones-fila" }, editar, borrar),
  );
}

// --- Cargar datos ----------------------------------------------------------

let ultimaCarga = 0;

/** Pide al backend los datos del mes que se muestra y repinta la página. */
async function cargar() {
  const carga = ++ultimaCarga;
  const mes = estado.mes;
  const [gastos, meses] = await Promise.all([
    api("GET", `/api/gastos?mes=${mes}`),
    api("GET", `/api/resumen/mensual?anio=${mes.slice(0, 4)}`),
  ]);
  if (carga !== ultimaCarga) return; // respuesta vieja: mientras tanto se pidió otro mes
  estado.gastos = gastos;
  pintarMes(meses.find((resumen) => resumen.mes === mes));
  pintarGastos();
}

function irAMes(mes) {
  if (mes < estado.mesMinimo || mes > mesDeHoy()) return; // no hay gastos futuros ni tan antiguos
  estado.mes = mes;
  cargar().catch(mostrarError);
}

// --- Formulario: crear, editar y borrar ------------------------------------

function reiniciarFormulario() {
  estado.editando = null;
  $("formulario").reset();
  $("fecha").value = hoy();
  $("fecha").max = hoy();
  $("titulo-formulario").textContent = "Nuevo gasto";
  $("guardar").textContent = "Agregar gasto";
  $("cancelar").hidden = true;
  limpiarErrores();
}

function empezarEdicion(gasto) {
  estado.editando = gasto.id;
  $("monto").value = gasto.monto.toFixed(2);
  $("categoria").value = gasto.categoria;
  $("fecha").value = gasto.fecha;
  $("nota").value = gasto.nota;
  $("titulo-formulario").textContent = "Editar gasto";
  $("guardar").textContent = "Guardar cambios";
  $("cancelar").hidden = false;
  limpiarErrores();
  avisar("");
  pintarGastos(); // resalta la fila que se está editando
  $("monto").focus(); // también lleva la vista hasta el formulario
}

async function guardar(evento) {
  evento.preventDefault();
  limpiarErrores();
  avisar("");
  const datos = {
    monto: $("monto").value,
    categoria: $("categoria").value,
    fecha: $("fecha").value,
    nota: $("nota").value,
  };
  $("guardar").disabled = true;
  try {
    const editando = estado.editando;
    const gasto = editando
      ? await api("PUT", `/api/gastos/${editando}`, datos)
      : await api("POST", "/api/gastos", datos);
    reiniciarFormulario();
    avisar(editando ? "Gasto actualizado." : "Gasto agregado.");
    estado.mes = gasto.fecha.slice(0, 7); // muestra el mes del gasto, para verlo en la lista
    await cargar();
    $("monto").focus(); // listo para anotar el siguiente
  } catch (error) {
    mostrarError(error);
  } finally {
    $("guardar").disabled = false;
  }
}

async function borrarGasto(gasto) {
  const descripcion = `${dinero(gasto.monto)} · ${gasto.categoria} · ${fechaLegible(gasto.fecha)}`;
  if (!confirm(`¿Borrar este gasto? No se puede deshacer.\n\n${descripcion}`)) return;
  try {
    await api("DELETE", `/api/gastos/${gasto.id}`);
    if (estado.editando === gasto.id) reiniciarFormulario();
    avisar("Gasto borrado.");
  } catch (error) {
    mostrarError(error);
  }
  await cargar().catch(mostrarError); // también si falló: la lista puede estar desactualizada
}

// --- Arranque --------------------------------------------------------------

async function iniciar() {
  const config = await api("GET", "/api/config");
  estado.moneda = config.moneda;
  estado.mesMinimo = `${config.anio_minimo}-01`;

  $("etiqueta-monto").textContent = `Monto (${config.moneda})`;
  $("nota").maxLength = config.nota_max_caracteres;
  $("fecha").min = `${config.anio_minimo}-01-01`;
  const elige = new Option("Elige…", "", true, true);
  elige.disabled = true;
  elige.hidden = true;
  $("categoria").replaceChildren(elige, ...config.categorias.map((nombre) => new Option(nombre)));
  reiniciarFormulario();

  $("formulario").addEventListener("submit", guardar);
  $("cancelar").addEventListener("click", () => {
    reiniciarFormulario();
    avisar("");
    pintarGastos();
  });
  $("mes-anterior").addEventListener("click", () => irAMes(moverMes(estado.mes, -1)));
  $("mes-siguiente").addEventListener("click", () => irAMes(moverMes(estado.mes, 1)));
  $("mes-actual").addEventListener("click", () => irAMes(mesDeHoy()));

  await cargar();
}

iniciar().catch(mostrarError);
