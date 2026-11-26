/* Sistema de Tickets de tareas — interfaz (JavaScript sin dependencias,
   para que funcione en un servidor sin acceso a internet). */
"use strict";

// ── Utilidades (las mismas de la Pizarra) ─────────────────────────────
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const DIAS_SEMANA = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];

const fmt = (iso) => (!iso ? "" : iso.slice(8, 10) + "/" + iso.slice(5, 7) + "/" + iso.slice(0, 4));
const fmtHora = (ts) => (ts ? new Date(ts).toLocaleString("es-PY", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "");
const fmtHoraCorta = (ts) => {
  if (!ts) return "";
  const d = new Date(ts), hoy = new Date();
  const hora = d.toLocaleTimeString("es-PY", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === hoy.toDateString()) return "hoy " + hora;
  const ayer = new Date(hoy); ayer.setDate(hoy.getDate() - 1);
  if (d.toDateString() === ayer.toDateString()) return "ayer " + hora;
  return d.toLocaleDateString("es-PY", { day: "2-digit", month: "2-digit" }) + " " + hora;
};
/** Duración legible a partir de horas: «35 min», «5 h», «2 d 3 h». */
const fmtDur = (h) => {
  if (h === null || h === undefined) return "—";
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`;
  if (h < 24) return `${Math.round(h)} h`;
  const d = Math.floor(h / 24), r = Math.round(h - d * 24);
  return r ? `${d} d ${r} h` : `${d} d`;
};
const aLocal = (d) => { const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000); return z.toISOString().slice(0, 16); };
const hoyIso = () => aLocal(new Date()).slice(0, 10);

const CANAL_ICONO = { TELEFONO: "📞", WHATSAPP: "💬", CORREO: "✉", PRESENCIAL: "🙋" };
const ESTADOS_ABIERTOS = ["NUEVO", "ASIGNADO", "EN_PROCESO", "EN_ESPERA"];
const ORDEN_PRIO = { URGENTE: 0, ALTA: 1, MEDIA: 2, BAJA: 3 };

const pref = {
  leer(k, def) { try { const v = localStorage.getItem("tickets." + k); return v === null ? def : JSON.parse(v); } catch { return def; } },
  guardar(k, v) { try { localStorage.setItem("tickets." + k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
};

function toast(msg, ms = 3500) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), ms);
}

class ErrorApi extends Error {
  constructor(status, data) { super(data?.detail || "Error " + status); this.status = status; this.data = data; }
}

async function api(metodo, url, cuerpo) {
  const op = { method: metodo, headers: {} };
  if (cuerpo instanceof FormData) op.body = cuerpo;
  else if (cuerpo !== undefined) { op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(cuerpo); }
  const r = await fetch(url, op);
  if (r.status === 401) { location.href = "/login"; throw new ErrorApi(401, {}); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErrorApi(r.status, data);
  return data;
}

function detalleError(d) {
  if (!d) return "Error desconocido";
  if (typeof d.detail === "string") return d.detail;
  if (Array.isArray(d.detail)) return d.detail.map((x) => `${(x.loc || []).slice(-1)[0]}: ${x.msg}`).join(" · ");
  return "Error";
}

const listaHallazgos = (hs) =>
  `<ul class="hallazgos">${hs.map((h) => `<li class="h-${esc(h.nivel)}">${esc(h.mensaje)}</li>`).join("")}</ul>`;

function mostrarError(e) {
  if (e?.data?.hallazgos) {
    const titulo = e.data.tipo === "VERSION" ? "⚠ El ticket cambió" : "⛔ No se puede guardar";
    modal($("#modal2"), { titulo, cuerpo: listaHallazgos(e.data.hallazgos), pie: [{ texto: "Entendido", clase: "primario" }] });
  } else if (e instanceof ErrorApi) {
    toast(detalleError(e.data), 6000);
  } else {
    console.error(e);
    toast("No hay conexión con el servidor.", 6000);
  }
}

/** Abre un diálogo. pie: [{texto, clase, accion(cerrar) -> (false para no cerrar)}] */
function modal(dlg, { titulo, cuerpo, pie = [], ancho = false, alCerrar }) {
  dlg.className = ancho ? "ancho" : "";
  dlg.innerHTML = `<div class="modal-cab"><h2>${esc(titulo)}</h2><button class="cerrar" aria-label="Cerrar">×</button></div>
    <div class="modal-cuerpo"></div><div class="modal-pie"></div>`;
  const c = $(".modal-cuerpo", dlg);
  if (typeof cuerpo === "string") c.innerHTML = cuerpo; else if (cuerpo) c.append(cuerpo);
  const cerrar = () => { if (dlg.open) dlg.close(); };
  dlg.onclose = () => alCerrar && alCerrar();
  $(".cerrar", dlg).onclick = cerrar;
  const piePanel = $(".modal-pie", dlg);
  if (!pie.length) piePanel.remove();
  for (const b of pie) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "btn " + (b.clase || "");
    el.textContent = b.texto;
    if (b.id) el.id = b.id;
    el.onclick = async () => {
      if (!b.accion) return cerrar();
      el.disabled = true;
      try { if ((await b.accion(cerrar)) !== false) cerrar(); }
      finally { el.disabled = false; }
    };
    piePanel.append(el);
  }
  if (!dlg.open) dlg.showModal();
  return { dlg, cuerpo: c, cerrar };
}

function confirmar(titulo, html, textoOk = "Confirmar") {
  return new Promise((ok) => {
    let r = false;
    modal($("#modal2"), {
      titulo, cuerpo: html,
      pie: [{ texto: "Cancelar" }, { texto: textoOk, clase: "primario", accion: () => { r = true; } }],
      alCerrar: () => ok(r),
    });
  });
}

/** Envía y, si el servidor pide confirmar advertencias (HTTP 428), las muestra y reintenta. */
async function enviarConConfirmacion(enviar) {
  try { return await enviar(false); }
  catch (e) {
    if (e?.status !== 428) throw e;
    const ok = await confirmar("⚠ Revise antes de guardar", listaHallazgos(e.data.hallazgos) +
      `<p class="ayuda">Si está seguro, confirme y quedará registrado en la auditoría.</p>`, "Guardar igual");
    if (!ok) return null;
    return await enviar(true);
  }
}

// ── Chips y pequeños componentes ──────────────────────────────────────
const chipEstado = (e) => `<span class="chip ${e}">${esc(E.cat.estados[e] || e)}</span>`;
const chipPrio = (p) => `<span class="chip ${p}">${esc(E.cat.prioridades[p] || p)}</span>`;
const chipAtraso = (t) => (t.atrasado ? `<span class="chip atrasado" title="Superó el tiempo objetivo de ${t.objetivo_horas} h para prioridad ${esc(E.cat.prioridades[t.prioridad])}">Atrasado</span>` : "");
const canalTxt = (c) => `<span class="canal" title="${esc(E.cat.canales[c])}">${CANAL_ICONO[c] || ""} ${esc(E.cat.canales[c])}</span>`;
const soyJefe = () => E.yo.rol === "JEFE";
const puedoTrabajar = (t) => t.estado !== "ANULADO" && (soyJefe() || t.tecnico_id === null || t.tecnico_id === E.yo.id);

// ── Estado ────────────────────────────────────────────────────────────
const E = {
  yo: null, cat: null, tickets: [], panel: null, vista: pref.leer("vista", "mios"),
  conocidos: null, sonido: pref.leer("sonido", true), sinVer: 0,
  filtroAbiertos: { tecnico: "", estado: "", prioridad: "" },
  busqueda: null, resultado: null, diasPanel: pref.leer("diasPanel", 30),
};

// ── Inicio ────────────────────────────────────────────────────────────
async function iniciar() {
  try { E.yo = await api("GET", "/api/yo"); } catch { return; }
  $("#nombre-usuario").textContent = E.yo.nombre;
  $("#m-version").textContent = `Versión ${E.yo.version}`;
  $("#oficina").textContent = "· " + E.yo.oficina;
  $("#m-admin").hidden = !soyJefe();
  $("#tab-panel").hidden = !soyJefe();
  if (E.vista === "panel" && !soyJefe()) E.vista = "mios";
  if (!pref.leer("vista", null)) E.vista = soyJefe() ? "panel" : "mios";
  E.cat = await api("GET", "/api/catalogos");
  pintarSonido();
  conectarEventos();
  await recargar();
  iniciarAutoActualizacion();
}

async function refrescarCatalogos() {
  E.cat = await api("GET", "/api/catalogos");
}

// ── Carga de datos y actualización automática ─────────────────────────
const AUTO_SEG = 15;   // cada cuántos segundos se buscan cambios hechos por otros usuarios

async function traerDatos() {
  const tablero = await api("GET", "/api/tablero");
  const panel = E.vista === "panel" && soyJefe() ? await api("GET", `/api/panel?dias=${E.diasPanel}`) : null;
  return { tablero, panel };
}

function aplicarDatos(r) {
  avisarNovedades(r.tablero.tickets);
  E.tickets = r.tablero.tickets;
  E.ahora = r.tablero.ahora;
  if (r.panel) E.panel = r.panel;
  E.firma = JSON.stringify(r.tablero.tickets.map((t) => [t.id, t.version, t.modificado_en, t.atrasado])) + JSON.stringify(r.panel);
}

async function recargar() {
  try {
    const r = await traerDatos();
    aplicarDatos(r);
    marcarActualizado(true);
    dibujar();
  } catch (e) { mostrarError(e); }
}

/** Indicador «Actualizado hace…» de la barra superior. */
function marcarActualizado(ok) {
  if (ok === true) { E.actualizado = Date.now(); E.sinConexion = false; } else if (ok === false) E.sinConexion = true;
  const el = $("#actualizado");
  if (!el || !E.actualizado) return;
  const s = Math.round((Date.now() - E.actualizado) / 1000);
  const hace = s < 5 ? "recién" : s < 60 ? `hace ${s} s` : `hace ${Math.floor(s / 60)} min`;
  el.classList.toggle("sin-conexion", !!E.sinConexion);
  el.textContent = E.sinConexion ? "⚠ Sin conexión con el servidor" : `● Actualizado ${hace}`;
  el.title = E.sinConexion
    ? "No se pudo consultar al servidor. Se vuelve a intentar sola cada " + AUTO_SEG + " segundos."
    : "Los cambios de los demás aparecen solos cada " + AUTO_SEG + " segundos.";
}

const hayVentanaAbierta = () => $("#modal").open || $("#modal2").open || !$("#menu-usuario").hidden;

/** Busca cambios hechos por otros usuarios y redibuja solo si los hay. No interrumpe:
    si hay una ventana o el menú abiertos, espera a que se cierren. */
async function actualizarAuto() {
  const tv = !$("#tv").hidden;
  if (document.hidden && !tv) { return; }
  if (E.autoEnCurso || (!tv && hayVentanaAbierta())) return;
  E.autoEnCurso = true;
  try {
    const r = await traerDatos();
    marcarActualizado(true);
    const firma = JSON.stringify(r.tablero.tickets.map((t) => [t.id, t.version, t.modificado_en, t.atrasado])) + JSON.stringify(r.panel);
    if (firma === E.firma) return;                         // nada cambió
    if (!tv && hayVentanaAbierta()) return;               // se abrió una ventana mientras se consultaba
    aplicarDatos(r);
    if (tv) { modoTV.pintar?.(); return; }
    const c = $("#contenido"), arriba = c.scrollTop;
    dibujar();
    c.scrollTop = arriba;
  } catch {
    marcarActualizado(false);
  } finally { E.autoEnCurso = false; }
}

function iniciarAutoActualizacion() {
  setInterval(actualizarAuto, AUTO_SEG * 1000);
  setInterval(() => marcarActualizado(), 5000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { actualizarAuto(); limpiarSinVer(); } });
  window.addEventListener("focus", () => { actualizarAuto(); limpiarSinVer(); });
  ["#modal", "#modal2"].forEach((s) => $(s).addEventListener("close", () => setTimeout(actualizarAuto, 300)));
}

// ── Avisos: ticket nuevo o asignado a mí (sonido + título de la pestaña) ──
function avisarNovedades(tickets) {
  const antes = E.conocidos;
  E.conocidos = new Map(tickets.map((t) => [t.id, t]));
  if (!antes) return;                                      // primera carga: no avisar
  const avisos = [];
  for (const t of tickets) {
    const prev = antes.get(t.id);
    if (!prev && t.estado === "NUEVO" && t.creado_por !== E.yo.id) avisos.push(`📥 Nuevo ticket #${t.id}: ${t.asunto}`);
    else if (t.tecnico_id === E.yo.id && ESTADOS_ABIERTOS.includes(t.estado) && t.modificado_por !== E.yo.id
             && (prev ? prev.tecnico_id !== E.yo.id : t.creado_por !== E.yo.id))
      avisos.push(`📋 Le asignaron el ticket #${t.id}: ${t.asunto}`);
  }
  if (!avisos.length) return;
  toast(avisos.slice(0, 3).join(" · ") + (avisos.length > 3 ? ` (y ${avisos.length - 3} más)` : ""), 8000);
  sonar();
  if (document.hidden || !document.hasFocus()) {
    E.sinVer += avisos.length;
    document.title = `(${E.sinVer}) Tickets de Soporte`;
  }
}
function limpiarSinVer() { E.sinVer = 0; document.title = "Tickets de Soporte"; }

