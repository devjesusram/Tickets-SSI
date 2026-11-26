"""Configuración.

Orden de prioridad: variables de entorno > archivo 'configuracion.txt' en la carpeta
del sistema > valores por defecto. El archivo usa líneas CLAVE=VALOR.
"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(os.environ.get("TICKETS_BASE", Path(__file__).resolve().parent.parent))


def _leer_archivo(ruta: Path) -> None:
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


_leer_archivo(BASE_DIR / "configuracion.txt")


def _entero(nombre: str, defecto: int) -> int:
    try:
        return int(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


DATOS_DIR = Path(os.environ.get("DATOS_DIR", BASE_DIR / "datos"))
DB_PATH = Path(os.environ.get("DB_PATH", DATOS_DIR / "tickets.db"))
ADJUNTOS_DIR = Path(os.environ.get("ADJUNTOS_DIR", DATOS_DIR / "adjuntos"))
LOGS_DIR = Path(os.environ.get("LOGS_DIR", DATOS_DIR / "registros"))
RESPALDOS_DIR = Path(os.environ.get("RESPALDOS_DIR", BASE_DIR / "respaldos"))
REPORTES_DIR = Path(os.environ.get("REPORTES_DIR", BASE_DIR / "reportes"))

HOST = os.environ.get("HOST", "0.0.0.0")
PUERTO = _entero("PUERTO", 8091)
ZONA = ZoneInfo(os.environ.get("ZONA_HORARIA", "America/Asuncion"))
SESION_HORAS = _entero("SESION_HORAS", 12)
# Ponga "true" solo si sirve el sistema por HTTPS
COOKIE_SEGURA = os.environ.get("COOKIE_SEGURA", "false").lower() == "true"
NOMBRE_CIRCUNSCRIPCION = os.environ.get("NOMBRE_CIRCUNSCRIPCION", "Circunscripción Judicial de Cordillera")
NOMBRE_OFICINA = os.environ.get("NOMBRE_OFICINA", "Sección de Servicios Informáticos")
ADJUNTO_MAX_MB = _entero("ADJUNTO_MAX_MB", 15)
DIAS_RESPALDO = _entero("DIAS_RESPALDO", 30)

# Tiempo objetivo de resolución por prioridad (en horas corridas). Pasado ese tiempo,
# un ticket abierto aparece como «atrasado» en el panel del jefe y en las alertas.
OBJETIVO_HORAS = {
    "URGENTE": _entero("OBJETIVO_HORAS_URGENTE", 4),
    "ALTA": _entero("OBJETIVO_HORAS_ALTA", 24),
    "MEDIA": _entero("OBJETIVO_HORAS_MEDIA", 72),
    "BAJA": _entero("OBJETIVO_HORAS_BAJA", 168),
}
# Minutos que un ticket puede quedar sin asignar antes de aparecer en las alertas
ALERTA_SIN_ASIGNAR_MIN = _entero("ALERTA_SIN_ASIGNAR_MIN", 30)

# Envío opcional del resumen diario por correo (servidor de correo INTERNO de la institución).
# Si SMTP_SERVIDOR queda vacío, el resumen solo se guarda como archivo en la carpeta «reportes».
SMTP_SERVIDOR = os.environ.get("SMTP_SERVIDOR", "").strip()
SMTP_PUERTO = _entero("SMTP_PUERTO", 25)
SMTP_USUARIO = os.environ.get("SMTP_USUARIO", "").strip()
SMTP_CLAVE = os.environ.get("SMTP_CLAVE", "")
SMTP_TLS = os.environ.get("SMTP_TLS", "false").lower() == "true"
SMTP_REMITENTE = os.environ.get("SMTP_REMITENTE", "").strip()
RESUMEN_DESTINATARIOS = [d.strip() for d in os.environ.get("RESUMEN_DESTINATARIOS", "").split(",") if d.strip()]
