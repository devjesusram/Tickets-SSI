"""API y servidor web del Sistema de Tickets de tareas."""
import csv
import io
import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import __version__, auth, config, db, indicadores, servicios
from .auth import requiere_jefe, usuario_actual
from .db import booleanos, escritura, todos, uno
from .reglas import (NOMBRE_CANAL, NOMBRE_ESTADO, NOMBRE_PRIORIDAD, Bloqueado,
                     ConflictoVersion, RequiereConfirmacion, SinPermiso, puede_trabajar)

STATIC = Path(__file__).parent / "static"
EXT_ADJUNTOS = {".pdf", ".eml", ".msg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".log",
                ".docx", ".doc", ".xlsx", ".xls", ".odt", ".ods", ".zip", ".opus", ".ogg", ".mp3", ".mp4"}


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    db.inicializar_esquema()
    config.ADJUNTOS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Sistema de Tickets de tareas", lifespan=ciclo_de_vida,
              docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")


# ── Manejo de errores ──────────────────────────────────────────────────

@app.exception_handler(Bloqueado)
def _h_bloqueado(_, e: Bloqueado):
    return JSONResponse({"tipo": "BLOQUEO", "hallazgos": [h.a_dict() for h in e.hallazgos]}, 409)


@app.exception_handler(RequiereConfirmacion)
def _h_confirmar(_, e: RequiereConfirmacion):
    return JSONResponse({"tipo": "CONFIRMAR", "hallazgos": [h.a_dict() for h in e.hallazgos]}, 428)


@app.exception_handler(ConflictoVersion)
def _h_version(_, e: ConflictoVersion):
    return JSONResponse({"tipo": "VERSION", "hallazgos": [
        {"nivel": "BLOQUEO", "regla": "T8", "mensaje": str(e)}]}, 409)


@app.exception_handler(SinPermiso)
def _h_permiso(_, e: SinPermiso):
    return JSONResponse({"detail": str(e)}, 403)


@app.exception_handler(LookupError)
def _h_no_existe(_, e: LookupError):
    return JSONResponse({"detail": str(e)}, 404)


# ── Modelos ────────────────────────────────────────────────────────────

def _vacio_a_none(v):
    return None if isinstance(v, str) and not v.strip() else v


class TicketIn(BaseModel):
    canal: Literal["TELEFONO", "WHATSAPP", "CORREO", "PRESENCIAL"]
    canal_referencia: Optional[str] = Field(default=None, max_length=300)
    solicitante: str = Field(min_length=2, max_length=150)
    contacto: Optional[str] = Field(default=None, max_length=150)
    area_id: Optional[int] = None
    categoria_id: Optional[int] = None
    asunto: str = Field(min_length=3, max_length=200)
    descripcion: Optional[str] = Field(default=None, max_length=10000)
    prioridad: Literal["URGENTE", "ALTA", "MEDIA", "BAJA"] = "MEDIA"
    recibido_en: Optional[datetime] = None     # vacío = ahora
    tecnico_id: Optional[int] = None           # solo al crear: vacío = sin asignar
    solucion: Optional[str] = Field(default=None, max_length=10000)   # solo al crear: resuelto en el momento
    confirmar_advertencias: bool = False
    version: Optional[int] = None

    _limpiar = field_validator("canal_referencia", "contacto", "descripcion", "recibido_en", "solucion",
                               "area_id", "categoria_id", "tecnico_id", mode="before")(_vacio_a_none)


class EstadoIn(BaseModel):
    estado: Literal["EN_PROCESO", "EN_ESPERA", "RESUELTO"]
    texto: Optional[str] = Field(default=None, max_length=10000)
    version: int


class AsignarIn(BaseModel):
    tecnico_id: Optional[int] = None           # vacío = liberar (vuelve a disponibles)
    texto: Optional[str] = Field(default=None, max_length=1000)
    version: int


class AnularIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=1000)
    version: int


class NotaIn(BaseModel):
    texto: str = Field(min_length=1, max_length=10000)


class LoginIn(BaseModel):
    usuario: str
    clave: str


class UsuarioIn(BaseModel):
    usuario: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    nombre: str = Field(min_length=3)
    rol: Literal["JEFE", "TECNICO"]
    activo: bool = True
    clave: Optional[str] = None


class ClaveIn(BaseModel):
    clave_actual: Optional[str] = None
    clave_nueva: str


class AreaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    localidad: Optional[str] = None
    interno: Optional[str] = None
    activo: bool = True

    _limpiar = field_validator("localidad", "interno", mode="before")(_vacio_a_none)


class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    activo: bool = True


# ── Sesión ─────────────────────────────────────────────────────────────

@app.post("/api/login")
def login(body: LoginIn, response: Response):
    with db.conexion() as conn:
        token = auth.iniciar_sesion(conn, body.usuario, body.clave)
    if not token:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="strict",
                        secure=config.COOKIE_SEGURA, max_age=config.SESION_HORAS * 3600)
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(auth.COOKIE)
    if token:
        with db.conexion() as conn:
            auth.cerrar_sesion(conn, token)
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@app.get("/api/yo")
def yo(u=Depends(usuario_actual)):
    return {**u, "hoy": indicadores.hoy_local(), "circunscripcion": config.NOMBRE_CIRCUNSCRIPCION,
            "oficina": config.NOMBRE_OFICINA, "version": __version__}


@app.post("/api/yo/clave")
def cambiar_mi_clave(body: ClaveIn, u=Depends(usuario_actual)):
    auth.validar_clave_nueva(body.clave_nueva)
    with db.conexion() as conn:
        r = uno(conn, "SELECT hash_clave FROM usuarios WHERE id = ?", (u["id"],))
        if not auth.verificar_clave(body.clave_actual or "", r["hash_clave"]):
            raise HTTPException(400, "La contraseña actual no es correcta.")
        with escritura(conn):
            conn.execute("UPDATE usuarios SET hash_clave = ? WHERE id = ?",
                         (auth.hash_clave(body.clave_nueva), u["id"]))
    return {"ok": True}


# ── Catálogos ──────────────────────────────────────────────────────────

SQL_USOS_AREA = "(SELECT count(*) FROM tickets t WHERE t.area_id = a.id)"
SQL_USOS_CATEGORIA = "(SELECT count(*) FROM tickets t WHERE t.categoria_id = c.id)"
SQL_USOS_USUARIO = """(SELECT count(*) FROM auditoria x WHERE x.usuario_id = u.id)
    + (SELECT count(*) FROM tickets t WHERE u.id IN (t.tecnico_id, t.creado_por, t.modificado_por))
    + (SELECT count(*) FROM notas n WHERE n.usuario_id = u.id)"""


@app.get("/api/catalogos")
def catalogos(u=Depends(usuario_actual)):
    with db.conexion() as conn:
        return {
            "areas": booleanos(todos(conn, f"SELECT a.*, {SQL_USOS_AREA} AS registros FROM areas a "
                                           "ORDER BY a.nombre"), "activo"),
            "categorias": booleanos(todos(conn, f"SELECT c.*, {SQL_USOS_CATEGORIA} AS registros FROM categorias c "
                                                "ORDER BY c.nombre = 'Otro', c.nombre"), "activo"),
            "tecnicos": todos(conn, "SELECT id, nombre, rol FROM usuarios WHERE activo = 1 ORDER BY nombre"),
            "canales": NOMBRE_CANAL, "estados": NOMBRE_ESTADO, "prioridades": NOMBRE_PRIORIDAD,
            "objetivos": config.OBJETIVO_HORAS, "alerta_sin_asignar_min": config.ALERTA_SIN_ASIGNAR_MIN,
        }


@app.get("/api/solicitantes")
def solicitantes(u=Depends(usuario_actual)):
    """Solicitantes anteriores (para completar rápido el formulario): el último contacto y área usados."""
    with db.conexion() as conn:
        return todos(conn, """SELECT t.solicitante, t.contacto, t.area_id
                              FROM tickets t
                              JOIN (SELECT lower(solicitante) AS s, max(id) AS id FROM tickets
                                    WHERE estado <> 'ANULADO' GROUP BY lower(solicitante)) x ON x.id = t.id
                              ORDER BY t.id DESC LIMIT 500""")


# ── Tickets ────────────────────────────────────────────────────────────

@app.get("/api/tablero")
def ver_tablero(u=Depends(usuario_actual)):
    """Abiertos + movidos en los últimos 7 días. La interfaz lo consulta cada 15 segundos."""
    with db.conexion() as conn:
        return {"ahora": db.ahora_utc(), "hoy": indicadores.hoy_local(), "tickets": indicadores.tablero(conn)}