function sonar() {
  if (!E.sonido) return;
  try {
    const ctx = sonar.ctx || (sonar.ctx = new (window.AudioContext || window.webkitAudioContext)());
    [0, 0.18].forEach((d, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = i ? 880 : 660;
      g.gain.setValueAtTime(0.0001, ctx.currentTime + d);
      g.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + d + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + d + 0.16);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + d); o.stop(ctx.currentTime + d + 0.18);
    });
  } catch { /* sin audio */ }
}
function pintarSonido() {
  const b = $("#btn-sonido");
  b.textContent = E.sonido ? "🔔" : "🔕";
  b.title = E.sonido ? "Aviso sonoro activado (clic para silenciar)" : "Aviso sonoro silenciado (clic para activar)";
}

// ── Dibujo de las vistas ──────────────────────────────────────────────
const mios = () => E.tickets.filter((t) => t.tecnico_id === E.yo.id && t.estado !== "ANULADO");
const disponibles = () => E.tickets.filter((t) => t.estado === "NUEVO");
const abiertos = () => E.tickets.filter((t) => ESTADOS_ABIERTOS.includes(t.estado));
const ordenar = (xs) => xs.sort((a, b) => (b.atrasado - a.atrasado) || (ORDEN_PRIO[a.prioridad] - ORDEN_PRIO[b.prioridad]) || a.recibido_en.localeCompare(b.recibido_en));

function filtroRapido(xs) {
  const q = $("#f-rapido").value.trim().toLowerCase();
  if (!q) return xs;
  return xs.filter((t) => [`#${t.id}`, String(t.id), t.asunto, t.solicitante, t.area, t.categoria, t.tecnico, t.descripcion, t.canal_referencia]
    .some((v) => v && String(v).toLowerCase().includes(q)));
}

function dibujar() {
  $$("#vistas button").forEach((b) => b.classList.toggle("activo", b.dataset.vista === E.vista));
  const nMios = mios().filter((t) => ESTADOS_ABIERTOS.includes(t.estado)).length;
  const disp = disponibles();
  const limite = Date.now() - E.cat.alerta_sin_asignar_min * 60000;
  $("#n-mios").textContent = nMios || "";
  $("#n-disponibles").textContent = disp.length || "";
  $("#n-disponibles").classList.toggle("alerta", disp.some((t) => new Date(t.recibido_en).getTime() < limite));
  $("#n-disponibles").title = `Tickets sin asignar. Se resalta si alguno espera más de ${E.cat.alerta_sin_asignar_min} min.`;
  $("#n-abiertos").textContent = abiertos().length || "";
  $("#f-rapido").hidden = E.vista === "panel" || E.vista === "buscar";
  const c = $("#contenido");
  if (E.vista === "mios") dibujarMios(c);
  else if (E.vista === "disponibles") dibujarLista(c, ordenar(filtroRapido(disponibles())), { tomar: true,
    vacio: "No hay tickets sin asignar. 🎉" });
  else if (E.vista === "abiertos") dibujarAbiertos(c);
  else if (E.vista === "buscar") dibujarBuscar(c);
  else if (E.vista === "panel") dibujarPanel(c);
}

function dibujarMios(c) {
  const xs = filtroRapido(mios());
  const cols = [["ASIGNADO", "Asignados (por empezar)"], ["EN_PROCESO", "En proceso"], ["EN_ESPERA", "En espera"], ["RESUELTO", "Resueltos (últimos 7 días)"]];
  c.innerHTML = `<div class="columnas">${cols.map(([e, titulo]) => {
    let ts = xs.filter((t) => t.estado === e);
    ts = e === "RESUELTO" ? ts.sort((a, b) => b.resuelto_en.localeCompare(a.resuelto_en)) : ordenar(ts);
    return `<section class="columna c-${e}"><h2><span>${titulo}</span><span>${ts.length}</span></h2>
      ${ts.map(tarjeta).join("") || `<div class="ayuda" style="padding:6px">—</div>`}</section>`;
  }).join("")}</div>
  ${xs.length ? "" : `<p class="vacio">No tiene tickets asignados. Mire la pestaña <b>📥 Disponibles</b> para tomar uno.</p>`}`;
  $$(".tarjeta", c).forEach((el) => {
    el.onclick = (ev) => { if (!ev.target.closest("button")) verTicket(+el.dataset.id); };
    el.onkeydown = (ev) => { if (ev.key === "Enter") verTicket(+el.dataset.id); };
  });
  $$("[data-rapido]", c).forEach((b) => (b.onclick = () => accionRapida(+b.dataset.id, b.dataset.rapido)));
}

function tarjeta(t) {
  const botones = t.estado === "ASIGNADO" ? `<button class="btn chico" data-rapido="EN_PROCESO" data-id="${t.id}">▶ Iniciar</button>`
    : t.estado === "EN_ESPERA" ? `<button class="btn chico" data-rapido="EN_PROCESO" data-id="${t.id}">▶ Retomar</button>` : "";
  const resolver = ["ASIGNADO", "EN_PROCESO", "EN_ESPERA"].includes(t.estado)
    ? `<button class="btn chico" data-rapido="RESUELTO" data-id="${t.id}">✔ Resolver</button>` : "";
  return `<article class="tarjeta ${t.prioridad} ${t.atrasado ? "atrasado" : ""}" data-id="${t.id}" tabindex="0">
    <div class="t-cab"><b style="color:var(--primario)">#${t.id}</b><span>${CANAL_ICONO[t.canal]} ${fmtHoraCorta(t.recibido_en)}</span></div>
    <div class="t-asunto">${esc(t.asunto)}</div>
    <div class="t-pie">${esc(t.solicitante)}${t.area ? " · " + esc(t.area) : ""}</div>
    <div class="t-pie" style="margin-top:4px">${chipPrio(t.prioridad)} ${chipAtraso(t)}
      ${t.estado === "EN_ESPERA" && t.motivo_espera ? `<span title="${esc(t.motivo_espera)}">⏸ ${esc(t.motivo_espera.slice(0, 40))}</span>` : ""}
      ${t.n_notas ? `<span title="Notas">💬 ${t.n_notas}</span>` : ""}${t.n_adjuntos ? `<span title="Adjuntos">📎 ${t.n_adjuntos}</span>` : ""}
      <span style="margin-left:auto" title="Tiempo desde que se recibió">${fmtDur(t.horas)}</span></div>
    ${botones || resolver ? `<div class="t-botones">${botones}${resolver}</div>` : ""}
  </article>`;
}

