"""Comandos de administración.

  python -m app.cli crear-admin [usuario] ["Nombre completo"]   (usuario JEFE; pide los datos que falten)
  python -m app.cli demo                                        (carga datos de ejemplo ficticios)
  python -m app.cli respaldo [carpeta]                          (respaldo de base y adjuntos)
  python -m app.cli restaurar <archivo .db> [archivo de adjuntos .zip]
  python -m app.cli resumen [aaaa-mm-dd]                        (resumen diario en «reportes» y, si se
                                                                 configuró, por correo)
"""
import getpass
import shutil
import smtplib
import sqlite3
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from . import auth, config, db, indicadores, servicios


def crear_admin(usuario: str | None, nombre: str | None) -> None:
    usuario = (usuario or input("Usuario del jefe/administrador (ej.: jefe): ")).strip().lower()
    nombre = (nombre or input("Nombre y apellido: ")).strip()
    if len(usuario) < 3 or len(nombre) < 3:
        sys.exit("El usuario y el nombre deben tener al menos 3 caracteres.")
    clave = getpass.getpass("Contraseña (mínimo 8 caracteres, no se ve al escribir): ")
    if len(clave) < 8 or clave != getpass.getpass("Repita la contraseña: "):
        sys.exit("Las contraseñas no coinciden o son demasiado cortas.")
    with db.conexion() as conn, db.escritura(conn):
        conn.execute("""INSERT INTO usuarios (usuario, nombre, rol, hash_clave) VALUES (?, ?, 'JEFE', ?)
                        ON CONFLICT (usuario) DO UPDATE SET hash_clave = excluded.hash_clave,
                                                             rol = 'JEFE', activo = 1""",
                     (usuario, nombre, auth.hash_clave(clave)))
    print(f"Usuario jefe/administrador '{usuario}' listo.")


# ── Respaldo y restauración ────────────────────────────────────────────

def respaldo(destino: str | None = None) -> Path:
    """Copia segura de la base (aunque el sistema esté en uso) y de los adjuntos."""
    carpeta = Path(destino) if destino else config.RESPALDOS_DIR
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(config.ZONA).strftime("%Y%m%d-%H%M")
    archivo_db = carpeta / f"tickets-db-{marca}.db"
    origen = db.conectar()
    copia = sqlite3.connect(archivo_db)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()
    archivo_adj = carpeta / f"tickets-adjuntos-{marca}.zip"
    with zipfile.ZipFile(archivo_adj, "w", zipfile.ZIP_DEFLATED) as z:
        if config.ADJUNTOS_DIR.exists():
            for f in sorted(config.ADJUNTOS_DIR.iterdir()):
                if f.is_file():
                    z.write(f, f.name)
    # Borra solo respaldos del sistema de Tickets más viejos que DIAS_RESPALDO
    limite = time.time() - config.DIAS_RESPALDO * 86400
    for f in list(carpeta.glob("tickets-db-*.db")) + list(carpeta.glob("tickets-adjuntos-*.zip")):
        if f.stat().st_mtime < limite:
            f.unlink()
    print(f"Respaldo listo:\n  {archivo_db}\n  {archivo_adj}")
    return archivo_db


def restaurar(archivo_db: str, archivo_adj: str | None = None) -> None:
    """Reemplaza los datos actuales por los del respaldo. El servidor debe estar detenido."""
    origen_path = Path(archivo_db)
    if not origen_path.is_file():
        sys.exit(f"No existe el archivo {origen_path}")
    prueba = sqlite3.connect(origen_path)
    try:
        if prueba.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            sys.exit("El archivo de respaldo está dañado.")
    finally:
        prueba.close()
    # Antes de reemplazar, guarda una copia de lo que hay ahora (por si acaso)
    if config.DB_PATH.exists():
        print("Guardando una copia de los datos actuales antes de restaurar…")
        respaldo(str(config.RESPALDOS_DIR / "antes-de-restaurar"))
    origen = sqlite3.connect(origen_path)
    destino = db.conectar()
    try:
        origen.backup(destino)
    finally:
        destino.close()
        origen.close()
    if not archivo_adj:
        # Busca el archivo de adjuntos del mismo respaldo (misma fecha y hora)
        candidato = origen_path.with_name(origen_path.name.replace("tickets-db-", "tickets-adjuntos-")).with_suffix(".zip")
        if candidato.is_file():
            archivo_adj = str(candidato)
            print(f"Restaurando también los adjuntos de {candidato.name}")
    if archivo_adj:
        config.ADJUNTOS_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archivo_adj) as z:
            for nombre in z.namelist():
                limpio = Path(nombre).name           # evita rutas fuera de la carpeta
                if limpio:
                    with z.open(nombre) as src, open(config.ADJUNTOS_DIR / limpio, "wb") as dst:
                        shutil.copyfileobj(src, dst)
    print("Restauración terminada.")