def _filtros(desde, hasta, estado, tecnico_id, canal, area_id, categoria_id, prioridad, q):
    if desde and hasta and hasta < desde:
        raise HTTPException(400, "Rango de fechas inválido.")
    return dict(desde=desde, hasta=hasta, estado=estado, tecnico_id=tecnico_id, canal=canal, area_id=area_id,
                categoria_id=categoria_id, prioridad=prioridad, texto=q)


@app.get("/api/tickets")
def buscar_tickets(desde: Optional[date] = None, hasta: Optional[date] = None, estado: Optional[str] = None,
                   tecnico_id: Optional[int] = None, canal: Optional[str] = None, area_id: Optional[int] = None,
                   categoria_id: Optional[int] = None, prioridad: Optional[str] = None, q: Optional[str] = None,
                   limite: int = Query(500, ge=1, le=5000), u=Depends(usuario_actual)):
    with db.conexion() as conn:
        return indicadores.buscar(conn, **_filtros(desde, hasta, estado, tecnico_id, canal, area_id,
                                                   categoria_id, prioridad, q), limite=limite)


@app.get("/api/tickets.csv")
def exportar_csv(desde: Optional[date] = None, hasta: Optional[date] = None, estado: Optional[str] = None,
                 tecnico_id: Optional[int] = None, canal: Optional[str] = None, area_id: Optional[int] = None,
                 categoria_id: Optional[int] = None, prioridad: Optional[str] = None, q: Optional[str] = None,
                 u=Depends(usuario_actual)):
    """Planilla para Excel (separador «;» y acentos correctos)."""
    with db.conexion() as conn:
        filas = indicadores.buscar(conn, **_filtros(desde, hasta, estado, tecnico_id, canal, area_id,
                                                    categoria_id, prioridad, q), limite=100000)

    def local(ts):
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(config.ZONA).strftime(
            "%d/%m/%Y %H:%M") if ts else ""

    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";")
    w.writerow(["Nº", "Recibido", "Canal", "Referencia", "Solicitante", "Contacto", "Área", "Categoría", "Asunto",
                "Descripción", "Prioridad", "Estado", "Técnico", "Asignado", "Resuelto", "Horas", "Atrasado",
                "Solución", "Cargado por"])
    for t in filas:
        w.writerow([t["id"], local(t["recibido_en"]), NOMBRE_CANAL[t["canal"]], t["canal_referencia"] or "",
                    t["solicitante"], t["contacto"] or "", t["area"] or "", t["categoria"] or "", t["asunto"],
                    t["descripcion"] or "", NOMBRE_PRIORIDAD[t["prioridad"]], NOMBRE_ESTADO[t["estado"]],
                    t["tecnico"] or "", local(t["asignado_en"]), local(t["resuelto_en"]),
                    str(t["horas"]).replace(".", ","), "Sí" if t["atrasado"] or t["fuera_de_plazo"] else "",
                    t["solucion"] or t["motivo_anulacion"] or "", t["creado_por_nombre"] or ""])
    nombre = f"tickets_{desde or 'inicio'}_{hasta or indicadores.hoy_local()}.csv"
    return Response("﻿" + salida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@app.get("/api/tickets/{tid}")
def ver_ticket(tid: int, u=Depends(usuario_actual)):
    with db.conexion() as conn:
        t = uno(conn, indicadores.SQL_TICKET + " WHERE t.id = ?", (tid,))
        if not t:
            raise HTTPException(404, f"El ticket #{tid} no existe.")
        indicadores.enriquecer(t, indicadores.ahora_utc())
        t["historial"] = todos(conn, """SELECT n.*, u.nombre AS usuario FROM notas n
                                        LEFT JOIN usuarios u ON u.id = n.usuario_id
                                        WHERE n.ticket_id = ? ORDER BY n.id""", (tid,))
        t["adjuntos"] = todos(conn, """SELECT j.id, j.nombre, j.bytes, j.creado_en, u.nombre AS usuario
                                       FROM adjuntos j LEFT JOIN usuarios u ON u.id = j.subido_por
                                       WHERE j.ticket_id = ? ORDER BY j.id""", (tid,))
    t["puede_trabajar"] = t["estado"] != "ANULADO" and puede_trabajar(t, u)
    t["puede_anular"] = t["estado"] != "ANULADO" and (u["rol"] == "JEFE" or t["creado_por"] == u["id"])
    return t


@app.post("/api/tickets", status_code=201)
def crear_ticket(body: TicketIn, u=Depends(usuario_actual)):
    with db.conexion() as conn:
        tid, avisos = servicios.crear_ticket(conn, body.model_dump(), u, body.confirmar_advertencias)
    return {"id": tid, "avisos": avisos}


@app.put("/api/tickets/{tid}")
def editar_ticket(tid: int, body: TicketIn, u=Depends(usuario_actual)):
    if body.version is None:
        raise HTTPException(400, "Falta la versión del registro.")
    with db.conexion() as conn:
        servicios.editar_ticket(conn, tid, body.model_dump(), body.version, u, body.confirmar_advertencias)
    return {"id": tid}


@app.post("/api/tickets/{tid}/tomar")
def tomar_ticket(tid: int, u=Depends(usuario_actual)):
    with db.conexion() as conn:
        servicios.tomar(conn, tid, u)
    return {"ok": True}


@app.post("/api/tickets/{tid}/asignar")
def asignar_ticket(tid: int, body: AsignarIn, u=Depends(usuario_actual)):
    with db.conexion() as conn:
        servicios.asignar(conn, tid, body.tecnico_id, body.version, u, body.texto)
    return {"ok": True}


@app.post("/api/tickets/{tid}/estado")
def cambiar_estado(tid: int, body: EstadoIn, u=Depends(usuario_actual)):
    with db.conexion() as conn:
        servicios.cambiar_estado(conn, tid, body.estado, body.texto, body.version, u)
    return {"ok": True}


@app.post("/api/tickets/{tid}/anular")
def anular_ticket(tid: int, body: AnularIn, u=Depends(usuario_actual)):
    with db.conexion() as conn:
        servicios.anular(conn, tid, body.motivo, body.version, u)
    return {"ok": True}


@app.post("/api/tickets/{tid}/notas", status_code=201)
def agregar_nota(tid: int, body: NotaIn, u=Depends(usuario_actual)):
    if not body.texto.strip():
        raise HTTPException(400, "La nota está vacía.")
    with db.conexion() as conn:
        nid = servicios.agregar_nota(conn, tid, body.texto, u)
    return {"id": nid}


@app.post("/api/tickets/{tid}/adjuntos", status_code=201)
async def subir_adjunto(tid: int, archivo: UploadFile = File(...), u=Depends(usuario_actual)):
    nombre = Path(archivo.filename or "archivo").name[:200]
    ext = Path(nombre).suffix.lower()
    if ext not in EXT_ADJUNTOS:
        raise HTTPException(400, f"Tipo de archivo no permitido ({ext or 'sin extensión'}). "
                                 "Se aceptan PDF, correos (.eml/.msg), imágenes, audios de WhatsApp y documentos.")
    contenido = await archivo.read(config.ADJUNTO_MAX_MB * 1024 * 1024 + 1)
    if len(contenido) > config.ADJUNTO_MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"El archivo supera el máximo de {config.ADJUNTO_MAX_MB} MB.")
    if not contenido:
        raise HTTPException(400, "El archivo está vacío.")
    guardado = f"{uuid.uuid4().hex}{ext}"
    config.ADJUNTOS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = config.ADJUNTOS_DIR / guardado
    ruta.write_bytes(contenido)
    try:
        with db.conexion() as conn:
            aid = servicios.registrar_adjunto(conn, tid, nombre, guardado, len(contenido), u)
    except BaseException:
        ruta.unlink(missing_ok=True)
        raise
    return {"id": aid}


