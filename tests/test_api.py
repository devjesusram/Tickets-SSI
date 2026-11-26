"""Pruebas de la API: sesión, permisos, códigos de respuesta, panel, CSV, adjuntos y respaldo."""
import pytest
from fastapi.testclient import TestClient

from app import auth, cli, config
from app.main import app


@pytest.fixture()
def cliente(usuarios):
    with TestClient(app) as c:
        yield c


def entrar(c, usuario="ana"):
    r = c.post("/api/login", json={"usuario": usuario, "clave": "clave1234"})
    assert r.status_code == 200
    assert auth.COOKIE == "tickets_sesion" and auth.COOKIE in r.cookies


def nuevo(c, **extra):
    body = {"canal": "WHATSAPP", "solicitante": "Gómez, Rosa (ficticia)", "asunto": "Sin internet",
            "prioridad": "ALTA", **extra}
    return c.post("/api/tickets", json=body)


def test_sin_sesion_401(cliente):
    assert cliente.get("/api/tablero").status_code == 401
    assert cliente.get("/").status_code == 200          # la página carga y el JS redirige al ingreso


def test_clave_incorrecta(cliente):
    assert cliente.post("/api/login", json={"usuario": "ana", "clave": "mal"}).status_code == 401


def test_tecnico_no_administra_ni_ve_panel(cliente):
    entrar(cliente, "ana")
    assert cliente.get("/api/panel").status_code == 403
    r = cliente.post("/api/usuarios", json={"usuario": "xx1", "nombre": "Xxx", "rol": "JEFE", "clave": "12345678"})
    assert r.status_code == 403


def test_flujo_por_api(cliente, usuarios):
    entrar(cliente, "ana")
    r = nuevo(cliente, area_id=usuarios["area"], recibido_en="")
    assert r.status_code == 201
    tid = r.json()["id"]
    assert nuevo(cliente, area_id=usuarios["area"]).status_code == 428          # posible duplicado
    assert cliente.post(f"/api/tickets/{tid}/tomar").status_code == 200
    t = cliente.get(f"/api/tickets/{tid}").json()
    assert t["estado"] == "ASIGNADO" and t["puede_trabajar"] and t["historial"]
    r = cliente.post(f"/api/tickets/{tid}/estado", json={"estado": "RESUELTO", "texto": "", "version": t["version"]})
    assert r.status_code == 409 and r.json()["hallazgos"][0]["regla"] == "T3"
    r = cliente.post(f"/api/tickets/{tid}/estado", json={"estado": "RESUELTO", "texto": "Se reinició el router",
                                                         "version": t["version"]})
    assert r.status_code == 200
    r = cliente.post(f"/api/tickets/{tid}/estado", json={"estado": "EN_PROCESO", "version": t["version"]})
    assert r.status_code == 409 and r.json()["tipo"] == "VERSION"
    tablero = cliente.get("/api/tablero").json()
    assert [x["estado"] for x in tablero["tickets"]] == ["RESUELTO"]


def test_otro_tecnico_recibe_403(cliente):
    entrar(cliente, "ana")
    tid = nuevo(cliente, tecnico_id=None).json()["id"]
    cliente.post(f"/api/tickets/{tid}/tomar")
    entrar(cliente, "beto")
    t = cliente.get(f"/api/tickets/{tid}").json()
    assert t["puede_trabajar"] is False
    r = cliente.post(f"/api/tickets/{tid}/estado", json={"estado": "EN_PROCESO", "version": t["version"]})
    assert r.status_code == 403
    assert cliente.post(f"/api/tickets/{tid}/notas", json={"texto": "Te ayudo"}).status_code == 201
    r = cliente.post(f"/api/tickets/{tid}/tomar")
    assert r.status_code == 409 and r.json()["hallazgos"][0]["regla"] == "T5"


def test_panel_busqueda_csv_y_resumen(cliente, usuarios):
    entrar(cliente, "jefe")
    tid = nuevo(cliente, tecnico_id=usuarios["ana"]["id"]).json()["id"]
    nuevo(cliente, solicitante="Otro Solicitante", solucion="Resuelto por teléfono")
    p = cliente.get("/api/panel").json()
    assert p["totales"]["abiertos"] == 1 and p["totales"]["resueltos_hoy"] == 1
    assert {u["nombre"] for u in p["por_tecnico"]} >= {"Ana Ficticia", "Beto Ficticio"}
    assert cliente.get("/api/tickets?q=internet").json()[0]["id"] in (tid, tid + 1)
    assert len(cliente.get(f"/api/tickets?q=%23{tid}").json()) == 1
    r = cliente.get("/api/tickets.csv")
    assert r.status_code == 200 and r.text.startswith("﻿Nº;") and "Gómez, Rosa" in r.text
    r = cliente.get("/api/reporte/diario")
    assert r.status_code == 200 and "Resumen diario" in r.text and "Claude" in r.text


def test_adjuntos(cliente):
    entrar(cliente, "ana")
    tid = nuevo(cliente).json()["id"]
    r = cliente.post(f"/api/tickets/{tid}/adjuntos", files={"archivo": ("correo.eml", b"From: x@y\r\n\r\nhola", "message/rfc822")})
    assert r.status_code == 201
    aid = r.json()["id"]
    assert cliente.get(f"/api/adjuntos/{aid}").content.endswith(b"hola")
    r = cliente.post(f"/api/tickets/{tid}/adjuntos", files={"archivo": ("virus.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400


def test_administracion(cliente, usuarios):
    entrar(cliente, "jefe")
    r = cliente.post("/api/usuarios", json={"usuario": "carla", "nombre": "Carla Ficticia", "rol": "TECNICO",
                                            "clave": "clave1234"})
    assert r.status_code == 201
    uid = r.json()["id"]
    assert cliente.delete(f"/api/usuarios/{uid}").status_code == 200        # nunca trabajó: se puede borrar
    assert cliente.delete(f"/api/usuarios/{usuarios['jefe']['id']}").status_code == 400
    aid = cliente.post("/api/areas", json={"nombre": "Mesa de Entrada", "interno": "100"}).json()["id"]
    nuevo(cliente, area_id=aid)
    assert cliente.delete(f"/api/areas/{aid}").status_code == 409           # tiene tickets
    cat = cliente.get("/api/catalogos").json()
    assert any(c["nombre"] == "Otro" for c in cat["categorias"])
    assert cliente.get("/api/auditoria").json()


def test_respaldo_y_resumen_por_linea_de_comandos(usuarios, conn):
    archivo = cli.respaldo()
    assert archivo.name.startswith("tickets-db-") and archivo.exists()
    r = cli.resumen()
    assert r.exists() and r.parent == config.REPORTES_DIR


def test_demo_carga_datos_ficticios(usuarios):
    cli.demo()
    with TestClient(app) as c:
        entrar(c, "jefe")
        assert len(c.get("/api/tablero").json()["tickets"]) > 5