# ── Resumen diario ─────────────────────────────────────────────────────

def resumen(fecha: str | None = None) -> Path:
    """Genera reportes/resumen-AAAA-MM-DD.html y, si hay servidor de correo configurado, lo envía."""
    d = date.fromisoformat(fecha) if fecha else indicadores.hoy_local()
    with db.conexion() as conn:
        r = indicadores.resumen_diario(conn, d)
    contenido = indicadores.resumen_html(r)
    config.REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    archivo = config.REPORTES_DIR / f"resumen-{d.isoformat()}.html"
    archivo.write_text(contenido, encoding="utf-8")
    print(f"Resumen guardado en {archivo}")
    if config.SMTP_SERVIDOR and config.RESUMEN_DESTINATARIOS:
        atrasados = sum(t["atrasado"] for t in r["abiertos"])
        msg = EmailMessage()
        msg["Subject"] = (f"Tickets {d:%d/%m/%Y}: {len(r['recibidos'])} recibidos, {len(r['resueltos'])} resueltos, "
                          f"{len(r['abiertos'])} abiertos ({atrasados} atrasados)")
        msg["From"] = config.SMTP_REMITENTE or config.SMTP_USUARIO or "tickets@localhost"
        msg["To"] = ", ".join(config.RESUMEN_DESTINATARIOS)
        msg.set_content("Abra este correo en un programa que muestre HTML para ver el resumen.")
        msg.add_alternative(contenido, subtype="html")
        try:
            with smtplib.SMTP(config.SMTP_SERVIDOR, config.SMTP_PUERTO, timeout=30) as s:
                if config.SMTP_TLS:
                    s.starttls()
                if config.SMTP_USUARIO:
                    s.login(config.SMTP_USUARIO, config.SMTP_CLAVE)
                s.send_message(msg)
            print(f"Resumen enviado a: {', '.join(config.RESUMEN_DESTINATARIOS)}")
        except (OSError, smtplib.SMTPException) as e:
            print(f"No se pudo enviar el correo ({e}). El resumen quedó guardado como archivo.")
    # Conserva los resúmenes del último año
    limite = time.time() - 366 * 86400
    for f in config.REPORTES_DIR.glob("resumen-*.html"):
        if f.stat().st_mtime < limite:
            f.unlink()
    return archivo


# ── Datos de ejemplo (todos FICTICIOS) ─────────────────────────────────

AREAS = [
    ("Juzgado Civil y Comercial 1º Turno", "Caacupé", "201"),
    ("Juzgado Civil y Comercial 2º Turno", "Caacupé", "202"),
    ("Juzgado Penal de Garantías 1º Turno", "Caacupé", "210"),
    ("Juzgado Penal de Garantías 2º Turno", "Caacupé", "211"),
    ("Juzgado Laboral", "Caacupé", "220"),
    ("Juzgado de la Niñez y la Adolescencia", "Caacupé", "230"),
    ("Tribunal de Sentencia", "Caacupé", "240"),
    ("Juzgado de Paz", "Caacupé", "250"),
    ("Juzgado de Paz", "Tobatí", None),
    ("Juzgado de Paz", "Piribebuy", None),
    ("Mesa de Entrada", "Caacupé", "100"),
    ("Administración", "Caacupé", "110"),
    ("Recursos Humanos", "Caacupé", "120"),
    ("Dirección de la Circunscripción", "Caacupé", "101"),
]
TECNICOS = [("tecnico1", "Benítez, Ana (ejemplo)"), ("tecnico2", "González, Carlos (ejemplo)"),
            ("tecnico3", "Ramírez, Lucía (ejemplo)"), ("tecnico4", "Ortiz, Diego (ejemplo)"),
            ("tecnico5", "Villalba, Sofía (ejemplo)")]
SOLICITANTES = ["Duarte, María", "Cáceres, José", "Acosta, Laura", "Figueredo, Raúl", "Insfrán, Elena",
                "Ayala, Hugo", "Ferreira, Patricia", "Núñez, Óscar", "Sanabria, Silvia", "Espínola, Jorge",
                "Báez, Mónica", "Galeano, Fernando", "Rojas, Andrés", "Giménez, Rosa", "Martínez, Miguel"]