function dibujarLista(c, xs, { tomar = false, vacio = "No hay tickets.", cabecera = "" } = {}) {
  c.innerHTML = cabecera + (xs.length ? `<div class="tabla-contenedor" style="max-height:none"><table class="lista"><thead><tr>
      <th>Nº</th><th>Asunto / solicitante</th><th class="col-opc">Canal</th><th>Prioridad</th><th>Estado</th>
      <th class="col-opc">Técnico</th><th class="col-opc">Recibido</th><th class="col-opc">Tiempo</th>${tomar ? "<th></th>" : ""}</tr></thead>
    <tbody>${xs.map((t) => `<tr class="fila-${t.prioridad} fila-${t.estado} ${t.atrasado ? "fila-atrasado" : ""}" data-id="${t.id}">
      <td class="num">#${t.id}</td>
      <td><div class="asunto">${esc(t.asunto)}</div><div class="sub">${esc(t.solicitante)}${t.area ? " · " + esc(t.area) : ""}${t.categoria ? " · " + esc(t.categoria) : ""}</div></td>
      <td class="col-opc">${canalTxt(t.canal)}</td>
      <td>${chipPrio(t.prioridad)}</td>
      <td>${chipEstado(t.estado)} ${chipAtraso(t)}</td>
      <td class="col-opc">${t.tecnico ? esc(t.tecnico) : `<span class="ayuda">sin asignar</span>`}</td>
      <td class="col-opc" style="white-space:nowrap">${fmtHoraCorta(t.recibido_en)}</td>
      <td class="col-opc" style="white-space:nowrap">${fmtDur(t.horas)}</td>
      ${tomar ? `<td class="acciones"><button class="btn chico primario" data-tomar="${t.id}">✋ Tomar</button></td>` : ""}
    </tr>`).join("")}</tbody></table></div>` : `<p class="vacio">${vacio}</p>`);
  $$("tbody tr", c).forEach((tr) => (tr.onclick = (ev) => { if (!ev.target.closest("button")) verTicket(+tr.dataset.id); }));
  $$("[data-tomar]", c).forEach((b) => (b.onclick = () => tomar(+b.dataset.tomar)));
}

function dibujarAbiertos(c) {
  const f = E.filtroAbiertos;
  let xs = filtroRapido(abiertos());
  if (f.tecnico === "0") xs = xs.filter((t) => t.tecnico_id === null);
  else if (f.tecnico) xs = xs.filter((t) => t.tecnico_id === +f.tecnico);
  if (f.estado) xs = f.estado === "ATRASADO" ? xs.filter((t) => t.atrasado) : xs.filter((t) => t.estado === f.estado);
  if (f.prioridad) xs = xs.filter((t) => t.prioridad === f.prioridad);
  const opc = (lista, sel) => lista.map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(sel) ? "selected" : ""}>${esc(t)}</option>`).join("");
  const cab = `<div class="filtros">
    <label>Técnico <select id="fa-tecnico">${opc([["", "Todos"], ["0", "(sin asignar)"], ...E.cat.tecnicos.map((u) => [u.id, u.nombre])], f.tecnico)}</select></label>
    <label>Estado <select id="fa-estado">${opc([["", "Todos los abiertos"], ...ESTADOS_ABIERTOS.map((e) => [e, E.cat.estados[e]]), ["ATRASADO", "⏰ Solo atrasados"]], f.estado)}</select></label>
    <label>Prioridad <select id="fa-prioridad">${opc([["", "Todas"], ...Object.entries(E.cat.prioridades)], f.prioridad)}</select></label>
    <span class="ayuda">${xs.length} ticket(s) · ordenados por atraso, prioridad y antigüedad</span></div>`;
  dibujarLista(c, ordenar(xs), { cabecera: cab, vacio: "No hay tickets abiertos con esos filtros." });
  ["tecnico", "estado", "prioridad"].forEach((k) => ($(`#fa-${k}`, c).onchange = (e) => { E.filtroAbiertos[k] = e.target.value; dibujar(); }));
}

// ── Historial / búsqueda ──────────────────────────────────────────────
function dibujarBuscar(c) {
  const b = E.busqueda || { desde: hoyIso().slice(0, 8) + "01", hasta: hoyIso(), estado: "", tecnico_id: "", canal: "", area_id: "", categoria_id: "", prioridad: "", q: "" };
  E.busqueda = b;
  const opc = (lista, sel) => lista.map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(sel) ? "selected" : ""}>${esc(t)}</option>`).join("");
  c.innerHTML = `<form class="filtros" id="f-buscar">
      <label>Desde <input type="date" name="desde" value="${esc(b.desde)}"></label>
      <label>Hasta <input type="date" name="hasta" value="${esc(b.hasta)}"></label>
      <label>Estado <select name="estado">${opc([["", "Todos"], ...Object.entries(E.cat.estados)], b.estado)}</select></label>
      <label>Técnico <select name="tecnico_id">${opc([["", "Todos"], ["0", "(sin asignar)"], ...E.cat.tecnicos.map((u) => [u.id, u.nombre])], b.tecnico_id)}</select></label>
      <label>Canal <select name="canal">${opc([["", "Todos"], ...Object.entries(E.cat.canales)], b.canal)}</select></label>
      <label>Prioridad <select name="prioridad">${opc([["", "Todas"], ...Object.entries(E.cat.prioridades)], b.prioridad)}</select></label>
      <label>Área <select name="area_id">${opc([["", "Todas"], ...E.cat.areas.map((a) => [a.id, a.nombre])], b.area_id)}</select></label>
      <label>Categoría <select name="categoria_id">${opc([["", "Todas"], ...E.cat.categorias.map((x) => [x.id, x.nombre])], b.categoria_id)}</select></label>
      <input type="search" name="q" value="${esc(b.q)}" placeholder="Texto, nº de ticket, solicitante…" style="min-width:220px">
      <button class="btn primario">🔍 Buscar</button>
      <button class="btn" type="button" id="b-csv" title="Planilla para abrir con Excel o LibreOffice">⇩ Exportar a Excel (CSV)</button>
    </form><div id="resultado"></div>`;
  const leer = () => Object.fromEntries(new FormData($("#f-buscar", c)).entries());
  const params = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== "")).toString();
  const buscar = async () => {
    E.busqueda = leer();
    try {
      E.resultado = await api("GET", "/api/tickets?" + params(E.busqueda));
      pintarResultado();
    } catch (e) { mostrarError(e); }
  };
  const pintarResultado = () => {
    const r = $("#resultado", c);
    if (!E.resultado) { r.innerHTML = `<p class="vacio">Elija los filtros y presione Buscar.</p>`; return; }
    dibujarLista(r, E.resultado, { vacio: "No se encontraron tickets con esos filtros.",
      cabecera: `<p class="ayuda">${E.resultado.length} ticket(s)${E.resultado.length >= 500 ? " (se muestran los 500 más recientes; use «Exportar» para obtener todos)" : ""}.</p>` });
  };
  $("#f-buscar", c).onsubmit = (e) => { e.preventDefault(); buscar(); };
  $("#b-csv", c).onclick = () => { location.href = "/api/tickets.csv?" + params(leer()); };
  if (E.resultado) pintarResultado(); else buscar();
}

// ── Panel del jefe ────────────────────────────────────────────────────
function barras(pares, etiqueta = (k) => k) {
  const max = Math.max(1, ...pares.map(([, v]) => v));
  if (!pares.length) return `<p class="ayuda">Sin datos en el período.</p>`;
  return `<ul class="barras">${pares.map(([k, v]) => `<li><span class="etq" title="${esc(etiqueta(k))}">${esc(etiqueta(k))}</span>
    <span class="b"><i style="width:${(100 * v / max).toFixed(1)}%"></i></span><span class="n">${v}</span></li>`).join("")}</ul>`;
}

function dibujarPanel(c) {
  const p = E.panel;
  if (!p) { c.innerHTML = `<div class="vacio">Cargando…</div>`; return; }
  const t = p.totales;
  const pct = (v) => (v === null ? "—" : v + " %");
  const irAbiertos = (filtro) => { E.filtroAbiertos = { tecnico: "", estado: "", prioridad: "", ...filtro }; cambiarVista("abiertos"); };
  c.innerHTML = `
    <div class="filtros"><b style="font-size:16px">📊 Panel general</b>
      <label>Período <select id="p-dias">${[7, 30, 90, 365].map((d) => `<option value="${d}" ${d === E.diasPanel ? "selected" : ""}>Últimos ${d} días</option>`).join("")}</select></label>
      <span class="sep" style="flex:1"></span>
      <button class="btn" id="p-resumen">🖨 Resumen del día</button>
      <button class="btn" id="p-csv">⇩ Exportar período (CSV)</button></div>
    <div class="kpis">
      <div class="kpi clic" data-ir='{}'><b>${t.abiertos}</b><span>Abiertos ahora</span></div>
      <div class="kpi ambar clic" data-ir='{"tecnico":"0"}'><b>${t.sin_asignar}</b><span>Sin asignar</span></div>
      <div class="kpi rojo clic" data-ir='{"estado":"ATRASADO"}'><b>${t.atrasados}</b><span>Atrasados</span></div>
      <div class="kpi violeta clic" data-ir='{"estado":"EN_ESPERA"}'><b>${t.en_espera}</b><span>En espera</span></div>
      <div class="kpi"><b>${t.recibidos_hoy}</b><span>Recibidos hoy</span></div>
      <div class="kpi verde"><b>${t.resueltos_hoy}</b><span>Resueltos hoy</span></div>
      <div class="kpi"><b>${fmtDur(t.horas_asignacion)}</b><span>Tiempo medio hasta asignar (${p.dias} d)</span></div>
      <div class="kpi"><b>${fmtDur(t.horas_resolucion)}</b><span>Tiempo medio de resolución (${p.dias} d)</span></div>
      <div class="kpi verde"><b>${pct(t.en_plazo_pct)}</b><span>Resueltos dentro del objetivo (${p.dias} d)</span></div>
      <div class="kpi"><b>${t.recibidos_periodo} / ${t.resueltos_periodo}</b><span>Recibidos / resueltos (${p.dias} d)</span></div>
    </div>
    <div class="caja"><h2>Carga de trabajo por técnico</h2>
      <div class="tabla-contenedor" style="max-height:none"><table class="tabla"><thead><tr><th>Técnico</th>
        <th class="n">Asignados</th><th class="n">En proceso</th><th class="n">En espera</th><th class="n">Abiertos</th>
        <th class="n">Urgentes/altos</th><th class="n">Atrasados</th><th class="n">Más antiguo</th>
        <th class="n">Resueltos hoy</th><th class="n">Semana</th><th class="n">${p.dias} días</th>
        <th class="n">Tiempo medio</th><th class="n">En objetivo</th></tr></thead>
      <tbody>${p.por_tecnico.map((u) => `<tr>
        <td>${esc(u.nombre)}${u.rol === "JEFE" ? ' <span class="ayuda">(jefe)</span>' : ""}</td>
        <td class="n">${u.ASIGNADO}</td><td class="n">${u.EN_PROCESO}</td><td class="n">${u.EN_ESPERA}</td>
        <td class="n ${u.abiertos ? "clic" : ""}" data-tec="${u.id}"><b>${u.abiertos}</b></td>
        <td class="n">${u.urgentes}</td>
        <td class="n" style="${u.atrasados ? "color:var(--licencia);font-weight:700" : ""}">${u.atrasados}</td>
        <td class="n">${u.mas_antiguo === null ? "—" : fmtDur(u.mas_antiguo)}</td>
        <td class="n">${u.resueltos_hoy}</td><td class="n">${u.resueltos_semana}</td><td class="n">${u.resueltos_periodo}</td>
        <td class="n">${fmtDur(u.horas_promedio)}</td><td class="n">${pct(u.en_plazo_pct)}</td></tr>`).join("")}</tbody></table></div>
      <p class="ayuda">Tiempo objetivo de resolución: ${Object.entries(p.objetivos).map(([k, v]) => `${esc(E.cat.prioridades[k])} ${v} h`).join(" · ")}.
        Los tickets «En espera» no cuentan como atrasados. Se cambia en <code>configuracion.txt</code>.</p></div>
    <div class="paneles">
      <div class="caja"><h2>Abiertos por estado</h2>${barras(Object.entries(p.por_estado), (k) => E.cat.estados[k])}</div>
      <div class="caja"><h2>Abiertos por prioridad</h2>${barras(Object.entries(p.por_prioridad), (k) => E.cat.prioridades[k])}</div>
      <div class="caja"><h2>Pedidos por canal (${p.dias} d)</h2>${barras(Object.entries(p.por_canal).sort((a, b) => b[1] - a[1]), (k) => `${CANAL_ICONO[k]} ${E.cat.canales[k]}`)}</div>
      <div class="caja"><h2>Categorías más frecuentes (${p.dias} d)</h2>${barras(p.por_categoria)}</div>
      <div class="caja"><h2>Áreas que más piden (${p.dias} d)</h2>${barras(p.por_area)}</div>
    </div>
    <div class="paneles">
      <div class="caja"><h2>⏰ Atrasados</h2><div id="p-atrasados"></div></div>
      <div class="caja"><h2>📥 Sin asignar</h2><div id="p-sin"></div></div>
    </div>`;
  const mini = (el, xs, vacio) => {
    el.innerHTML = xs.length ? `<table class="tabla"><tbody>${xs.map((x) => `<tr data-id="${x.id}" style="cursor:pointer">
      <td class="num" style="color:var(--primario);font-weight:700">#${x.id}</td><td>${esc(x.asunto)}<div class="ayuda">${esc(x.tecnico || "sin asignar")} · ${esc(x.solicitante)}</div></td>
      <td>${chipPrio(x.prioridad)}</td><td class="n" style="white-space:nowrap">${fmtDur(x.horas)}</td></tr>`).join("")}</tbody></table>` : `<p class="ayuda">${vacio}</p>`;
    $$("tr[data-id]", el).forEach((tr) => (tr.onclick = () => verTicket(+tr.dataset.id)));
  };
  mini($("#p-atrasados", c), p.atrasados, "Ninguno. 👍");
  mini($("#p-sin", c), p.sin_asignar, "Ninguno.");
  $$("[data-ir]", c).forEach((k) => (k.onclick = () => irAbiertos(JSON.parse(k.dataset.ir))));
  $$("td[data-tec].clic", c).forEach((td) => (td.onclick = () => irAbiertos({ tecnico: td.dataset.tec })));
  $("#p-dias", c).onchange = async (e) => { E.diasPanel = +e.target.value; pref.guardar("diasPanel", E.diasPanel); await recargar(); };
  $("#p-resumen", c).onclick = () => window.open("/api/reporte/diario", "_blank", "noopener");
  $("#p-csv", c).onclick = () => {
    const d = new Date(); d.setDate(d.getDate() - (E.diasPanel - 1));
    location.href = `/api/tickets.csv?desde=${aLocal(d).slice(0, 10)}&hasta=${hoyIso()}`;
  };
}

function cambiarVista(v) {
  E.vista = v;
  pref.guardar("vista", v);
  dibujar();
  if (v === "panel") recargar();
}

// ── Acciones sobre tickets ────────────────────────────────────────────
async function tomar(id) {
  try { await api("POST", `/api/tickets/${id}/tomar`); toast(`Tomó el ticket #${id}.`); await recargar(); }
  catch (e) { mostrarError(e); await recargar(); }
}

