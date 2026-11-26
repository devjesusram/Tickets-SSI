"""Consultas de lectura: listas de tickets, panel del jefe y resumen diario."""
import html
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from . import config, db
from .reglas import ABIERTOS, NOMBRE_CANAL, NOMBRE_ESTADO, NOMBRE_PRIORIDAD, PRIORIDADES

SQL_TICKET = """
SELECT t.*, a.nombre AS area, a.localidad AS area_localidad, c.nombre AS categoria,
       ut.nombre AS tecnico, uc.nombre AS creado_por_nombre, um.nombre AS modificado_por_nombre,
       (SELECT count(*) FROM notas n WHERE n.ticket_id = t.id AND n.tipo = 'NOTA') AS n_notas,
       (SELECT count(*) FROM adjuntos j WHERE j.ticket_id = t.id) AS n_adjuntos
FROM tickets t
LEFT JOIN areas a ON a.id = t.area_id
LEFT JOIN categorias c ON c.id = t.categoria_id
LEFT JOIN usuarios ut ON ut.id = t.tecnico_id
LEFT JOIN usuarios uc ON uc.id = t.creado_por
LEFT JOIN usuarios um ON um.id = t.modificado_por
"""


def _dt(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")) if texto else None


def _horas(a: datetime, b: datetime) -> float:
    return round((b - a).total_seconds() / 3600, 1)


def enriquecer(t: dict, ahora: datetime) -> dict:
    """Agrega horas abierto, tiempo objetivo y si está atrasado.
    Un ticket «En espera» no se marca atrasado: depende de un tercero."""
    recibido = _dt(t["recibido_en"])
    fin = _dt(t["resuelto_en"]) if t["estado"] == "RESUELTO" else ahora
    objetivo = config.OBJETIVO_HORAS.get(t["prioridad"], 72)
    t["horas"] = _horas(recibido, fin)
    t["objetivo_horas"] = objetivo
    t["atrasado"] = t["estado"] in ("NUEVO", "ASIGNADO", "EN_PROCESO") and t["horas"] > objetivo
    t["fuera_de_plazo"] = t["estado"] == "RESUELTO" and t["horas"] > objetivo
    return t


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def inicio_dia_utc(d: date) -> str:
    """Medianoche local del día d, expresada en UTC (para comparar con la base)."""
    return datetime.combine(d, time(0), tzinfo=config.ZONA).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hoy_local() -> date:
    return datetime.now(config.ZONA).date()


def tablero(conn, dias_resueltos: int = 7) -> list[dict]:
    """Tickets abiertos + resueltos/anulados de los últimos días (lo que miran los técnicos)."""
    desde = inicio_dia_utc(hoy_local() - timedelta(days=dias_resueltos))
    filas = db.todos(conn, SQL_TICKET + """
        WHERE t.estado IN ('NUEVO','ASIGNADO','EN_PROCESO','EN_ESPERA')
           OR coalesce(t.resuelto_en, t.modificado_en, t.creado_en) >= ?
        ORDER BY t.id DESC""", (desde,))
    ahora = ahora_utc()
    return [enriquecer(f, ahora) for f in filas]


def buscar(conn, *, desde: date | None, hasta: date | None, estado: str | None, tecnico_id: int | None,
           canal: str | None, area_id: int | None, categoria_id: int | None, prioridad: str | None,
           texto: str | None, limite: int = 500) -> list[dict]:
    cond, params = [], []
    if desde:
        cond.append("t.recibido_en >= ?")
        params.append(inicio_dia_utc(desde))
    if hasta:
        cond.append("t.recibido_en < ?")
        params.append(inicio_dia_utc(hasta + timedelta(days=1)))
    for campo, valor in (("t.estado", estado), ("t.canal", canal), ("t.area_id", area_id),
                         ("t.categoria_id", categoria_id), ("t.prioridad", prioridad)):
        if valor:
            cond.append(f"{campo} = ?")
            params.append(valor)
    if tecnico_id == 0:
        cond.append("t.tecnico_id IS NULL")
    elif tecnico_id:
        cond.append("t.tecnico_id = ?")
        params.append(tecnico_id)
    if texto and texto.strip():
        q = texto.strip()
        if q.lstrip("#").isdigit():
            cond.append("t.id = ?")
            params.append(int(q.lstrip("#")))
        else:
            like = f"%{q.lower()}%"
            cond.append("""(lower(t.asunto) LIKE ? OR lower(coalesce(t.descripcion,'')) LIKE ?
                           OR lower(t.solicitante) LIKE ? OR lower(coalesce(t.solucion,'')) LIKE ?
                           OR lower(coalesce(t.canal_referencia,'')) LIKE ?
                           OR EXISTS (SELECT 1 FROM notas n WHERE n.ticket_id = t.id AND lower(n.texto) LIKE ?))""")
            params += [like] * 6
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    filas = db.todos(conn, SQL_TICKET + f" {where} ORDER BY t.id DESC LIMIT ?", (*params, limite))
    ahora = ahora_utc()
    return [enriquecer(f, ahora) for f in filas]


def _promedio(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 1) if xs else None


def panel(conn, dias: int = 30) -> dict:
    """Vista general del jefe: carga por técnico, estados, prioridades, tiempos y canales."""
    ahora = ahora_utc()
    hoy = hoy_local()
    ini_hoy = _dt(inicio_dia_utc(hoy))
    ini_semana = _dt(inicio_dia_utc(hoy - timedelta(days=hoy.weekday())))
    ini_periodo = inicio_dia_utc(hoy - timedelta(days=dias - 1))
    abiertos = [enriquecer(t, ahora) for t in db.todos(conn, SQL_TICKET + """
        WHERE t.estado IN ('NUEVO','ASIGNADO','EN_PROCESO','EN_ESPERA') ORDER BY t.recibido_en""")]
    periodo = [enriquecer(t, ahora) for t in db.todos(conn, SQL_TICKET + """
        WHERE t.estado <> 'ANULADO' AND (t.recibido_en >= ? OR t.resuelto_en >= ?)""", (ini_periodo, ini_periodo))]
    resueltos = [t for t in periodo if t["estado"] == "RESUELTO" and t["resuelto_en"] >= ini_periodo]
    tecnicos = db.todos(conn, "SELECT id, nombre, rol FROM usuarios WHERE activo = 1 ORDER BY nombre")

    por_tecnico = []
    for u in tecnicos:
        mios = [t for t in abiertos if t["tecnico_id"] == u["id"]]
        res = [t for t in resueltos if t["tecnico_id"] == u["id"]]
        fila = {
            "id": u["id"], "nombre": u["nombre"], "rol": u["rol"],
            "ASIGNADO": sum(t["estado"] == "ASIGNADO" for t in mios),
            "EN_PROCESO": sum(t["estado"] == "EN_PROCESO" for t in mios),
            "EN_ESPERA": sum(t["estado"] == "EN_ESPERA" for t in mios),
            "abiertos": len(mios),
            "urgentes": sum(t["prioridad"] in ("URGENTE", "ALTA") for t in mios),
            "atrasados": sum(t["atrasado"] for t in mios),
            "resueltos_hoy": sum(_dt(t["resuelto_en"]) >= ini_hoy for t in res),
            "resueltos_semana": sum(_dt(t["resuelto_en"]) >= ini_semana for t in res),
            "resueltos_periodo": len(res),
            "horas_promedio": _promedio([t["horas"] for t in res]),
            "en_plazo_pct": round(100 * sum(not t["fuera_de_plazo"] for t in res) / len(res)) if res else None,
            "mas_antiguo": max((t["horas"] for t in mios), default=None),
        }
        # El jefe aparece solo si tiene o tuvo tickets
        if u["rol"] == "TECNICO" or fila["abiertos"] or fila["resueltos_periodo"]:
            por_tecnico.append(fila)

    sin_asignar = [t for t in abiertos if t["tecnico_id"] is None]
    asignacion = [_horas(_dt(t["recibido_en"]), _dt(t["asignado_en"])) for t in periodo if t["asignado_en"]]
    return {
        "dias": dias,
        "generado": db.ahora_utc(),
        "objetivos": config.OBJETIVO_HORAS,
        "totales": {
            "abiertos": len(abiertos),
            "sin_asignar": len(sin_asignar),
            "atrasados": sum(t["atrasado"] for t in abiertos),
            "en_espera": sum(t["estado"] == "EN_ESPERA" for t in abiertos),
            "recibidos_hoy": sum(_dt(t["recibido_en"]) >= ini_hoy for t in periodo),
            "resueltos_hoy": sum(_dt(t["resuelto_en"]) >= ini_hoy for t in resueltos),
            "recibidos_periodo": sum(t["recibido_en"] >= ini_periodo for t in periodo),
            "resueltos_periodo": len(resueltos),
            "horas_resolucion": _promedio([t["horas"] for t in resueltos]),
            "horas_asignacion": _promedio(asignacion),
            "en_plazo_pct": (round(100 * sum(not t["fuera_de_plazo"] for t in resueltos) / len(resueltos))
                             if resueltos else None),
        },
        "por_tecnico": por_tecnico,
        "por_estado": {e: sum(t["estado"] == e for t in abiertos) for e in ABIERTOS},
        "por_prioridad": {p: sum(t["prioridad"] == p for t in abiertos) for p in PRIORIDADES},
        "por_canal": dict(Counter(t["canal"] for t in periodo if t["recibido_en"] >= ini_periodo)),
        "por_categoria": Counter(t["categoria"] or "(sin categoría)" for t in periodo
                                 if t["recibido_en"] >= ini_periodo).most_common(10),
        "por_area": Counter(t["area"] or "(sin área)" for t in periodo
                            if t["recibido_en"] >= ini_periodo).most_common(10),
        "atrasados": [t for t in abiertos if t["atrasado"]][:30],
        "sin_asignar": sin_asignar[:30],
    }


# ── Resumen diario (archivo HTML y, si se configura, correo) ───────────

def resumen_diario(conn, d: date) -> dict:
    ini, fin = inicio_dia_utc(d), inicio_dia_utc(d + timedelta(days=1))
    ahora = ahora_utc()
    recibidos = [enriquecer(t, ahora) for t in db.todos(conn, SQL_TICKET + """
        WHERE t.recibido_en >= ? AND t.recibido_en < ? AND t.estado <> 'ANULADO' ORDER BY t.id""", (ini, fin))]
    resueltos = [enriquecer(t, ahora) for t in db.todos(conn, SQL_TICKET + """
        WHERE t.estado = 'RESUELTO' AND t.resuelto_en >= ? AND t.resuelto_en < ? ORDER BY t.resuelto_en""",
                                                         (ini, fin))]
    abiertos = [enriquecer(t, ahora) for t in db.todos(conn, SQL_TICKET + """
        WHERE t.estado IN ('NUEVO','ASIGNADO','EN_PROCESO','EN_ESPERA') ORDER BY t.recibido_en""")]
    carga = defaultdict(lambda: {"abiertos": 0, "atrasados": 0, "resueltos": 0})
    for t in abiertos:
        k = t["tecnico"] or "(sin asignar)"
        carga[k]["abiertos"] += 1
        carga[k]["atrasados"] += t["atrasado"]
    for t in resueltos:
        carga[t["tecnico"] or "(sin asignar)"]["resueltos"] += 1
    return {"fecha": d, "recibidos": recibidos, "resueltos": resueltos, "abiertos": abiertos,
            "carga": dict(sorted(carga.items())),
            "por_canal": Counter(NOMBRE_CANAL[t["canal"]] for t in recibidos)}


def _hora_local(texto: str | None) -> str:
    return _dt(texto).astimezone(config.ZONA).strftime("%d/%m %H:%M") if texto else ""


def resumen_html(r: dict) -> str:
    e = html.escape
    d: date = r["fecha"]

    def tabla(filas, cols):
        if not filas:
            return "<p class='vacio'>Ninguno.</p>"
        cab = "".join(f"<th>{e(c)}</th>" for c, _ in cols)
        cuerpo = "".join("<tr>" + "".join(f"<td>{e(str(f(t)))}</td>" for _, f in cols) + "</tr>" for t in filas)
        return f"<table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>"

    col_ticket = [("Nº", lambda t: f"#{t['id']}"), ("Prioridad", lambda t: NOMBRE_PRIORIDAD[t["prioridad"]]),
                  ("Asunto", lambda t: t["asunto"]), ("Solicitante", lambda t: t["solicitante"]),
                  ("Área", lambda t: t["area"] or "")]
    atrasados = [t for t in r["abiertos"] if t["atrasado"]]
    sin_asignar = [t for t in r["abiertos"] if t["tecnico_id"] is None]
    carga = [{"t": k, **v} for k, v in r["carga"].items()]
    canales = " · ".join(f"{e(k)}: {v}" for k, v in r["por_canal"].items()) or "—"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Resumen del {d:%d/%m/%Y} · Tickets</title>
<style>
 body {{ font: 14px/1.45 system-ui, "Segoe UI", Roboto, sans-serif; color: #1d2330; background: #f4f5f7; margin: 0; }}
 header {{ background: #1f4e8c; color: #fff; padding: 14px 20px; }}
 header h1 {{ margin: 0; font-size: 18px; }} header p {{ margin: 2px 0 0; opacity: .85; }}
 main {{ max-width: 980px; margin: 0 auto; padding: 8px 20px 30px; }}
 section {{ background: #fff; border: 1px solid #d9dde5; border-radius: 8px; padding: 12px 16px; margin-top: 14px; }}
 h2 {{ font-size: 15px; margin: 0 0 8px; color: #1f4e8c; }}
 .cifras {{ display: flex; gap: 12px; flex-wrap: wrap; }}
 .cifra {{ background: #f4f5f7; border-radius: 8px; padding: 8px 14px; min-width: 120px; }}
 .cifra b {{ display: block; font-size: 22px; }} .rojo b {{ color: #c62828; }} .ambar b {{ color: #b26a00; }}
 table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
 th, td {{ text-align: left; padding: 5px 7px; border-bottom: 1px solid #d9dde5; vertical-align: top; }}
 th {{ background: #f4f5f7; }} .vacio {{ color: #5b6475; margin: 0; }}
 footer {{ text-align: center; font-size: 12px; color: #5b6475; margin-top: 20px; }}
</style></head><body>
<header><h1>🎫 Resumen diario de tickets · {d:%d/%m/%Y}</h1>
<p>{e(config.NOMBRE_OFICINA)} · {e(config.NOMBRE_CIRCUNSCRIPCION)}</p></header>
<main>
<section><div class="cifras">
 <div class="cifra"><b>{len(r['recibidos'])}</b>recibidos</div>
 <div class="cifra"><b>{len(r['resueltos'])}</b>resueltos</div>
 <div class="cifra"><b>{len(r['abiertos'])}</b>abiertos ahora</div>
 <div class="cifra ambar"><b>{len(sin_asignar)}</b>sin asignar</div>
 <div class="cifra rojo"><b>{len(atrasados)}</b>atrasados</div>
</div><p>Por canal: {canales}</p></section>
<section><h2>Carga por técnico</h2>{tabla(carga, [("Técnico", lambda x: x["t"]), ("Abiertos", lambda x: x["abiertos"]),
    ("Atrasados", lambda x: x["atrasados"]), ("Resueltos en el día", lambda x: x["resueltos"])])}</section>
<section><h2>Atrasados (superaron el tiempo objetivo)</h2>{tabla(atrasados, col_ticket + [
    ("Técnico", lambda t: t["tecnico"] or "(sin asignar)"), ("Horas", lambda t: t["horas"])])}</section>
<section><h2>Sin asignar</h2>{tabla(sin_asignar, col_ticket + [("Recibido", lambda t: _hora_local(t["recibido_en"]))])}</section>
<section><h2>Resueltos en el día</h2>{tabla(r['resueltos'], [("Nº", lambda t: f"#{t['id']}"),
    ("Asunto", lambda t: t["asunto"]), ("Técnico", lambda t: t["tecnico"] or ""),
    ("Solución", lambda t: t["solucion"] or ""), ("Horas", lambda t: t["horas"])])}</section>
<section><h2>Recibidos en el día</h2>{tabla(r['recibidos'], col_ticket + [
    ("Canal", lambda t: NOMBRE_CANAL[t["canal"]]), ("Estado", lambda t: NOMBRE_ESTADO[t["estado"]])])}</section>
<footer>Generado automáticamente por el Sistema de Tickets ·
 Desarrollado por la Sección de Servicios Informáticos · Circunscripción Judicial de Cordillera ·
 con la asistencia de Claude (IA de Anthropic)</footer>
</main></body></html>"""
