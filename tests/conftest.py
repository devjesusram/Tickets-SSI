"""Cada prueba usa una base SQLite nueva en una carpeta temporal."""
import pytest

from app import auth, config, db


@pytest.fixture(autouse=True)
def _base_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "tickets.db")
    monkeypatch.setattr(config, "ADJUNTOS_DIR", tmp_path / "adjuntos")
    monkeypatch.setattr(config, "RESPALDOS_DIR", tmp_path / "respaldos")
    monkeypatch.setattr(config, "REPORTES_DIR", tmp_path / "reportes")
    db.inicializar_esquema()


@pytest.fixture()
def conn():
    c = db.conectar()
    yield c
    c.close()


@pytest.fixture()
def usuarios(conn):
    """Un jefe y dos técnicos (contraseña «clave1234»). Devuelve dicts como los de la sesión."""
    us = {}
    with db.escritura(conn):
        for usuario, nombre, rol in (("jefe", "Jefe Ficticio", "JEFE"), ("ana", "Ana Ficticia", "TECNICO"),
                                     ("beto", "Beto Ficticio", "TECNICO")):
            uid = conn.execute("INSERT INTO usuarios (usuario, nombre, rol, hash_clave) VALUES (?, ?, ?, ?)",
                               (usuario, nombre, rol, auth.hash_clave("clave1234"))).lastrowid
            us[usuario] = {"id": uid, "usuario": usuario, "nombre": nombre, "rol": rol}
        us["area"] = conn.execute("INSERT INTO areas (nombre) VALUES ('Juzgado de Ejemplo')").lastrowid
    return us


def datos_ticket(**extra):
    return {"canal": "TELEFONO", "solicitante": "Pérez, Juan (ficticio)", "asunto": "No imprime",
            "prioridad": "MEDIA", "recibido_en": None, **extra}