async function accionRapida(id, estado) {
  try {
    const t = await api("GET", `/api/tickets/${id}`);
    if (estado === "EN_PROCESO") {
      await api("POST", `/api/tickets/${id}/estado`, { estado, version: t.version });
      toast(`Ticket #${id} en proceso.`);
      await recargar();
    } else pedirTextoEstado(t, estado);
  } catch (e) { mostrarError(e); }
}

const TEXTO_ESTADO = {
  EN_PROCESO: { titulo: "Pasar a «En proceso»", etiqueta: "Comentario (opcional)", req: false, boton: "▶ Iniciar" },
  EN_ESPERA: { titulo: "Poner «En espera»", etiqueta: "Motivo de la espera", req: true, boton: "⏸ Poner en espera",
    ayuda: "Por ejemplo: «esperando repuesto», «el usuario no está», «derivado al proveedor»." },
  RESUELTO: { titulo: "Marcar como resuelto", etiqueta: "Solución aplicada", req: true, boton: "✔ Resolver",
    ayuda: "Describa qué se hizo. Queda como nota de resolución y sirve de referencia para casos parecidos." },
  REABRIR: { titulo: "Reabrir el ticket", etiqueta: "Motivo", req: true, boton: "↺ Reabrir", ayuda: "Por ejemplo: «el problema volvió a aparecer»." },
};

function pedirTextoEstado(t, estado, alTerminar) {
  const cfg = TEXTO_ESTADO[t.estado === "RESUELTO" ? "REABRIR" : estado];
  const nuevo = t.estado === "RESUELTO" ? "EN_PROCESO" : estado;
  const { cuerpo } = modal($("#modal2"), { titulo: `${cfg.titulo} · #${t.id}`,
    cuerpo: `<p style="margin-top:0"><b>${esc(t.asunto)}</b></p>
      <label class="${cfg.req ? "req" : ""}" for="x-texto">${cfg.etiqueta}</label>
      <textarea id="x-texto" rows="4" ${cfg.req ? "required" : ""}></textarea>${cfg.ayuda ? `<p class="ayuda">${esc(cfg.ayuda)}</p>` : ""}
      ${!t.tecnico_id ? `<p class="ayuda">ℹ El ticket no tiene técnico: quedará asignado a usted.</p>` : ""}`,
    pie: [{ texto: "Cancelar" }, { texto: cfg.boton, clase: "primario", accion: async () => {
      const texto = $("#x-texto", cuerpo).value.trim();
      if (cfg.req && !texto) { $("#x-texto", cuerpo).reportValidity(); return false; }
      try {
        await api("POST", `/api/tickets/${t.id}/estado`, { estado: nuevo, texto, version: t.version });
        toast(`Ticket #${t.id}: ${E.cat.estados[nuevo].toLowerCase()}.`);
        await recargar();
        if (alTerminar) alTerminar();
      } catch (e) { mostrarError(e); return false; }
    } }] });
  setTimeout(() => $("#x-texto", cuerpo).focus(), 50);
}

function pedirAsignacion(t, alTerminar) {
  const opciones = E.cat.tecnicos.filter((u) => u.id !== t.tecnico_id)
    .map((u) => `<option value="${u.id}">${esc(u.nombre)}${u.id === E.yo.id ? " (yo)" : ""}</option>`).join("");
  const { cuerpo } = modal($("#modal2"), { titulo: `${t.tecnico_id ? "Reasignar" : "Asignar"} el ticket #${t.id}`,
    cuerpo: `<form class="form" id="f-asig">
      <label for="a-tec">Asignar a</label><select id="a-tec">${opciones}${t.tecnico_id ? `<option value="">— Liberar: vuelve a «Disponibles» sin técnico —</option>` : ""}</select>
      <label for="a-motivo">Motivo (opcional)</label><input type="text" id="a-motivo" maxlength="300" placeholder="Ej.: conoce el sistema, está en esa sede…">
    </form>${t.tecnico_id ? `<p class="ayuda">Al reasignar, el ticket vuelve a «Asignado» para que el nuevo técnico lo inicie.</p>` : ""}`,
    pie: [{ texto: "Cancelar" }, { texto: "Guardar", clase: "primario", accion: async () => {
      const v = $("#a-tec", cuerpo).value;
      try {
        await api("POST", `/api/tickets/${t.id}/asignar`, { tecnico_id: v ? +v : null, texto: $("#a-motivo", cuerpo).value, version: t.version });
        toast(v ? "Ticket asignado." : "Ticket liberado.");
        await recargar();
        if (alTerminar) alTerminar();
      } catch (e) { mostrarError(e); return false; }
    } }] });
}

