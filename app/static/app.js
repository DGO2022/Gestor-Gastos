"use strict";

/* Gestor de gastos: el navegador solo pinta. Las reglas y las sumas las hace el backend. */

const $ = (id) => document.getElementById(id);

const estado = {
  moneda: "",
  mesMinimo: "2000-01",
  mes: mesDeHoy(), // mes que se muestra, "AAAA-MM"
  editando: null, // id del gasto que se está editando, o null
  gastos: [], // gastos del mes que se muestra
  meses: [], // total de cada mes del año que se muestra
  categorias: [], // total por categoría del mes que se muestra
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

const formatoMesCorto = new Intl.DateTimeFormat("es", { month: "short" });

/** "2026-11" -> "nov". */
function nombreCortoDeMes(mes) {
  const [anio, numero] = mes.split("-").map(Number);
  return formatoMesCorto.format(new Date(anio, numero - 1, 1)).replace(".", "");
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
  return `${estado.moneda}\u00a0${formatoNumero.format(monto)}`;
}

const formatoPorcentaje = new Intl.NumberFormat(undefined, { style: "percent" });

/** Qué parte del total del mes es este monto: "28%". */
function parteDelMes(monto) {
  const total = estado.meses.find((resumen) => resumen.mes === estado.mes).total;
  return formatoPorcentaje.format(total ? monto / total : 0);
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

// --- Gráficos --------------------------------------------------------------

const graficos = {}; // gráficos de Chart.js ya creados, por nombre
const ALTO_DE_FILA = 34; // píxeles que ocupa cada categoría
let tema = {}; // colores vigentes

/** Lee los colores de las variables CSS, que cambian solas entre el tema claro y el oscuro. */
function leerTema() {
  const estilos = getComputedStyle(document.documentElement);
  const color = (variable) => estilos.getPropertyValue(variable).trim();
  return {
    serie: color("--serie"),
    serieActiva: color("--serie-activa"),
    serieTenue: color("--serie-tenue"),
    tinta: color("--tinta"),
    tinta2: color("--tinta-2"),
    tinta3: color("--tinta-3"),
    rejilla: color("--rejilla"),
    eje: color("--eje"),
    superficie: color("--superficie"),
  };
}

/** Etiqueta emergente: arriba el valor, que es lo que se busca, y debajo a qué corresponde. */
function emergente(valor, detalle) {
  return {
    displayColors: false, // hay una sola serie: sobra la muestra de color
    backgroundColor: tema.tinta,
    titleColor: tema.superficie,
    bodyColor: tema.superficie,
    titleFont: { size: 14, weight: 600 },
    padding: 10,
    cornerRadius: 8,
    callbacks: {
      title: (puntos) => valor(puntos[0].dataIndex),
      label: (punto) => detalle(punto.dataIndex),
    },
  };
}

const formatoEje = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
const formatoEjeCompacto = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Marcas del eje: números completos hasta 10 000 y abreviados (10K, 20K...) desde ahí. */
function marcaDelEje(valor) {
  return (this.max < 10000 ? formatoEje : formatoEjeCompacto).format(valor);
}

/** Columnas con el total de cada mes del año. Hacer clic en un mes lo muestra. */
function configDeMeses() {
  const meses = estado.meses;
  const esElMesVisto = (resumen) => resumen.mes === estado.mes;
  return {
    data: {
      labels: meses.map((resumen) => nombreCortoDeMes(resumen.mes)),
      datasets: [
        {
          data: meses.map((resumen) => resumen.total),
          // Énfasis: el mes que se está viendo va en color y el resto en gris, como contexto.
          backgroundColor: meses.map((r) => (esElMesVisto(r) ? tema.serie : tema.serieTenue)),
          hoverBackgroundColor: meses.map((r) => (esElMesVisto(r) ? tema.serieActiva : tema.tinta3)),
          borderRadius: 4, // punta redondeada; la base queda recta
          maxBarThickness: 24,
        },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false }, // responde toda la franja del mes
      onClick: (_evento, barras) => {
        if (barras.length) irAMes(meses[barras[0].index].mes);
      },
      onHover: (evento, barras) => {
        evento.native.target.style.cursor = barras.length ? "pointer" : "default";
      },
      scales: {
        x: { grid: { display: false }, border: { color: tema.eje }, ticks: { color: tema.tinta3 } },
        y: {
          beginAtZero: true,
          suggestedMax: meses.some((resumen) => resumen.total > 0) ? undefined : 100,
          border: { display: false },
          grid: { color: tema.rejilla },
          ticks: { color: tema.tinta3, maxTicksLimit: 5, callback: marcaDelEje },
        },
      },
      plugins: {
        tooltip: emergente(
          (i) => dinero(meses[i].total),
          (i) => `${nombreDeMes(meses[i].mes)} · ${cuantosGastos(meses[i].cantidad)}`,
        ),
      },
    },
  };
}

function fuenteDeMontos() {
  return `600 12px ${Chart.defaults.font.family}`;
}

const medidor = document.createElement("canvas").getContext("2d");

function anchoDelMasLargo(textos) {
  medidor.font = fuenteDeMontos();
  return Math.max(0, ...textos.map((texto) => medidor.measureText(texto).width));
}

/** Complemento de Chart.js: escribe el monto en la punta de cada barra horizontal. */
const montoEnLaPunta = {
  id: "montoEnLaPunta",
  afterDatasetsDraw(grafico) {
    const lapiz = grafico.ctx;
    lapiz.save();
    lapiz.font = fuenteDeMontos();
    lapiz.fillStyle = tema.tinta; // el texto va en color de texto, no en el de la barra
    lapiz.textBaseline = "middle";
    grafico.getDatasetMeta(0).data.forEach((barra, i) => {
      lapiz.fillText(dinero(grafico.data.datasets[0].data[i]), barra.x + 6, barra.y);
    });
    lapiz.restore();
  },
};

/** Barras horizontales, de mayor a menor gasto, con el total de cada categoría del mes. */
function configDeCategorias() {
  const filas = estado.categorias;
  const montos = filas.map((fila) => dinero(fila.total));
  return {
    data: {
      labels: filas.map((fila) => fila.categoria),
      datasets: [
        {
          data: filas.map((fila) => fila.total),
          // Un solo color: la categoría la dice su nombre y el monto, el largo de la barra.
          backgroundColor: tema.serie,
          hoverBackgroundColor: tema.serieActiva,
          borderRadius: 4,
          barThickness: 14,
        },
      ],
    },
    options: {
      indexAxis: "y",
      interaction: { mode: "index", axis: "y", intersect: false }, // responde toda la fila
      layout: { padding: { right: anchoDelMasLargo(montos) + 14 } }, // sitio para el monto
      scales: {
        x: { display: false, beginAtZero: true }, // sin eje: cada barra lleva su monto escrito
        y: {
          grid: { display: false },
          border: { display: false },
          ticks: { color: tema.tinta2, font: { size: 13 } },
        },
      },
      plugins: {
        tooltip: emergente(
          (i) => montos[i],
          (i) =>
            `${filas[i].categoria} · ${parteDelMes(filas[i].total)} del mes · ${cuantosGastos(filas[i].cantidad)}`,
        ),
      },
    },
  };
}

/** Crea el gráfico la primera vez; después lo actualiza en su sitio, sin parpadeos. */
function pintarGrafico(nombre, config, complementos = []) {
  const grafico = graficos[nombre];
  if (grafico) {
    Object.assign(grafico, config);
    grafico.resize();
    grafico.update();
  } else {
    const lienzo = $(`grafico-${nombre}`);
    graficos[nombre] = new Chart(lienzo, { type: "bar", plugins: complementos, ...config });
  }
}

/** Los mismos datos del gráfico en una tabla: se leen sin cursor y con lector de pantalla. */
function pintarTabla(id, columnas, filas) {
  const cabecera = columnas.map((texto, i) =>
    el("th", { scope: "col", className: i ? "numero" : "", textContent: texto }),
  );
  const cuerpo = filas.map(([nombre, ...valores]) =>
    el(
      "tr",
      {},
      el("th", { scope: "row", textContent: nombre }),
      ...valores.map((valor) => el("td", { className: "numero", textContent: valor })),
    ),
  );
  $(id).replaceChildren(el("thead", {}, el("tr", {}, ...cabecera)), el("tbody", {}, ...cuerpo));
}

function pintarGraficos() {
  tema = leerTema();
  const hayGastos = estado.categorias.length > 0;

  $("subtitulo-categorias").textContent = conMayuscula(nombreDeMes(estado.mes));
  $("vacio-categorias").hidden = hayGastos;
  $("datos-categorias").hidden = !hayGastos;
  $("lienzo-categorias").hidden = !hayGastos;
  $("lienzo-categorias").style.height = `${estado.categorias.length * ALTO_DE_FILA + 8}px`;
  pintarGrafico("categorias", configDeCategorias(), [montoEnLaPunta]);
  pintarTabla(
    "tabla-categorias",
    ["Categoría", "Total", "Parte del mes", "Gastos"],
    estado.categorias.map((fila) => [
      fila.categoria,
      dinero(fila.total),
      parteDelMes(fila.total),
      fila.cantidad,
    ]),
  );

  $("subtitulo-meses").textContent = `${estado.mes.slice(0, 4)} · haz clic en un mes para verlo`;
  pintarGrafico("meses", configDeMeses());
  pintarTabla(
    "tabla-meses",
    ["Mes", "Total", "Gastos"],
    estado.meses.map((resumen) => [
      conMayuscula(nombreDeMes(resumen.mes)),
      dinero(resumen.total),
      resumen.cantidad,
    ]),
  );
}

// --- Cargar datos ----------------------------------------------------------

let ultimaCarga = 0;

/** Pide al backend los datos del mes que se muestra y repinta la página. */
async function cargar() {
  const carga = ++ultimaCarga;
  const mes = estado.mes;
  const [gastos, meses, categorias] = await Promise.all([
    api("GET", `/api/gastos?mes=${mes}`),
    api("GET", `/api/resumen/mensual?anio=${mes.slice(0, 4)}`),
    api("GET", `/api/resumen/categorias?mes=${mes}`),
  ]);
  if (carga !== ultimaCarga) return; // respuesta vieja: mientras tanto se pidió otro mes
  Object.assign(estado, { gastos, meses, categorias });
  pintarMes(meses.find((resumen) => resumen.mes === mes));
  pintarGastos();
  pintarGraficos();
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

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.maintainAspectRatio = false; // el tamaño lo manda la caja .lienzo del CSS
  Chart.defaults.plugins.legend.display = false; // una sola serie: el título ya dice qué se ve
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) Chart.defaults.animation = false;
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", pintarGraficos);

  await cargar();
}

iniciar().catch(mostrarError);
