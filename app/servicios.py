"""Operaciones sobre tickets: alta, edición, asignación, estados, notas y anulación.

Cada operación:
  · corre dentro de una transacción de escritura exclusiva (db.escritura), así dos
    técnicos que guardan a la vez se atienden de a uno;
  · controla la «version» del ticket (si otro lo cambió mientras se editaba, avisa);
  · deja una línea en el historial del ticket (tabla notas) y otra en la auditoría.
"""
import json
from datetime import datetime, timedelta, timezone

from . import db
from .db import escritura, uno
from .reglas import (ABIERTOS, NOMBRE_ESTADO, Bloqueado, ConflictoVersion, Hallazgo, RequiereConfirmacion,
                     SinPermiso, bloquear, exigir_no_anulado, exigir_permiso, validar_transicion)

CAMPOS_EDITABLES = ("canal", "canal_referencia", "solicitante", "contacto", "area_id", "categoria_id",
                    "asunto", "descripcion", "prioridad", "recibido_en")


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def auditar(conn, tabla, registro_id, accion, datos, usuario_id, hallazgos=None):
    conn.execute("""INSERT INTO auditoria (tabla, registro_id, accion, datos,
                                           advertencias_confirmadas, usuario_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                 (tabla, registro_id, accion, _json(datos),
                  _json([h.a_dict() for h in hallazgos]) if hallazgos else None, usuario_id))


def historial(conn, ticket_id: int, tipo: str, texto: str, usuario_id: int) -> None:
    conn.execute("INSERT INTO notas (ticket_id, tipo, texto, usuario_id) VALUES (?, ?, ?, ?)",
                 (ticket_id, tipo, texto, usuario_id))


def a_utc(valor) -> str:
    """Convierte una fecha y hora (con o sin zona) a texto UTC «aaaa-mm-ddThh:mm:ssZ».
    Sin zona se interpreta como hora local de la institución."""
    from . import config
    if valor is None:
        return db.ahora_utc()
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=config.ZONA)
    return valor.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def de_utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def obtener(conn, tid: int) -> dict:
    t = uno(conn, "SELECT * FROM tickets WHERE id = ?", (tid,))
    if not t:
        raise LookupError(f"El ticket #{tid} no existe.")
    return t


def _controlar_version(t: dict, version: int | None) -> None:
    if version is not None and version != t["version"]:
        raise ConflictoVersion(f"Otro usuario modificó el ticket #{t['id']} mientras usted lo tenía abierto. "
                               "Ciérrelo y vuelva a abrirlo para ver los cambios.")


def _tecnico(conn, tecnico_id: int | None) -> dict | None:
    """T1: el técnico debe existir y estar activo."""
    if tecnico_id is None:
        return None
    u = uno(conn, "SELECT id, nombre, rol, activo FROM usuarios WHERE id = ?", (tecnico_id,))
    if not u or not u["activo"]:
        bloquear("T1", "El técnico elegido no existe o está desactivado.")
    return u


def _nombre(conn, uid: int | None) -> str:
    if uid is None:
        return "nadie"
    r = uno(conn, "SELECT nombre FROM usuarios WHERE id = ?", (uid,))
    return r["nombre"] if r else f"usuario {uid}"


def _advertencias_alta(conn, datos: dict, excluir_id: int | None = None) -> list[Hallazgo]:
    """T6 (posible duplicado) y T7 (fecha de recepción)."""
    hs: list[Hallazgo] = []
    recibido = de_utc(datos["recibido_en"])
    ahora = datetime.now(timezone.utc)
    if recibido > ahora + timedelta(minutes=5):
        bloquear("T7", "La fecha y hora de recepción no puede ser posterior a este momento.")
    if recibido < ahora - timedelta(days=30):
        hs.append(Hallazgo("ADVERTENCIA", "T7", "La fecha de recepción tiene más de 30 días. ¿Es correcta?"))
    marcas = ",".join("?" * len(ABIERTOS))
    params: list = [*ABIERTOS, datos["solicitante"].strip()]
    filtro_area = ""
    if datos.get("area_id") and datos.get("categoria_id"):
        filtro_area = " OR (area_id = ? AND categoria_id = ?)"
        params += [datos["area_id"], datos["categoria_id"]]
    excluir = ""
    if excluir_id:
        excluir = " AND id <> ?"
        params.append(excluir_id)
    parecidos = db.todos(conn, f"""SELECT id, asunto FROM tickets
                                  WHERE estado IN ({marcas})
                                    AND (lower(solicitante) = lower(?){filtro_area}){excluir}
                                  ORDER BY id DESC LIMIT 5""", params)
    if parecidos:
        lista = "; ".join(f"#{p['id']} «{p['asunto']}»" for p in parecidos)
        hs.append(Hallazgo("ADVERTENCIA", "T6",
                           f"Posible duplicado: ya hay tickets abiertos del mismo solicitante o del mismo área "
                           f"y categoría ({lista}). Si es el mismo pedido, agregue una nota a ese ticket en lugar "
                           "de crear otro."))
    return hs


def _confirmar(hallazgos: list[Hallazgo], confirmar: bool) -> None:
    if hallazgos and not confirmar:
        raise RequiereConfirmacion(hallazgos)


# ── Alta y edición ─────────────────────────────────────────────────────

def crear_ticket(conn, datos: dict, usuario: dict, confirmar_advertencias: bool = False) -> tuple[int, list]:
    """Crea un ticket. Si trae técnico, queda ASIGNADO. Si trae solución, queda RESUELTO
    (pedidos que se resuelven en el momento, durante la llamada)."""
    datos = {**datos}
    datos["solicitante"] = datos["solicitante"].strip()
    datos["asunto"] = datos["asunto"].strip()
    datos["recibido_en"] = a_utc(datos.get("recibido_en"))
    solucion = (datos.pop("solucion", None) or "").strip() or None
    with escritura(conn):
        tecnico = _tecnico(conn, datos.get("tecnico_id"))
        if solucion and not tecnico:
            tecnico = _tecnico(conn, usuario["id"])          # lo resolvió quien lo carga
            datos["tecnico_id"] = usuario["id"]
        hs = _advertencias_alta(conn, datos)
        _confirmar(hs, confirmar_advertencias)
        ahora = db.ahora_utc()
        estado = "RESUELTO" if solucion else ("ASIGNADO" if tecnico else "NUEVO")
        tid = conn.execute(
            """INSERT INTO tickets (canal, canal_referencia, solicitante, contacto, area_id, categoria_id, asunto,
                                    descripcion, prioridad, estado, tecnico_id, solucion, recibido_en, asignado_en,
                                    iniciado_en, resuelto_en, creado_por)
               VALUES (:canal, :canal_referencia, :solicitante, :contacto, :area_id, :categoria_id, :asunto,
                       :descripcion, :prioridad, :estado, :tecnico_id, :solucion, :recibido_en, :asignado_en,
                       :iniciado_en, :resuelto_en, :creado_por)""",
            {**{k: datos.get(k) for k in CAMPOS_EDITABLES}, "estado": estado,
             "tecnico_id": tecnico["id"] if tecnico else None, "solucion": solucion,
             "asignado_en": ahora if tecnico else None, "iniciado_en": ahora if solucion else None,
             "resuelto_en": ahora if solucion else None, "creado_por": usuario["id"]}).lastrowid
        texto = f"Ticket creado ({NOMBRE_ESTADO[estado].lower()})"
        if tecnico:
            texto += f", asignado a {tecnico['nombre']}"
        historial(conn, tid, "ESTADO", texto + ".", usuario["id"])
        if solucion:
            historial(conn, tid, "ESTADO", f"Resuelto en el momento. Solución: {solucion}", usuario["id"])
        auditar(conn, "tickets", tid, "CREAR", {**datos, "estado": estado, "solucion": solucion},
                usuario["id"], hs or None)
    return tid, []


def editar_ticket(conn, tid: int, datos: dict, version: int, usuario: dict,
                  confirmar_advertencias: bool = False) -> list:
    datos = {k: datos.get(k) for k in CAMPOS_EDITABLES}
    datos["solicitante"] = datos["solicitante"].strip()
    datos["asunto"] = datos["asunto"].strip()
    datos["recibido_en"] = a_utc(datos.get("recibido_en"))
    with escritura(conn):
        t = obtener(conn, tid)
        _controlar_version(t, version)
        exigir_no_anulado(t)
        exigir_permiso(t, usuario)
        hs = []
        if datos["recibido_en"] != t["recibido_en"]:
            hs = [h for h in _advertencias_alta(conn, datos, excluir_id=tid) if h.regla == "T7"]
        _confirmar(hs, confirmar_advertencias)
        cambios = {k: v for k, v in datos.items() if v != t[k]}
        if not cambios:
            return []
        sets = ", ".join(f"{k} = :{k}" for k in cambios)
        conn.execute(f"""UPDATE tickets SET {sets}, version = version + 1, modificado_por = :uid,
                         modificado_en = :ahora WHERE id = :id""",
                     {**cambios, "uid": usuario["id"], "ahora": db.ahora_utc(), "id": tid})
        if "prioridad" in cambios:
            historial(conn, tid, "EDICION", f"Prioridad: {t['prioridad'].lower()} → {cambios['prioridad'].lower()}.",
                      usuario["id"])
        otros = [k for k in cambios if k != "prioridad"]
        if otros:
            historial(conn, tid, "EDICION", "Datos editados: " + ", ".join(k.replace("_id", "").replace("_", " ")
                                                                            for k in otros) + ".", usuario["id"])
        auditar(conn, "tickets", tid, "MODIFICAR", {"antes": {k: t[k] for k in cambios}, "despues": cambios},
                usuario["id"], hs or None)
    return []


# ── Asignación ─────────────────────────────────────────────────────────

def tomar(conn, tid: int, usuario: dict) -> None:
    """El técnico se asigna un ticket disponible. T5: si otro lo tomó un instante antes, avisa."""
    with escritura(conn):
        t = obtener(conn, tid)
        exigir_no_anulado(t)
        ahora = db.ahora_utc()
        cur = conn.execute("""UPDATE tickets SET tecnico_id = ?, estado = 'ASIGNADO', asignado_en = ?,
                                     version = version + 1, modificado_por = ?, modificado_en = ?
                              WHERE id = ? AND tecnico_id IS NULL AND estado = 'NUEVO'""",
                           (usuario["id"], ahora, usuario["id"], ahora, tid))
        if cur.rowcount == 0:
            if t["tecnico_id"] == usuario["id"]:
                return
            bloquear("T5", f"El ticket #{tid} ya lo tomó {_nombre(conn, t['tecnico_id'])}.")
        historial(conn, tid, "ASIGNACION", f"{usuario['nombre']} tomó el ticket.", usuario["id"])
        auditar(conn, "tickets", tid, "ASIGNAR", {"tecnico_id": usuario["id"], "accion": "tomar"}, usuario["id"])


def asignar(conn, tid: int, tecnico_id: int | None, version: int, usuario: dict, texto: str | None = None) -> None:
    """Asigna, reasigna o libera (tecnico_id=None) un ticket.
    Al reasignar, el ticket vuelve a «Asignado»: el técnico nuevo todavía no empezó."""
    with escritura(conn):
        t = obtener(conn, tid)
        _controlar_version(t, version)
        exigir_no_anulado(t)
        exigir_permiso(t, usuario)
        if t["estado"] == "RESUELTO":
            bloquear("T2", "El ticket ya está resuelto. Para volver a trabajarlo, primero reábralo.")
        if tecnico_id == t["tecnico_id"]:
            return
        tecnico = _tecnico(conn, tecnico_id)
        ahora = db.ahora_utc()
        if tecnico:
            conn.execute("""UPDATE tickets SET tecnico_id = ?, estado = 'ASIGNADO', asignado_en = ?, motivo_espera = NULL,
                                   version = version + 1, modificado_por = ?, modificado_en = ? WHERE id = ?""",
                         (tecnico["id"], ahora, usuario["id"], ahora, tid))
            msg = (f"Reasignado de {_nombre(conn, t['tecnico_id'])} a {tecnico['nombre']}" if t["tecnico_id"]
                   else f"Asignado a {tecnico['nombre']}")
        else:
            conn.execute("""UPDATE tickets SET tecnico_id = NULL, estado = 'NUEVO', asignado_en = NULL, motivo_espera = NULL,
                                   version = version + 1, modificado_por = ?, modificado_en = ? WHERE id = ?""",
                         (usuario["id"], ahora, tid))
            msg = f"Liberado por {usuario['nombre']}: vuelve a la lista de disponibles"
        if (texto or "").strip():
            msg += f". Motivo: {texto.strip()}"
        historial(conn, tid, "ASIGNACION", msg + ".", usuario["id"])
        auditar(conn, "tickets", tid, "ASIGNAR", {"antes": t["tecnico_id"], "despues": tecnico_id, "motivo": texto},
                usuario["id"])


# ── Estados ────────────────────────────────────────────────────────────

def cambiar_estado(conn, tid: int, nuevo: str, texto: str | None, version: int, usuario: dict) -> None:
    texto = (texto or "").strip() or None
    with escritura(conn):
        t = obtener(conn, tid)
        _controlar_version(t, version)
        exigir_permiso(t, usuario)
        validar_transicion(t, nuevo, texto)
        ahora = db.ahora_utc()
        cambios: dict = {"estado": nuevo}
        if t["tecnico_id"] is None:                       # NUEVO: quien lo trabaja se lo asigna
            cambios.update(tecnico_id=usuario["id"], asignado_en=ahora)
        if nuevo == "EN_PROCESO" and not t["iniciado_en"]:
            cambios["iniciado_en"] = ahora
        cambios["motivo_espera"] = texto if nuevo == "EN_ESPERA" else None
        if nuevo == "RESUELTO":
            cambios.update(solucion=texto, resuelto_en=ahora)
            cambios.setdefault("iniciado_en", t["iniciado_en"] or ahora)
        if t["estado"] == "RESUELTO":                     # reabrir
            cambios.update(resuelto_en=None, solucion=None)
        sets = ", ".join(f"{k} = :{k}" for k in cambios)
        conn.execute(f"""UPDATE tickets SET {sets}, version = version + 1, modificado_por = :uid,
                         modificado_en = :ahora WHERE id = :id""",
                     {**cambios, "uid": usuario["id"], "ahora": ahora, "id": tid})
        if "tecnico_id" in cambios:
            historial(conn, tid, "ASIGNACION", f"{usuario['nombre']} tomó el ticket.", usuario["id"])
        if t["estado"] == "RESUELTO":
            msg = f"Reabierto. Motivo: {texto}"
        elif nuevo == "RESUELTO":
            msg = f"Resuelto. Solución: {texto}"
        elif nuevo == "EN_ESPERA":
            msg = f"En espera. Motivo: {texto}"
        else:
            msg = f"{NOMBRE_ESTADO[t['estado']]} → {NOMBRE_ESTADO[nuevo]}." + (f" {texto}" if texto else "")
        historial(conn, tid, "ESTADO", msg, usuario["id"])
        auditar(conn, "tickets", tid, "ESTADO", {"antes": t["estado"], "despues": nuevo, "texto": texto},
                usuario["id"])


def anular(conn, tid: int, motivo: str, version: int, usuario: dict) -> None:
    """No se borra: se anula con motivo (por ejemplo, un duplicado o un error de carga).
    Puede anular el jefe o quien creó el ticket."""
    with escritura(conn):
        t = obtener(conn, tid)
        _controlar_version(t, version)
        exigir_no_anulado(t)
        if usuario["rol"] != "JEFE" and t["creado_por"] != usuario["id"]:
            raise SinPermiso("Solo el jefe o quien cargó el ticket pueden anularlo.")
        ahora = db.ahora_utc()
        conn.execute("""UPDATE tickets SET estado = 'ANULADO', motivo_anulacion = ?, version = version + 1,
                               modificado_por = ?, modificado_en = ? WHERE id = ?""",
                     (motivo.strip(), usuario["id"], ahora, tid))
        historial(conn, tid, "ESTADO", f"Anulado. Motivo: {motivo.strip()}", usuario["id"])
        auditar(conn, "tickets", tid, "ANULAR", {"estado_anterior": t["estado"], "motivo": motivo}, usuario["id"])


# ── Notas y adjuntos ───────────────────────────────────────────────────

def agregar_nota(conn, tid: int, texto: str, usuario: dict) -> int:
    """Cualquier técnico puede dejar una nota en cualquier ticket (colaboración)."""
    with escritura(conn):
        t = obtener(conn, tid)
        exigir_no_anulado(t)
        cur = conn.execute("INSERT INTO notas (ticket_id, tipo, texto, usuario_id) VALUES (?, 'NOTA', ?, ?)",
                           (tid, texto.strip(), usuario["id"]))
        # Una nota también cuenta como movimiento del ticket (lo ven los demás al actualizar)
        conn.execute("UPDATE tickets SET modificado_por = ?, modificado_en = ? WHERE id = ?",
                     (usuario["id"], db.ahora_utc(), tid))
        auditar(conn, "notas", cur.lastrowid, "CREAR", {"ticket_id": tid, "texto": texto}, usuario["id"])
    return cur.lastrowid


def registrar_adjunto(conn, tid: int, nombre: str, archivo: str, tam: int, usuario: dict) -> int:
    with escritura(conn):
        t = obtener(conn, tid)
        exigir_no_anulado(t)
        aid = conn.execute("""INSERT INTO adjuntos (ticket_id, nombre, archivo, bytes, subido_por)
                              VALUES (?, ?, ?, ?, ?)""", (tid, nombre, archivo, tam, usuario["id"])).lastrowid
        historial(conn, tid, "ADJUNTO", f"Adjuntó el archivo «{nombre}».", usuario["id"])
        auditar(conn, "adjuntos", aid, "CREAR", {"ticket_id": tid, "nombre": nombre, "bytes": tam}, usuario["id"])
    return aid


__all__ = ["Bloqueado", "RequiereConfirmacion", "ConflictoVersion", "crear_ticket", "editar_ticket", "tomar",
           "asignar", "cambiar_estado", "anular", "agregar_nota", "registrar_adjunto", "auditar", "a_utc"]