function pedirAnulacion(t, alTerminar) {
  const { cuerpo } = modal($("#modal2"), { titulo: `Anular el ticket #${t.id}`,
    cuerpo: `<p style="margin-top:0">El ticket no se borra: queda <b>anulado</b> con el motivo y se conserva en el historial y la auditoría.</p>
      <label class="req" for="an-motivo">Motivo</label><textarea id="an-motivo" rows="3" required placeholder="Ej.: duplicado del #123, cargado por error…"></textarea>`,
    pie: [{ texto: "Cancelar" }, { texto: "Anular", clase: "peligro", accion: async () => {
      const motivo = $("#an-motivo", cuerpo).value.trim();
      if (motivo.length < 3) { $("#an-motivo", cuerpo).reportValidity(); toast("Indique el motivo."); return false; }
      try {
        await api("POST", `/api/tickets/${t.id}/anular`, { motivo, version: t.version });
        toast(`Ticket #${t.id} anulado.`);
        await recargar();
        if (alTerminar) alTerminar();
      } catch (e) { mostrarError(e); return false; }
    } }] });
}

// ── Ficha de un ticket ────────────────────────────────────────────────
async function verTicket(id) {
  let t;
  try { t = await api("GET", `/api/tickets/${id}`); } catch (e) { mostrarError(e); return; }
  const recargarFicha = () => verTicket(id);
  const puede = t.puede_trabajar;
  const acc = [];
  if (puede) {
    if (t.estado === "NUEVO") acc.push(["tomar", "✋ Tomar", "primario"]);
    if (["NUEVO", "ASIGNADO"].includes(t.estado)) acc.push(["EN_PROCESO", "▶ Iniciar", t.estado === "ASIGNADO" ? "primario" : ""]);
    if (t.estado === "EN_ESPERA") acc.push(["EN_PROCESO", "▶ Retomar", "primario"]);
    if (["NUEVO", "ASIGNADO", "EN_PROCESO"].includes(t.estado)) acc.push(["EN_ESPERA", "⏸ En espera", ""]);
    if (ESTADOS_ABIERTOS.includes(t.estado)) acc.push(["RESUELTO", "✔ Resolver", t.estado === "EN_PROCESO" ? "primario" : ""]);
    if (t.estado === "RESUELTO") acc.push(["REABRIR", "↺ Reabrir", ""]);
    if (ESTADOS_ABIERTOS.includes(t.estado)) acc.push(["asignar", t.tecnico_id ? "👥 Reasignar / liberar" : "👥 Asignar a…", ""]);
    acc.push(["editar", "✎ Editar datos", ""]);
  }
  if (t.puede_anular) acc.push(["anular", "Anular", "peligro"]);
  const historial = t.historial.map((h) => `<li class="${h.tipo}"><div class="quien">${fmtHora(h.creado_en)} · ${esc(h.usuario || "—")}</div>
    <div class="texto">${esc(h.texto)}</div></li>`).join("");
  const adj = t.adjuntos.map((a) => `<li>📎 <a href="/api/adjuntos/${a.id}" target="_blank" rel="noopener">${esc(a.nombre)}</a>
    <span class="ayuda">(${Math.max(1, Math.round(a.bytes / 1024))} KB · ${esc(a.usuario || "")} · ${fmtHoraCorta(a.creado_en)})</span></li>`).join("");
  const html = `
    <div class="ficha-cab"><span class="asunto">${esc(t.asunto)}</span>
      ${chipEstado(t.estado)} ${chipPrio(t.prioridad)} ${chipAtraso(t)}
      <span class="ayuda">· ${canalTxt(t.canal)} · ${t.estado === "RESUELTO" ? "resuelto en" : "abierto hace"} ${fmtDur(t.horas)} (objetivo ${t.objetivo_horas} h)</span></div>
    ${t.estado === "RESUELTO" ? `<div class="solucion"><b>✔ Solución:</b> ${esc(t.solucion)}</div>` : ""}
    ${t.estado === "EN_ESPERA" ? `<div class="espera"><b>⏸ En espera:</b> ${esc(t.motivo_espera || "")}</div>` : ""}
    ${t.estado === "ANULADO" ? `<div class="espera" style="background:var(--inhabil);color:var(--texto-suave)"><b>Anulado:</b> ${esc(t.motivo_anulacion || "")}</div>` : ""}
    ${acc.length ? `<div class="acciones-ticket">${acc.map(([k, txt, cl]) => `<button class="btn ${cl}" data-acc="${k}">${txt}</button>`).join("")}</div>`
      : `<p class="ayuda" style="margin:12px 0">ℹ Este ticket está asignado a <b>${esc(t.tecnico || "otro técnico")}</b>. Solo esa persona o el jefe pueden cambiarlo; usted puede dejar una nota.</p>`}
    <dl class="detalle">
      <dt>Solicitante</dt><dd><b>${esc(t.solicitante)}</b>${t.contacto ? ` · ${esc(t.contacto)}` : ""}</dd>
      <dt>Área</dt><dd>${esc(t.area || "—")}</dd>
      <dt>Categoría</dt><dd>${esc(t.categoria || "—")}</dd>
      <dt>Canal</dt><dd>${canalTxt(t.canal)}${t.canal_referencia ? ` · ${esc(t.canal_referencia)}` : ""}</dd>
      <dt>Técnico</dt><dd>${t.tecnico ? esc(t.tecnico) : `<span class="ayuda">sin asignar</span>`}</dd>
      <dt>Recibido</dt><dd>${fmtHora(t.recibido_en)} <span class="ayuda">(cargado por ${esc(t.creado_por_nombre || "—")} el ${fmtHora(t.creado_en)})</span></dd>
      ${t.asignado_en ? `<dt>Asignado</dt><dd>${fmtHora(t.asignado_en)}</dd>` : ""}
      ${t.iniciado_en ? `<dt>Iniciado</dt><dd>${fmtHora(t.iniciado_en)}</dd>` : ""}
      ${t.resuelto_en ? `<dt>Resuelto</dt><dd>${fmtHora(t.resuelto_en)}</dd>` : ""}
    </dl>
    ${t.descripcion ? `<h3 style="font-size:13px;margin:14px 0 0">Descripción del pedido</h3><div class="descripcion">${esc(t.descripcion)}</div>` : ""}
    <h3 style="font-size:13px;margin:14px 0 0">Adjuntos</h3>
    ${adj ? `<ul class="adjuntos">${adj}</ul>` : `<p class="ayuda" style="margin:4px 0">Ninguno.</p>`}
    ${t.estado !== "ANULADO" ? `<label class="btn chico" style="display:inline-block;margin-top:4px">📎 Adjuntar archivo<input type="file" id="v-adj" hidden></label>
      <span class="ayuda">Correo (.eml), captura o audio de WhatsApp, PDF… (máx. según configuración)</span>` : ""}
    <h3 style="font-size:13px;margin:16px 0 0">Historial y notas</h3>
    <ul class="historial">${historial}</ul>
    ${t.estado !== "ANULADO" ? `<form id="v-nota" style="display:flex;gap:8px;align-items:flex-start">
      <textarea id="v-texto" rows="2" placeholder="Agregar una nota (lo que se hizo, a quién se llamó, qué falta…)" style="flex:1"></textarea>
      <button class="btn primario">Agregar nota</button></form>` : ""}`;
  const { cuerpo, cerrar } = modal($("#modal"), { titulo: `Ticket #${t.id}`, cuerpo: html, ancho: true,
    pie: [{ texto: "🖨 Imprimir", accion: () => { window.print(); return false; } }, { texto: "Cerrar", clase: "primario" }] });
  $$("[data-acc]", cuerpo).forEach((b) => (b.onclick = async () => {
    const k = b.dataset.acc;
    if (k === "tomar") {
      try { await api("POST", `/api/tickets/${t.id}/tomar`); toast(`Tomó el ticket #${t.id}.`); await recargar(); recargarFicha(); }
      catch (e) { mostrarError(e); }
    } else if (k === "EN_PROCESO" && t.estado !== "RESUELTO") {
      try { await api("POST", `/api/tickets/${t.id}/estado`, { estado: "EN_PROCESO", version: t.version }); toast(`Ticket #${t.id} en proceso.`); await recargar(); recargarFicha(); }
      catch (e) { mostrarError(e); }
    } else if (["EN_ESPERA", "RESUELTO", "REABRIR"].includes(k)) pedirTextoEstado(t, k === "REABRIR" ? "EN_PROCESO" : k, recargarFicha);
    else if (k === "asignar") pedirAsignacion(t, recargarFicha);
    else if (k === "editar") { cerrar(); formTicket(t); }
    else if (k === "anular") pedirAnulacion(t, recargarFicha);
  }));
  const fNota = $("#v-nota", cuerpo);
  if (fNota) fNota.onsubmit = async (ev) => {
    ev.preventDefault();
    const texto = $("#v-texto", cuerpo).value.trim();
    if (!texto) return;
    try { await api("POST", `/api/tickets/${t.id}/notas`, { texto }); recargarFicha(); }
    catch (e) { mostrarError(e); }
  };
  const fAdj = $("#v-adj", cuerpo);
  if (fAdj) fAdj.onchange = async () => {
    if (!fAdj.files[0]) return;
    try { await subirAdjunto(t.id, fAdj.files[0]); toast("Archivo adjuntado."); recargarFicha(); }
    catch (e) { mostrarError(e); }
  };
}

async function subirAdjunto(tid, archivo) {
  const fd = new FormData();
  fd.append("archivo", archivo);
  return api("POST", `/api/tickets/${tid}/adjuntos`, fd);
}