@app.get("/api/adjuntos/{aid}")
def descargar_adjunto(aid: int, u=Depends(usuario_actual)):
    with db.conexion() as conn:
        r = uno(conn, "SELECT nombre, archivo FROM adjuntos WHERE id = ?", (aid,))
    if not r:
        raise HTTPException(404, "Adjunto inexistente")
    ruta = config.ADJUNTOS_DIR / Path(r["archivo"]).name
    if not ruta.is_file():
        raise HTTPException(404, "El archivo ya no está en el servidor (¿se restauró un respaldo sin adjuntos?).")
    return FileResponse(ruta, filename=r["nombre"])


# ── Panel del jefe y reportes ──────────────────────────────────────────

@app.get("/api/panel")
def ver_panel(dias: int = Query(30, ge=1, le=366), u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return indicadores.panel(conn, dias)


@app.get("/api/reporte/diario", response_class=HTMLResponse)
def reporte_diario(fecha: Optional[date] = None, u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        r = indicadores.resumen_diario(conn, fecha or indicadores.hoy_local())
    return HTMLResponse(indicadores.resumen_html(r))


# ── Administración (solo JEFE) ─────────────────────────────────────────

def _guardar(conn, sql, params, tabla, accion, uid, registro_id=None):
    try:
        with escritura(conn):
            cur = conn.execute(sql, params)
            rid = registro_id or cur.lastrowid
            if registro_id and cur.rowcount == 0:
                raise HTTPException(404, "Registro inexistente")
            servicios.auditar(conn, tabla, rid, accion, {k: v for k, v in params.items() if k != "h"}, uid)
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise HTTPException(409, "Ya existe un registro con ese nombre.")
        raise HTTPException(409, f"No se pudo guardar: {e}")
    return {"id": rid}


def _bool01(d: dict) -> dict:
    return {k: (1 if v is True else 0 if v is False else v) for k, v in d.items()}


def _eliminar(conn, tabla: str, rid: int, sql_usos: str, alias: str, que: str, alternativa: str, uid: int):
    """Borra un registro SOLO si no tiene nada asociado. Queda en la auditoría con sus datos."""
    with escritura(conn):
        fila = uno(conn, f"SELECT {alias}.*, {sql_usos} AS registros FROM {tabla} {alias} WHERE {alias}.id = ?", (rid,))
        if not fila:
            raise HTTPException(404, f"{que} inexistente")
        if fila["registros"]:
            raise HTTPException(409, f"No se puede eliminar: tiene {fila['registros']} registro(s) asociado(s). {alternativa}")
        try:
            conn.execute(f"DELETE FROM {tabla} WHERE id = ?", (rid,))
        except sqlite3.IntegrityError:
            raise HTTPException(409, f"No se puede eliminar: tiene registros asociados. {alternativa}")
        fila.pop("registros")
        fila.pop("hash_clave", None)
        servicios.auditar(conn, tabla, rid, "ELIMINAR", fila, uid)
    return {"ok": True}


@app.post("/api/areas", status_code=201)
def crear_area(body: AreaIn, u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return _guardar(conn, "INSERT INTO areas (nombre, localidad, interno, activo) "
                              "VALUES (:nombre, :localidad, :interno, :activo)",
                        _bool01(body.model_dump()), "areas", "CREAR", u["id"])


@app.put("/api/areas/{aid}")
def editar_area(aid: int, body: AreaIn, u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return _guardar(conn, "UPDATE areas SET nombre = :nombre, localidad = :localidad, interno = :interno, "
                              "activo = :activo WHERE id = :id",
                        {**_bool01(body.model_dump()), "id": aid}, "areas", "MODIFICAR", u["id"], aid)


@app.delete("/api/areas/{aid}")
def eliminar_area(aid: int, u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return _eliminar(conn, "areas", aid, SQL_USOS_AREA, "a", "Área",
                         "Desmárquela como activa para que no aparezca en los formularios.", u["id"])


@app.post("/api/categorias", status_code=201)
def crear_categoria(body: CategoriaIn, u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return _guardar(conn, "INSERT INTO categorias (nombre, activo) VALUES (:nombre, :activo)",
                        _bool01(body.model_dump()), "categorias", "CREAR", u["id"])


@app.put("/api/categorias/{cid}")
def editar_categoria(cid: int, body: CategoriaIn, u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return _guardar(conn, "UPDATE categorias SET nombre = :nombre, activo = :activo WHERE id = :id",
                        {**_bool01(body.model_dump()), "id": cid}, "categorias", "MODIFICAR", u["id"], cid)


@app.delete("/api/categorias/{cid}")
def eliminar_categoria(cid: int, u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return _eliminar(conn, "categorias", cid, SQL_USOS_CATEGORIA, "c", "Categoría",
                         "Desmárquela como activa para que no aparezca en los formularios.", u["id"])


@app.get("/api/usuarios")
def listar_usuarios(u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        return booleanos(todos(conn, f"SELECT u.id, u.usuario, u.nombre, u.rol, u.activo, u.creado_en, "
                                     f"({SQL_USOS_USUARIO}) AS registros FROM usuarios u ORDER BY nombre"), "activo")


@app.post("/api/usuarios", status_code=201)
def crear_usuario(body: UsuarioIn, u=Depends(requiere_jefe)):
    auth.validar_clave_nueva(body.clave)
    datos = _bool01(body.model_dump(exclude={"clave"}))
    datos["usuario"] = datos["usuario"].strip().lower()
    with db.conexion() as conn:
        return _guardar(conn, """INSERT INTO usuarios (usuario, nombre, rol, activo, hash_clave)
                                 VALUES (:usuario, :nombre, :rol, :activo, :h)""",
                        {**datos, "h": auth.hash_clave(body.clave)}, "usuarios", "CREAR", u["id"])


@app.put("/api/usuarios/{uid}")
def editar_usuario(uid: int, body: UsuarioIn, u=Depends(requiere_jefe)):
    if uid == u["id"] and (body.rol != "JEFE" or not body.activo):
        raise HTTPException(400, "No puede quitarse a sí mismo el rol de jefe ni desactivarse.")
    if body.clave:
        auth.validar_clave_nueva(body.clave)
    datos = _bool01(body.model_dump(exclude={"clave"}))
    datos["usuario"] = datos["usuario"].strip().lower()
    with db.conexion() as conn:
        r = _guardar(conn, """UPDATE usuarios SET usuario = :usuario, nombre = :nombre,
                                rol = :rol, activo = :activo WHERE id = :id""",
                     {**datos, "id": uid}, "usuarios", "MODIFICAR", u["id"], uid)
        with escritura(conn):
            if body.clave:
                conn.execute("UPDATE usuarios SET hash_clave = ? WHERE id = ?", (auth.hash_clave(body.clave), uid))
            if body.clave or not body.activo:
                conn.execute("DELETE FROM sesiones WHERE usuario_id = ?", (uid,))
        return r


@app.delete("/api/usuarios/{uid}")
def eliminar_usuario(uid: int, u=Depends(requiere_jefe)):
    if uid == u["id"]:
        raise HTTPException(400, "No puede eliminarse a sí mismo.")
    with db.conexion() as conn:
        with escritura(conn):
            conn.execute("DELETE FROM sesiones WHERE usuario_id = ?", (uid,))
        return _eliminar(conn, "usuarios", uid, f"({SQL_USOS_USUARIO})", "u", "Usuario",
                         "Edítelo y desmarque «Puede ingresar» para conservar la auditoría.", u["id"])


@app.get("/api/auditoria")
def ver_auditoria(limite: int = Query(300, le=2000), u=Depends(requiere_jefe)):
    with db.conexion() as conn:
        filas = todos(conn, """SELECT a.*, u.nombre AS usuario FROM auditoria a
                               LEFT JOIN usuarios u ON u.id = a.usuario_id
                               ORDER BY a.id DESC LIMIT ?""", (limite,))
    for f in filas:
        f["datos"] = json.loads(f["datos"])
        f["advertencias_confirmadas"] = json.loads(f["advertencias_confirmadas"]) if f["advertencias_confirmadas"] else None
    return filas


# ── Páginas ────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(STATIC / "index.html")


@app.get("/login", include_in_schema=False)
def pagina_login():
    return FileResponse(STATIC / "login.html")


@app.get("/manual", include_in_schema=False)
def pagina_manual():
    """Manual de usuario (no requiere sesión: no contiene datos reales)."""
    return FileResponse(STATIC / "manual.html")


@app.get("/salud", include_in_schema=False)
def salud():
    with db.conexion() as conn:
        conn.execute("SELECT 1")
    return {"ok": True, "sistema": "tickets", "version": __version__}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def cabeceras(request: Request, call_next):
    resp = await call_next(request)
    ruta = request.url.path
    if ruta.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    elif ruta.startswith("/static/") or ruta in ("/", "/login", "/manual"):
        # El navegador puede guardar la página, pero debe preguntar si cambió antes de usarla:
        # así, después de actualizar el sistema, todos ven la versión nueva sin Ctrl+F5.
        resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@app.exception_handler(401)
def _h_401(request: Request, e):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": e.detail}, 401)
    return RedirectResponse("/login")
