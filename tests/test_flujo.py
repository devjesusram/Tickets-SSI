"""Reglas del flujo de tickets (servicios): estados, asignación, permisos y concurrencia."""
import threading
from datetime import datetime, timedelta, timezone

import pytest

from app import db, servicios
from app.reglas import Bloqueado, ConflictoVersion, RequiereConfirmacion, SinPermiso
from tests.conftest import datos_ticket


def estado(conn, tid):
    return servicios.obtener(conn, tid)


def test_alta_sin_asignar_queda_nuevo(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), usuarios["ana"])
    t = estado(conn, tid)
    assert t["estado"] == "NUEVO" and t["tecnico_id"] is None
    assert db.uno(conn, "SELECT count(*) AS n FROM auditoria WHERE accion = 'CREAR'")["n"] == 1


def test_alta_asignada_y_resuelta_en_el_momento(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(tecnico_id=usuarios["beto"]["id"]), usuarios["ana"])
    assert estado(conn, tid)["estado"] == "ASIGNADO"
    tid2, _ = servicios.crear_ticket(conn, datos_ticket(solicitante="Otra Persona", solucion="Se reinició"),
                                     usuarios["ana"])
    t = estado(conn, tid2)
    assert t["estado"] == "RESUELTO" and t["tecnico_id"] == usuarios["ana"]["id"] and t["resuelto_en"]


def test_flujo_completo(conn, usuarios):
    ana = usuarios["ana"]
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), ana)
    servicios.tomar(conn, tid, ana)
    t = estado(conn, tid)
    assert t["estado"] == "ASIGNADO" and t["tecnico_id"] == ana["id"]
    servicios.cambiar_estado(conn, tid, "EN_PROCESO", None, t["version"], ana)
    t = estado(conn, tid)
    assert t["iniciado_en"]
    with pytest.raises(Bloqueado) as e:                       # T3: espera sin motivo
        servicios.cambiar_estado(conn, tid, "EN_ESPERA", "  ", t["version"], ana)
    assert e.value.hallazgos[0].regla == "T3"
    servicios.cambiar_estado(conn, tid, "EN_ESPERA", "Esperando repuesto", t["version"], ana)
    t = estado(conn, tid)
    assert t["motivo_espera"] == "Esperando repuesto"
    with pytest.raises(Bloqueado):                            # T3: resolver sin solución
        servicios.cambiar_estado(conn, tid, "RESUELTO", "", t["version"], ana)
    servicios.cambiar_estado(conn, tid, "RESUELTO", "Se cambió el cable", t["version"], ana)
    t = estado(conn, tid)
    assert t["estado"] == "RESUELTO" and t["solucion"] == "Se cambió el cable" and t["motivo_espera"] is None
    servicios.cambiar_estado(conn, tid, "EN_PROCESO", "Volvió a fallar", t["version"], ana)   # reabrir
    t = estado(conn, tid)
    assert t["estado"] == "EN_PROCESO" and t["resuelto_en"] is None and t["solucion"] is None
    tipos = [n["tipo"] for n in db.todos(conn, "SELECT tipo FROM notas WHERE ticket_id = ? ORDER BY id", (tid,))]
    assert tipos.count("ESTADO") >= 5 and "ASIGNACION" in tipos


def test_transicion_invalida(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(tecnico_id=usuarios["ana"]["id"]), usuarios["ana"])
    t = estado(conn, tid)
    with pytest.raises(Bloqueado) as e:
        servicios.cambiar_estado(conn, tid, "ASIGNADO", None, t["version"], usuarios["ana"])
    assert e.value.hallazgos[0].regla == "T2"


def test_iniciar_un_nuevo_lo_asigna_a_quien_lo_hace(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), usuarios["jefe"])
    servicios.cambiar_estado(conn, tid, "EN_PROCESO", None, 1, usuarios["beto"])
    t = estado(conn, tid)
    assert t["tecnico_id"] == usuarios["beto"]["id"] and t["estado"] == "EN_PROCESO"


def test_tecnico_no_toca_tickets_de_otro(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(tecnico_id=usuarios["ana"]["id"]), usuarios["ana"])
    t = estado(conn, tid)
    with pytest.raises(SinPermiso):
        servicios.cambiar_estado(conn, tid, "EN_PROCESO", None, t["version"], usuarios["beto"])
    with pytest.raises(SinPermiso):
        servicios.asignar(conn, tid, usuarios["beto"]["id"], t["version"], usuarios["beto"])
    # pero puede dejar una nota (colaboración)
    servicios.agregar_nota(conn, tid, "Yo vi ese problema la semana pasada", usuarios["beto"])
    # y el jefe sí puede reasignar
    servicios.asignar(conn, tid, usuarios["beto"]["id"], t["version"], usuarios["jefe"], "Está en esa sede")
    t = estado(conn, tid)
    assert t["tecnico_id"] == usuarios["beto"]["id"] and t["estado"] == "ASIGNADO"