// ── Formulario de alta / edición ──────────────────────────────────────
/** Lee remitente, asunto, fecha y texto de un correo .eml para completar el formulario. */
function leerEml(texto) {
  const partes = texto.split(/\r?\n\r?\n/);
  const cab = partes[0].replace(/\r?\n[ \t]+/g, " ");
  const campo = (n) => { const m = cab.match(new RegExp("^" + n + ":\\s*(.*)$", "im")); return m ? decodificarMime(m[1].trim()) : ""; };
  const fecha = campo("Date") ? new Date(campo("Date")) : null;
  let cuerpo = "";
  if (!/multipart|base64/i.test(cab)) cuerpo = partes.slice(1).join("\n\n");
  else {
    // Busca la primera parte text/plain (sin decodificar base64 de adjuntos)
    const m = texto.match(/Content-Type:\s*text\/plain[^]*?\r?\n\r?\n([^]*?)(\r?\n--)/i);
    if (m) {
      const cabParte = texto.slice(Math.max(0, m.index), m.index + m[0].indexOf(m[1]));
      cuerpo = m[1];
      if (/base64/i.test(cabParte)) { try { cuerpo = new TextDecoder().decode(Uint8Array.from(atob(cuerpo.replace(/\s+/g, "")), (c) => c.charCodeAt(0))); } catch { cuerpo = ""; } }
      else if (/quoted-printable/i.test(cabParte)) cuerpo = decodificarQP(cuerpo);
    }
  }
  const de = campo("From");
  const nombre = de.replace(/<.*>/, "").replace(/"/g, "").trim();
  const correo = (de.match(/<([^>]+)>/) || [, de.includes("@") ? de : ""])[1];
  return { nombre: nombre || correo, correo, asunto: campo("Subject"), fecha: fecha && !isNaN(fecha) ? fecha : null, cuerpo: cuerpo.trim().slice(0, 4000) };
}
function decodificarQP(s) {
  const bin = s.replace(/=\r?\n/g, "").replace(/=([0-9A-F]{2})/gi, (_, h) => String.fromCharCode(parseInt(h, 16)));
  try { return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))); } catch { return bin; }
}
function decodificarMime(s) {
  return s.replace(/=\?([^?]+)\?([BbQq])\?([^?]*)\?=/g, (_, cs, enc, txt) => {
    try {
      let bytes;
      if (enc.toUpperCase() === "B") bytes = Uint8Array.from(atob(txt), (c) => c.charCodeAt(0));
      else bytes = Uint8Array.from(txt.replace(/_/g, " ").replace(/=([0-9A-F]{2})/gi, (_, h) => String.fromCharCode(parseInt(h, 16))), (c) => c.charCodeAt(0));
      return new TextDecoder(cs).decode(bytes);
    } catch { return txt; }
  }).replace(/\?=\s+=\?/g, "");
}

async function formTicket(existente = null) {
  const t = existente || { canal: pref.leer("ultimoCanal", "TELEFONO"), prioridad: "MEDIA" };
  const nuevo = !existente;
  let solicitantes = [];
  try { solicitantes = await api("GET", "/api/solicitantes"); } catch { /* sigue sin sugerencias */ }
  const radios = (nombre, pares, sel, clase = "") => `<div class="opciones ${clase}">${pares.map(([v, txt]) =>
    `<label><input type="radio" name="${nombre}" value="${v}" ${v === sel ? "checked" : ""}>${txt}</label>`).join("")}</div>`;
  const areas = E.cat.areas.filter((a) => a.activo || a.id === t.area_id);
  const cats = E.cat.categorias.filter((c) => c.activo || c.id === t.categoria_id);
  const html = `<form class="form" id="f-ticket" autocomplete="off">
    <h3>¿Cómo llegó el pedido?</h3>
    <label class="req">Canal</label>${radios("canal", Object.entries(E.cat.canales).map(([k, v]) => [k, `${CANAL_ICONO[k]} ${v}`]), t.canal)}
    <label for="t-ref" id="l-ref">Referencia</label><div><input type="text" id="t-ref" maxlength="300" value="${esc(t.canal_referencia || "")}">
      <div class="ayuda" id="ayuda-ref"></div></div>
    <label for="t-recibido">Recibido</label><div class="fila-campos"><input type="datetime-local" id="t-recibido" value="${aLocal(t.recibido_en ? new Date(t.recibido_en) : new Date())}">
      <span class="ayuda">Cuándo llegó (si lo carga más tarde, ponga la hora real)</span></div>
    ${nuevo ? `<label>Correo .eml</label><div><div class="zona-archivo" id="t-zona" tabindex="0">✉ Arrastre aquí el correo (.eml) o una captura de WhatsApp: se adjunta al ticket
      <span class="ayuda">(del .eml se completan solos el solicitante, el asunto y la descripción)</span></div>
      <input type="file" id="t-archivo" hidden><div class="ayuda" id="t-archivo-nombre"></div></div>` : ""}
    <h3>¿Quién lo pide?</h3>
    <label for="t-sol" class="req">Solicitante</label><div><input type="text" id="t-sol" list="dl-sol" required minlength="2" maxlength="150" value="${esc(t.solicitante || "")}" placeholder="Apellido, Nombre">
      <datalist id="dl-sol">${solicitantes.map((s) => `<option value="${esc(s.solicitante)}">`).join("")}</datalist></div>
    <label for="t-contacto">Contacto</label><input type="text" id="t-contacto" maxlength="150" value="${esc(t.contacto || "")}" placeholder="Interno, celular o correo para responderle">
    <label for="t-area">Área / despacho</label><select id="t-area"><option value="">—</option>${areas.map((a) => `<option value="${a.id}" ${a.id === t.area_id ? "selected" : ""}>${esc(a.nombre)}</option>`).join("")}</select>
    <h3>¿Qué necesita?</h3>
    <label for="t-asunto" class="req">Asunto</label><input type="text" id="t-asunto" required minlength="3" maxlength="200" value="${esc(t.asunto || "")}" placeholder="Ej.: No imprime la impresora de Mesa de Entrada">
    <label for="t-cat">Categoría</label><select id="t-cat"><option value="">—</option>${cats.map((c) => `<option value="${c.id}" ${c.id === t.categoria_id ? "selected" : ""}>${esc(c.nombre)}</option>`).join("")}</select>
    <label for="t-desc">Descripción</label><textarea id="t-desc" rows="4" maxlength="10000" placeholder="Detalle del problema, mensaje de error, nº de patrimonio del equipo…">${esc(t.descripcion || "")}</textarea>
    <label class="req">Prioridad</label><div>${radios("prioridad", Object.entries(E.cat.prioridades).map(([k, v]) => [k, v]), t.prioridad, "prio")}
      <div class="ayuda">Objetivo de resolución: ${Object.entries(E.cat.objetivos).map(([k, v]) => `${esc(E.cat.prioridades[k])} ${v} h`).join(" · ")}</div></div>
    ${nuevo ? `<h3>¿Quién lo atiende?</h3>
    <label for="t-tec">Asignar a</label><select id="t-tec"><option value="">— Sin asignar (queda en «Disponibles») —</option>
      <option value="${E.yo.id}">Yo (${esc(E.yo.nombre)})</option>
      ${E.cat.tecnicos.filter((u) => u.id !== E.yo.id).map((u) => `<option value="${u.id}">${esc(u.nombre)}</option>`).join("")}</select>
    <label></label><label style="color:var(--texto)"><input type="checkbox" id="t-resuelto"> Ya se resolvió en el momento (por ejemplo, durante la llamada)</label>
    <label for="t-solucion" id="l-solucion" hidden class="req">Solución</label><textarea id="t-solucion" rows="3" hidden placeholder="Qué se hizo para resolverlo"></textarea>` : ""}
  </form>`;
  const { cuerpo } = modal($("#modal"), { titulo: nuevo ? "Nuevo ticket" : `Editar ticket #${t.id}`, cuerpo: html, ancho: true,
    pie: [{ texto: "Cancelar" }, { texto: nuevo ? "Crear ticket" : "Guardar cambios", clase: "primario", accion: guardar }] });
  const f = $("#f-ticket", cuerpo);
  let archivo = null;

  const ayudaRef = () => {
    const c = f.canal.value;
    $("#ayuda-ref", f).textContent = { TELEFONO: "Interno o número desde el que llamó.", WHATSAPP: "Número o nombre del contacto de WhatsApp.",
      CORREO: "Asunto o remitente del correo.", PRESENCIAL: "Opcional: dónde se hizo el pedido." }[c] || "";
  };
  $$("input[name=canal]", f).forEach((r) => (r.onchange = ayudaRef));
  ayudaRef();

  // Al elegir un solicitante conocido, completa el contacto y el área de la última vez
  $("#t-sol", f).addEventListener("change", () => {
    const s = solicitantes.find((x) => x.solicitante.toLowerCase() === $("#t-sol", f).value.trim().toLowerCase());
    if (!s) return;
    if (!$("#t-contacto", f).value && s.contacto) $("#t-contacto", f).value = s.contacto;
    if (!$("#t-area", f).value && s.area_id) $("#t-area", f).value = s.area_id;
  });

  if (nuevo) {
    const chk = $("#t-resuelto", f);
    chk.onchange = () => {
      $("#t-solucion", f).hidden = $("#l-solucion", f).hidden = !chk.checked;
      if (chk.checked && !$("#t-tec", f).value) $("#t-tec", f).value = String(E.yo.id);
      if (chk.checked) $("#t-solucion", f).focus();
    };
    const zona = $("#t-zona", f), input = $("#t-archivo", f);
    const elegir = async (file) => {
      if (!file) return;
      archivo = file;
      $("#t-archivo-nombre", f).textContent = `📎 Se adjuntará: ${file.name}`;
      if (/\.eml$/i.test(file.name)) {
        const d = leerEml(await file.text());
        f.canal.value = "CORREO"; ayudaRef();
        if (!$("#t-sol", f).value && d.nombre) $("#t-sol", f).value = d.nombre;
        if (!$("#t-contacto", f).value && d.correo) $("#t-contacto", f).value = d.correo;
        if (!$("#t-asunto", f).value && d.asunto) $("#t-asunto", f).value = d.asunto.slice(0, 200);
        if (!$("#t-ref", f).value) $("#t-ref", f).value = `${d.correo || d.nombre}${d.asunto ? " · " + d.asunto : ""}`.slice(0, 300);
        if (!$("#t-desc", f).value && d.cuerpo) $("#t-desc", f).value = d.cuerpo;
        if (d.fecha) $("#t-recibido", f).value = aLocal(d.fecha);
        toast("Datos tomados del correo. Revíselos antes de guardar.");
      } else if (/\.(png|jpe?g|webp|gif|opus|ogg|mp3|mp4)$/i.test(file.name) && f.canal.value !== "WHATSAPP") {
        f.canal.value = "WHATSAPP"; ayudaRef();
      }
    };
    zona.onclick = () => input.click();
    zona.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } };
    input.onchange = () => elegir(input.files[0]);
    zona.ondragover = (e) => { e.preventDefault(); zona.classList.add("encima"); };
    zona.ondragleave = () => zona.classList.remove("encima");
    zona.ondrop = (e) => { e.preventDefault(); zona.classList.remove("encima"); elegir(e.dataTransfer.files[0]); };
  }
  setTimeout(() => (nuevo ? $("#t-sol", f) : $("#t-asunto", f)).focus(), 50);

  async function guardar() {
    if (!f.reportValidity()) return false;
    const resuelto = nuevo && $("#t-resuelto", f).checked;
    if (resuelto && !$("#t-solucion", f).value.trim()) { toast("Describa la solución aplicada."); $("#t-solucion", f).focus(); return false; }
    const datos = {
      canal: f.canal.value, canal_referencia: $("#t-ref", f).value, recibido_en: $("#t-recibido", f).value,
      solicitante: $("#t-sol", f).value, contacto: $("#t-contacto", f).value,
      area_id: $("#t-area", f).value ? +$("#t-area", f).value : null,
      categoria_id: $("#t-cat", f).value ? +$("#t-cat", f).value : null,
      asunto: $("#t-asunto", f).value, descripcion: $("#t-desc", f).value, prioridad: f.prioridad.value,
    };
    if (nuevo) {
      datos.tecnico_id = $("#t-tec", f).value ? +$("#t-tec", f).value : null;
      if (resuelto) datos.solucion = $("#t-solucion", f).value;
    } else datos.version = t.version;
    try {
      const r = await enviarConConfirmacion((conf) => api(nuevo ? "POST" : "PUT", nuevo ? "/api/tickets" : `/api/tickets/${t.id}`,
        { ...datos, confirmar_advertencias: conf }));
      if (!r) return false;
      if (nuevo) {
        pref.guardar("ultimoCanal", datos.canal);
        if (archivo) { try { await subirAdjunto(r.id, archivo); } catch (e) { mostrarError(e); } }
        toast(`Ticket #${r.id} creado${resuelto ? " y resuelto" : datos.tecnico_id ? " y asignado" : ""}.`);
      } else toast("Cambios guardados.");
      await recargar();
      if (!nuevo) setTimeout(() => verTicket(t.id), 50);
    } catch (e) { mostrarError(e); return false; }
  }
}