PEDIDOS = [
    ("No enciende la computadora", "Computadora / hardware", "ALTA", "Se escucha un pitido y la pantalla queda negra."),
    ("La impresora atasca las hojas", "Impresora / escáner", "MEDIA", "Atasca en cada impresión doble faz."),
    ("Sin internet en la oficina", "Red / internet", "URGENTE", "Ninguna PC del despacho tiene conexión."),
    ("No puede ingresar al correo", "Correo electrónico", "ALTA", "Dice contraseña incorrecta."),
    ("El sistema de gestión no carga los expedientes", "Sistema de gestión judicial", "URGENTE", "Queda cargando."),
    ("Blanqueo de contraseña", "Usuario y contraseña", "MEDIA", "Olvidó la contraseña de Windows."),
    ("Instalar lector de PDF", "Programas / software", "BAJA", "Necesita firmar documentos en PDF."),
    ("El teléfono interno no tiene tono", "Telefonía", "MEDIA", "Desde ayer a la tarde."),
    ("Preparar videoconferencia para audiencia", "Audiencias / videoconferencia", "ALTA", "Audiencia a las 10:00."),
    ("Escáner no aparece en la PC", "Impresora / escáner", "MEDIA", "Después de una actualización de Windows."),
    ("PC muy lenta", "Computadora / hardware", "BAJA", "Tarda varios minutos en abrir el navegador."),
    ("Mover una PC a otro escritorio", "Otro", "BAJA", "Reubicación por cambio de oficina."),
    ("Configurar correo en el celular", "Correo electrónico", "BAJA", "Correo institucional en el teléfono."),
    ("Monitor parpadea", "Computadora / hardware", "MEDIA", "Parpadea cada pocos segundos."),
    ("No imprime en red", "Impresora / escáner", "ALTA", "La impresora compartida no responde."),
]
CANALES_DEMO = ["TELEFONO", "TELEFONO", "WHATSAPP", "WHATSAPP", "CORREO", "PRESENCIAL"]
SOLUCIONES = ["Se reinició el equipo y se reconfiguró la red.", "Se cambió el cable de red.",
              "Se reinstaló el controlador.", "Se blanqueó la contraseña y se verificó el ingreso.",
              "Se limpió el rodillo de la impresora.", "Se instaló el programa y se probó con el usuario."]