def test_liberar_vuelve_a_disponibles(conn, usuarios):
    ana = usuarios["ana"]
    tid, _ = servicios.crear_ticket(conn, datos_ticket(tecnico_id=ana["id"]), ana)
    servicios.cambiar_estado(conn, tid, "EN_ESPERA", "No está el usuario", 1, ana)
    servicios.asignar(conn, tid, None, 2, ana)
    t = estado(conn, tid)
    assert t["estado"] == "NUEVO" and t["tecnico_id"] is None and t["motivo_espera"] is None


def test_tomar_dos_a_la_vez_solo_uno_gana(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), usuarios["jefe"])
    resultados = []

    def intentar(u):
        c = db.conectar()
        try:
            servicios.tomar(c, tid, u)
            resultados.append(("ok", u["usuario"]))
        except Bloqueado as e:
            resultados.append(("bloqueado", e.hallazgos[0].regla))
        finally:
            c.close()

    hilos = [threading.Thread(target=intentar, args=(usuarios[n],)) for n in ("ana", "beto")]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(r[0] for r in resultados) == ["bloqueado", "ok"]
    assert ("bloqueado", "T5") in resultados


def test_version_desactualizada(conn, usuarios):
    ana = usuarios["ana"]
    tid, _ = servicios.crear_ticket(conn, datos_ticket(tecnico_id=ana["id"]), ana)
    servicios.cambiar_estado(conn, tid, "EN_PROCESO", None, 1, ana)
    with pytest.raises(ConflictoVersion):
        servicios.cambiar_estado(conn, tid, "RESUELTO", "Listo", 1, ana)   # versión vieja


def test_posible_duplicado_pide_confirmar(conn, usuarios):
    servicios.crear_ticket(conn, datos_ticket(), usuarios["ana"])
    with pytest.raises(RequiereConfirmacion) as e:
        servicios.crear_ticket(conn, datos_ticket(solicitante="PÉREZ, JUAN (FICTICIO)".lower()), usuarios["ana"])
    assert e.value.hallazgos[0].regla == "T6"
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), usuarios["ana"], confirmar_advertencias=True)
    aud = db.uno(conn, "SELECT advertencias_confirmadas FROM auditoria WHERE registro_id = ? AND accion = 'CREAR'", (tid,))
    assert "T6" in aud["advertencias_confirmadas"]


def test_fecha_de_recepcion(conn, usuarios):
    futuro = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(Bloqueado):
        servicios.crear_ticket(conn, datos_ticket(recibido_en=futuro), usuarios["ana"])
    viejo = datetime.now(timezone.utc) - timedelta(days=45)
    with pytest.raises(RequiereConfirmacion):
        servicios.crear_ticket(conn, datos_ticket(recibido_en=viejo), usuarios["ana"])
    # sin zona horaria: se interpreta como hora local de Asunción
    tid, _ = servicios.crear_ticket(conn, datos_ticket(solicitante="X Y", recibido_en="2026-11-20T08:00"),
                                    usuarios["ana"])
    assert estado(conn, tid)["recibido_en"] == "2026-11-20T11:00:00Z"


def test_anular(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), usuarios["ana"])
    with pytest.raises(SinPermiso):                           # no lo cargó él ni es jefe
        servicios.anular(conn, tid, "Duplicado", 1, usuarios["beto"])
    servicios.anular(conn, tid, "Duplicado del #1", 1, usuarios["ana"])
    t = estado(conn, tid)
    assert t["estado"] == "ANULADO"
    with pytest.raises(Bloqueado) as e:
        servicios.tomar(conn, tid, usuarios["beto"])
    assert e.value.hallazgos[0].regla == "T4"


def test_la_base_impide_estados_incoherentes(conn, usuarios):
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), usuarios["ana"])
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        with db.escritura(conn):
            conn.execute("UPDATE tickets SET estado = 'EN_PROCESO' WHERE id = ?", (tid,))   # sin técnico
    with pytest.raises(sqlite3.IntegrityError):
        with db.escritura(conn):
            conn.execute("UPDATE tickets SET estado = 'RESUELTO', tecnico_id = ? WHERE id = ?",
                         (usuarios["ana"]["id"], tid))                                         # sin solución


def test_editar_registra_cambios(conn, usuarios):
    ana = usuarios["ana"]
    tid, _ = servicios.crear_ticket(conn, datos_ticket(), ana)
    t = estado(conn, tid)
    nuevos = {k: t[k] for k in servicios.CAMPOS_EDITABLES}
    nuevos.update(prioridad="URGENTE", asunto="No imprime nada")
    servicios.editar_ticket(conn, tid, nuevos, t["version"], ana)
    t2 = estado(conn, tid)
    assert t2["prioridad"] == "URGENTE" and t2["version"] == t["version"] + 1
    textos = [n["texto"] for n in db.todos(conn, "SELECT texto FROM notas WHERE ticket_id = ?", (tid,))]
    assert any("Prioridad" in x for x in textos)