// ── Menú del usuario ──────────────────────────────────────────────────
function acercaDe() {
  modal($("#modal"), { titulo: "Acerca del Sistema de Tickets", cuerpo: `
    <p style="font-size:16px;margin-top:0"><b>🎫 Tickets de Soporte</b> · Versión ${esc(E.yo.version)}</p>
    <p>Registra los pedidos que llegan por teléfono interno, WhatsApp, correo o en persona; los reparte entre los técnicos
      y muestra al jefe la carga de trabajo y los tiempos de atención.</p>
    <dl class="detalle">
      <dt>Desarrollado por</dt><dd><b>Sección de Servicios Informáticos</b><br>${esc(E.yo.circunscripcion)}</dd>
      <dt>Con la asistencia de</dt><dd><b>Claude</b>, inteligencia artificial de Anthropic</dd>
      <dt>Funciona</dt><dd>En la red interna, sin internet. Los datos quedan en el servidor de la institución.</dd>
      <dt>Sistema hermano</dt><dd>Pizarra de Interinatos (misma base técnica y visual)</dd>
    </dl>`, pie: [{ texto: "Cerrar", clase: "primario" }] });
}

function cambiarClave() {
  const html = `<form class="form" id="f-clave">
    <label for="c-act">Contraseña actual</label><input type="password" id="c-act" autocomplete="current-password" required>
    <label for="c-nue">Nueva contraseña</label><input type="password" id="c-nue" autocomplete="new-password" minlength="8" required>
    <label for="c-rep">Repita la nueva</label><input type="password" id="c-rep" autocomplete="new-password" minlength="8" required></form>`;
  const { cuerpo } = modal($("#modal"), { titulo: "Cambiar contraseña", cuerpo: html, pie: [{ texto: "Cancelar" }, { texto: "Guardar", clase: "primario", accion: async () => {
    const f = $("#f-clave", cuerpo);
    if (!f.reportValidity()) return false;
    if ($("#c-nue", f).value !== $("#c-rep", f).value) { toast("Las contraseñas nuevas no coinciden."); return false; }
    try { await api("POST", "/api/yo/clave", { clave_actual: $("#c-act", f).value, clave_nueva: $("#c-nue", f).value }); toast("Contraseña actualizada."); }
    catch (e) { mostrarError(e); return false; }
  } }] });
}

// ── Administración (solo JEFE) ────────────────────────────────────────
async function administrar(pestana = "usuarios") {
  const tabs = { usuarios: "Usuarios", areas: "Áreas", categorias: "Categorías", auditoria: "Auditoría" };
  const { cuerpo } = modal($("#modal"), { titulo: "Administración", ancho: true,
    cuerpo: `<div class="pestanas">${Object.entries(tabs).map(([k, t]) => `<button data-t="${k}" class="${k === pestana ? "activa" : ""}">${t}</button>`).join("")}</div><div id="adm"></div>` });
  $$(".pestanas button", cuerpo).forEach((b) => (b.onclick = () => administrar(b.dataset.t)));
  const el = $("#adm", cuerpo);
  try {
    if (pestana === "usuarios") await admUsuarios(el);
    if (pestana === "areas") await admAreas(el);
    if (pestana === "categorias") await admCategorias(el);
    if (pestana === "auditoria") await admAuditoria(el);
  } catch (e) { mostrarError(e); }
}

function formSimple(titulo, campos, valores, alGuardar) {
  const html = `<form class="form" id="f-simple">${campos.map((c) => {
    const v = valores[c.k] ?? "";
    let input;
    if (c.tipo === "select") input = `<select id="s-${c.k}" ${c.req ? "required" : ""}>${c.opciones.map(([val, txt]) => `<option value="${esc(val)}" ${String(val) === String(v) ? "selected" : ""}>${esc(txt)}</option>`).join("")}</select>`;
    else if (c.tipo === "check") input = `<label><input type="checkbox" id="s-${c.k}" ${v !== false ? "checked" : ""}> ${esc(c.ayuda || "")}</label>`;
    else input = `<input type="${c.tipo || "text"}" id="s-${c.k}" value="${esc(v)}" ${c.req ? "required" : ""} ${c.min ? `minlength="${c.min}"` : ""} ${c.patron ? `pattern="${c.patron}"` : ""}>${c.ayuda && c.tipo !== "check" ? `<div class="ayuda">${esc(c.ayuda)}</div>` : ""}`;
    return `<label class="${c.req ? "req" : ""}" for="s-${c.k}">${esc(c.t)}</label><div>${input}</div>`;
  }).join("")}</form>`;
  const { cuerpo } = modal($("#modal2"), { titulo, cuerpo: html, pie: [{ texto: "Cancelar" }, { texto: "Guardar", clase: "primario", accion: async () => {
    const f = $("#f-simple", cuerpo);
    if (!f.reportValidity()) return false;
    const datos = {};
    for (const c of campos) {
      const i = $("#s-" + c.k, f);
      datos[c.k] = c.tipo === "check" ? i.checked : i.value;
    }
    try { await alGuardar(datos); toast("Guardado."); }
    catch (e) { mostrarError(e); return false; }
  } }] });
}

async function eliminarRegistro(url, titulo, queHtml, despues) {
  const ok = await confirmar(titulo, `<p>¿Eliminar definitivamente ${queHtml}?</p>
    <p class="ayuda">La eliminación queda registrada en la auditoría.</p>`, "Eliminar");
  if (!ok) return;
  try {
    await api("DELETE", url);
    toast("Eliminado.");
    await despues();
  } catch (e) { mostrarError(e); }
}

async function admUsuarios(el) {
  const us = await api("GET", "/api/usuarios");
  const editar = (u = {}) => formSimple(u.id ? "Editar usuario" : "Nuevo usuario", [
    { k: "usuario", t: "Usuario", req: true, min: 3, patron: "[A-Za-z0-9._\\-]+", ayuda: "Sin espacios ni acentos, por ejemplo: jramirez" },
    { k: "nombre", t: "Nombre completo", req: true, min: 3 },
    { k: "rol", t: "Rol", tipo: "select", opciones: [["TECNICO", "Técnico (carga, toma y resuelve tickets)"], ["JEFE", "Jefe (además: asigna a otros, panel general, administración)"]], req: true },
    { k: "clave", t: u.id ? "Nueva contraseña" : "Contraseña", tipo: "password", req: !u.id, min: 8, ayuda: u.id ? "Déjela vacía para no cambiarla." : "Mínimo 8 caracteres. Pídale al usuario que la cambie al ingresar." },
    { k: "activo", t: "Estado", tipo: "check", ayuda: "Puede ingresar" },
  ], u, async (d) => {
    if (!d.clave) delete d.clave;
    await api(u.id ? "PUT" : "POST", u.id ? `/api/usuarios/${u.id}` : "/api/usuarios", d);
    await refrescarCatalogos();
    administrar("usuarios");
  });
  el.innerHTML = `<button class="btn primario" id="a-nuevo" style="margin-bottom:8px">+ Usuario</button>
    <div class="tabla-contenedor"><table class="tabla"><thead><tr><th>Usuario</th><th>Nombre</th><th>Rol</th><th>Alta</th><th></th></tr></thead>
    <tbody>${us.map((u) => `<tr class="${u.activo ? "" : "inactivo"}"><td>${esc(u.usuario)}</td><td>${esc(u.nombre)}</td><td>${u.rol === "JEFE" ? "Jefe" : "Técnico"}</td><td>${fmtHora(u.creado_en)}</td><td style="white-space:nowrap"><button class="btn chico" data-id="${u.id}">Editar</button>
      ${u.registros || u.id === E.yo.id ? "" : `<button class="btn chico peligro" data-borrar="${u.id}">Eliminar</button>`}</td></tr>`).join("")}</tbody></table></div>
    <p class="ayuda">«Eliminar» aparece solo en usuarios que nunca trabajaron en el sistema (por ejemplo, creados por error).
      Para quien ya trabajó, use «Editar» y desmarque «Puede ingresar»: así se conserva el historial y la auditoría.</p>`;
  $$("[data-borrar]", el).forEach((b) => (b.onclick = () => {
    const u = us.find((x) => x.id === +b.dataset.borrar);
    eliminarRegistro(`/api/usuarios/${u.id}`, "Eliminar usuario", `el usuario <b>${esc(u.usuario)}</b> (${esc(u.nombre)})`,
      async () => { await refrescarCatalogos(); administrar("usuarios"); });
  }));
  $("#a-nuevo", el).onclick = () => editar({ rol: "TECNICO", activo: true });
  $$("[data-id]", el).forEach((b) => (b.onclick = () => editar(us.find((u) => u.id === +b.dataset.id))));
}