def demo() -> None:
    with db.conexion() as conn:
        if db.uno(conn, "SELECT count(*) AS n FROM tickets")["n"]:
            sys.exit("Ya hay tickets cargados: los datos de ejemplo solo se cargan en una base vacía.")
        jefe = db.uno(conn, "SELECT id, nombre, rol FROM usuarios WHERE rol = 'JEFE' ORDER BY id LIMIT 1")
        if not jefe:
            sys.exit("Primero cree el usuario jefe (1-crear-administrador.bat).")
        clave = auth.hash_clave("practica123")
        with db.escritura(conn):
            for nombre, loc, interno in AREAS:
                conn.execute("INSERT OR IGNORE INTO areas (nombre, localidad, interno) VALUES (?, ?, ?)",
                             (f"{nombre} - {loc}", loc, interno))
            for usuario, nombre in TECNICOS:
                conn.execute("""INSERT OR IGNORE INTO usuarios (usuario, nombre, rol, hash_clave)
                                VALUES (?, ?, 'TECNICO', ?)""", (usuario, nombre, clave))
        areas = [r["id"] for r in db.todos(conn, "SELECT id FROM areas ORDER BY id")]
        cats = {r["nombre"]: r["id"] for r in db.todos(conn, "SELECT id, nombre FROM categorias")}
        tecs = db.todos(conn, "SELECT id, nombre, rol FROM usuarios WHERE rol = 'TECNICO' ORDER BY usuario")
        ahora = datetime.now(timezone.utc).replace(microsecond=0)
        # Ticket k: recibido hace (horas) — más viejos primero; el estado depende de la antigüedad
        n = 42
        for k in range(n):
            asunto, cat, prio, desc = PEDIDOS[k % len(PEDIDOS)]
            horas_atras = (n - k) * 7.3 + (k % 3)
            recibido = ahora - timedelta(hours=horas_atras)
            canal = CANALES_DEMO[k % len(CANALES_DEMO)]
            sol = SOLICITANTES[(k * 4) % len(SOLICITANTES)]
            tec = tecs[k % len(tecs)]
            ref = {"TELEFONO": f"Interno {200 + k % 50}", "WHATSAPP": f"0981 000 {100 + k:03d} (ejemplo)",
                   "CORREO": f"Asunto: {asunto}", "PRESENCIAL": None}[canal]
            datos = {"canal": canal, "canal_referencia": ref, "solicitante": sol,
                     "contacto": f"Interno {200 + k % 50}", "area_id": areas[(k * 3) % len(areas)],
                     "categoria_id": cats[cat], "asunto": asunto, "descripcion": desc + " (dato de ejemplo)",
                     "prioridad": prio, "recibido_en": recibido}
            if k % 9 == 4:   # algunos se resolvieron en el momento, durante la llamada
                datos["solucion"] = "Se guió al usuario por teléfono. " + SOLUCIONES[k % len(SOLUCIONES)]
                datos["tecnico_id"] = tec["id"]
            elif k < n - 4:
                datos["tecnico_id"] = tec["id"]
            tid, _ = servicios.crear_ticket(conn, datos, jefe if k % 2 else tec, confirmar_advertencias=True)
            t = servicios.obtener(conn, tid)
            if k < n - 14 and not datos.get("solucion"):
                if k % 5 == 0:
                    servicios.cambiar_estado(conn, tid, "EN_PROCESO", None, t["version"], tec)
                    t = servicios.obtener(conn, tid)
                servicios.cambiar_estado(conn, tid, "RESUELTO", SOLUCIONES[k % len(SOLUCIONES)], t["version"], tec)
            elif n - 14 <= k < n - 4 and not datos.get("solucion"):
                if k % 3 == 0:
                    servicios.cambiar_estado(conn, tid, "EN_ESPERA", "Esperando repuesto de Administración.",
                                             t["version"], tec)
                elif k % 3 == 1:
                    servicios.cambiar_estado(conn, tid, "EN_PROCESO", "Revisando en el lugar.", t["version"], tec)
                if k % 4 == 0:
                    servicios.agregar_nota(conn, tid, "Se llamó al usuario para coordinar la visita.", tec)
            # Tiempos realistas: lo que pasó después de recibirlo, repartido en las horas siguientes
            t = servicios.obtener(conn, tid)
            dur = min(horas_atras * 0.8, 3 + (k % 7) * 6)
            fmt = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            with db.escritura(conn):
                conn.execute("""UPDATE tickets SET creado_en = ?, asignado_en = CASE WHEN asignado_en IS NULL THEN NULL ELSE ? END,
                                       iniciado_en = CASE WHEN iniciado_en IS NULL THEN NULL ELSE ? END,
                                       resuelto_en = CASE WHEN resuelto_en IS NULL THEN NULL ELSE ? END,
                                       modificado_en = CASE WHEN modificado_en IS NULL THEN NULL ELSE ? END
                                WHERE id = ?""",
                             (fmt(recibido + timedelta(minutes=3)), fmt(recibido + timedelta(minutes=20 + k % 40)),
                              fmt(recibido + timedelta(hours=dur / 3)),
                              fmt(recibido + timedelta(hours=0.3 if datos.get("solucion") else dur)),
                              fmt(recibido + timedelta(hours=dur)), tid))
                notas = db.todos(conn, "SELECT id FROM notas WHERE ticket_id = ? ORDER BY id", (tid,))
                for i, nota in enumerate(notas):
                    paso = timedelta(minutes=3) if i == 0 else timedelta(hours=dur * i / len(notas))
                    conn.execute("UPDATE notas SET creado_en = ? WHERE id = ?", (fmt(recibido + paso), nota["id"]))
    print("Datos de ejemplo cargados (son ficticios).")
    print("Se crearon 5 técnicos de ejemplo: tecnico1 … tecnico5, contraseña «practica123».")
    print("Antes de usar el sistema en serio, desactive o borre esos usuarios (o empiece con una base nueva).")


def main(argv: list[str]) -> None:
    if db.inicializar_esquema():
        print(f"Base de datos creada en {config.DB_PATH}")
    cmd = argv[0] if argv else ""
    if cmd == "crear-admin":
        crear_admin(argv[1] if len(argv) > 1 else None, argv[2] if len(argv) > 2 else None)
    elif cmd == "demo":
        demo()
    elif cmd == "respaldo":
        respaldo(argv[1] if len(argv) > 1 else None)
    elif cmd == "restaurar" and len(argv) >= 2:
        restaurar(argv[1], argv[2] if len(argv) > 2 else None)
    elif cmd == "resumen":
        resumen(argv[1] if len(argv) > 1 else None)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