async function admAreas(el) {
  await refrescarCatalogos();
  const xs = E.cat.areas;
  const editar = (a = {}) => formSimple(a.id ? "Editar área" : "Nueva área", [
    { k: "nombre", t: "Nombre", req: true, min: 2, ayuda: "Ej.: Juzgado de Paz - Tobatí, Mesa de Entrada…" },
    { k: "localidad", t: "Localidad" },
    { k: "interno", t: "Teléfono interno" },
    { k: "activo", t: "Estado", tipo: "check", ayuda: "Aparece en los formularios" },
  ], a, async (d) => {
    await api(a.id ? "PUT" : "POST", a.id ? `/api/areas/${a.id}` : "/api/areas", d);
    administrar("areas");
  });
  el.innerHTML = `<button class="btn primario" id="a-nuevo" style="margin-bottom:8px">+ Área</button>
    <div class="tabla-contenedor"><table class="tabla"><thead><tr><th>Nombre</th><th>Localidad</th><th>Interno</th><th>Tickets</th><th></th></tr></thead>
    <tbody>${xs.map((a) => `<tr class="${a.activo ? "" : "inactivo"}"><td>${esc(a.nombre)}</td><td>${esc(a.localidad || "")}</td><td>${esc(a.interno || "")}</td><td>${a.registros}</td>
      <td style="white-space:nowrap"><button class="btn chico" data-id="${a.id}">Editar</button>
      ${a.registros ? "" : `<button class="btn chico peligro" data-borrar="${a.id}">Eliminar</button>`}</td></tr>`).join("") || `<tr><td colspan="5" class="ayuda">Todavía no hay áreas: cargue los juzgados y oficinas que piden soporte.</td></tr>`}</tbody></table></div>`;
  $("#a-nuevo", el).onclick = () => editar({ activo: true });
  $$("[data-id]", el).forEach((b) => (b.onclick = () => editar(xs.find((a) => a.id === +b.dataset.id))));
  $$("[data-borrar]", el).forEach((b) => (b.onclick = () => {
    const a = xs.find((x) => x.id === +b.dataset.borrar);
    eliminarRegistro(`/api/areas/${a.id}`, "Eliminar área", `el área <b>${esc(a.nombre)}</b>`, async () => administrar("areas"));
  }));
}

async function admCategorias(el) {
  await refrescarCatalogos();
  const xs = E.cat.categorias;
  const editar = (c = {}) => formSimple(c.id ? "Editar categoría" : "Nueva categoría", [
    { k: "nombre", t: "Nombre", req: true, min: 2 },
    { k: "activo", t: "Estado", tipo: "check", ayuda: "Aparece en los formularios" },
  ], c, async (d) => {
    await api(c.id ? "PUT" : "POST", c.id ? `/api/categorias/${c.id}` : "/api/categorias", d);
    administrar("categorias");
  });
  el.innerHTML = `<button class="btn primario" id="a-nuevo" style="margin-bottom:8px">+ Categoría</button>
    <div class="tabla-contenedor"><table class="tabla"><thead><tr><th>Nombre</th><th>Tickets</th><th></th></tr></thead>
    <tbody>${xs.map((c) => `<tr class="${c.activo ? "" : "inactivo"}"><td>${esc(c.nombre)}</td><td>${c.registros}</td>
      <td style="white-space:nowrap"><button class="btn chico" data-id="${c.id}">Editar</button>
      ${c.registros ? "" : `<button class="btn chico peligro" data-borrar="${c.id}">Eliminar</button>`}</td></tr>`).join("")}</tbody></table></div>`;
  $("#a-nuevo", el).onclick = () => editar({ activo: true });
  $$("[data-id]", el).forEach((b) => (b.onclick = () => editar(xs.find((c) => c.id === +b.dataset.id))));
  $$("[data-borrar]", el).forEach((b) => (b.onclick = () => {
    const c = xs.find((x) => x.id === +b.dataset.borrar);
    eliminarRegistro(`/api/categorias/${c.id}`, "Eliminar categoría", `la categoría <b>${esc(c.nombre)}</b>`, async () => administrar("categorias"));
  }));
}

async function admAuditoria(el) {
  const xs = await api("GET", "/api/auditoria?limite=300");
  const resumen = (d) => Object.entries(d).filter(([, v]) => v !== null && v !== "").map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ");
  el.innerHTML = `<p class="ayuda">Últimos 300 cambios. Las advertencias confirmadas muestran qué avisos aceptó el usuario.</p>
    <div class="tabla-contenedor"><table class="tabla"><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Registro</th><th>Datos</th><th>Avisos confirmados</th></tr></thead>
    <tbody>${xs.map((x) => `<tr><td style="white-space:nowrap">${fmtHora(x.ts)}</td><td>${esc(x.usuario || "—")}</td><td>${x.accion}</td><td>${x.tabla} #${x.registro_id}</td>
      <td style="max-width:420px;overflow-wrap:anywhere">${esc(resumen(x.datos))}</td><td>${(x.advertencias_confirmadas || []).map((h) => esc(h.mensaje)).join("<br>")}</td></tr>`).join("")}</tbody></table></div>`;
}

// ── Modo TV (monitor de la oficina) ───────────────────────────────────
function modoTV() {
  const tv = $("#tv");
  const pintar = () => {
    const abiertosTv = ordenar(abiertos());
    const sin = abiertosTv.filter((t) => t.estado === "NUEVO");
    const porTec = E.cat.tecnicos.map((u) => ({ u, xs: abiertosTv.filter((t) => t.tecnico_id === u.id) })).filter((x) => x.xs.length || x.u.rol === "TECNICO");
    const hoy = new Date();
    const item = (t, conTec = false) => `<div class="item"><b>#${t.id}</b> ${esc(t.asunto)}
      ${t.prioridad === "URGENTE" ? `<span class="urg">· URGENTE</span>` : ""}${t.atrasado ? ` <span class="mal">⏰ atrasado</span>` : ""}
      <small>${CANAL_ICONO[t.canal]} ${esc(t.area || t.solicitante)} · hace ${fmtDur(t.horas)}${conTec && t.tecnico ? " · " + esc(t.tecnico) : ""}
      ${t.estado === "EN_ESPERA" ? " · ⏸ en espera" : t.estado === "EN_PROCESO" ? " · ▶ en proceso" : ""}</small></div>`;
    tv.innerHTML = `<button class="btn salir" id="tv-salir">Salir (Esc)</button>
      <h1>🎫 ${esc(E.yo.oficina)}</h1>
      <div class="fecha">${DIAS_SEMANA[hoy.getDay()]} ${fmt(hoyIso())} · ${abiertosTv.length} ticket(s) abierto(s) · ${sin.length} sin asignar · ${abiertosTv.filter((t) => t.atrasado).length} atrasado(s)</div>
      <div class="grilla-tv">
        <div class="bloque"><h2>📥 Sin asignar</h2>${sin.map((t) => item(t)).join("") || `<div class="item ok">Ninguno ✔</div>`}</div>
        ${porTec.map(({ u, xs }) => `<div class="bloque"><h2>${esc(u.nombre)} · ${xs.length}</h2>${xs.slice(0, 8).map((t) => item(t)).join("") || `<div class="item" style="opacity:.6">Sin tickets abiertos</div>`}
          ${xs.length > 8 ? `<div class="item" style="opacity:.6">y ${xs.length - 8} más…</div>` : ""}</div>`).join("")}
      </div>`;
    $("#tv-salir").onclick = salir;
  };
  const salir = () => { tv.hidden = true; document.exitFullscreen?.().catch(() => {}); dibujar(); };
  modoTV.salir = salir;
  modoTV.pintar = pintar;   // la actualización automática la repinta cada pocos segundos
  pintar();
  tv.hidden = false;
  tv.requestFullscreen?.().catch(() => {});
}

// ── Eventos ───────────────────────────────────────────────────────────
function conectarEventos() {
  $$("#vistas button").forEach((b) => (b.onclick = () => cambiarVista(b.dataset.vista)));
  $("#btn-nuevo").onclick = () => formTicket();
  let t;
  $("#f-rapido").oninput = () => { clearTimeout(t); t = setTimeout(dibujar, 150); };
  $("#btn-tv").onclick = modoTV;
  $("#btn-sonido").onclick = () => { E.sonido = !E.sonido; pref.guardar("sonido", E.sonido); pintarSonido(); if (E.sonido) sonar(); };
  const menu = $("#menu-usuario");
  $("#btn-usuario").onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; };
  document.addEventListener("click", () => (menu.hidden = true));
  $("#m-admin").onclick = () => administrar();
  $("#m-clave").onclick = cambiarClave;
  $("#m-manual").onclick = () => window.open("/manual", "_blank", "noopener");
  $("#m-acerca").onclick = acercaDe;
  $("#m-salir").onclick = async () => { await api("POST", "/api/logout").catch(() => {}); location.href = "/login"; };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#tv").hidden) { modoTV.salir(); return; }
    if ($("#modal").open || $("#modal2").open || !$("#tv").hidden) return;
    if (e.target.matches("input, select, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === "n") { e.preventDefault(); formTicket(); }
    else if (k === "/") { e.preventDefault(); $("#f-rapido").focus(); }
  });
}

iniciar();
