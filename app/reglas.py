"""Reglas del flujo de tickets.

Hay dos niveles de error, igual que en la Pizarra:
  · BLOQUEO (HTTP 409): no se puede guardar.
  · ADVERTENCIA (HTTP 428): se muestra y se pide confirmar; si el usuario confirma,
    el aviso queda registrado en la auditoría.

Reglas
  T1  El técnico asignado debe existir y estar activo.
  T2  Cambio de estado no permitido desde el estado actual.
  T3  «En espera» exige el motivo; «Resuelto» exige la solución; reabrir exige el motivo.
  T4  Un ticket anulado ya no se modifica.
  T5  Dos técnicos toman el mismo ticket a la vez: solo uno lo consigue.
  T6  Posible duplicado: hay tickets abiertos del mismo solicitante o del mismo área y categoría.
  T7  La fecha de recepción no puede ser futura; si tiene más de 30 días, se pide confirmar.
  T8  Otro usuario modificó el ticket mientras se editaba (control por «version»).
  T9  Un técnico solo trabaja sus tickets y los disponibles; los de otro técnico, solo el jefe.
"""
from dataclasses import asdict, dataclass

ESTADOS = ("NUEVO", "ASIGNADO", "EN_PROCESO", "EN_ESPERA", "RESUELTO", "ANULADO")
ABIERTOS = ("NUEVO", "ASIGNADO", "EN_PROCESO", "EN_ESPERA")
PRIORIDADES = ("URGENTE", "ALTA", "MEDIA", "BAJA")
CANALES = ("TELEFONO", "WHATSAPP", "CORREO", "PRESENCIAL")

NOMBRE_ESTADO = {"NUEVO": "Nuevo / sin asignar", "ASIGNADO": "Asignado", "EN_PROCESO": "En proceso",
                 "EN_ESPERA": "En espera", "RESUELTO": "Resuelto", "ANULADO": "Anulado"}
NOMBRE_CANAL = {"TELEFONO": "Teléfono interno", "WHATSAPP": "WhatsApp", "CORREO": "Correo",
                "PRESENCIAL": "Presencial"}
NOMBRE_PRIORIDAD = {"URGENTE": "Urgente", "ALTA": "Alta", "MEDIA": "Media", "BAJA": "Baja"}

# Estados a los que se puede pasar desde cada estado con «cambiar estado».
# (Asignar, tomar, liberar y anular son acciones aparte.)
TRANSICIONES = {
    "NUEVO": {"EN_PROCESO", "EN_ESPERA", "RESUELTO"},      # quien lo hace se lo asigna
    "ASIGNADO": {"EN_PROCESO", "EN_ESPERA", "RESUELTO"},
    "EN_PROCESO": {"EN_ESPERA", "RESUELTO"},
    "EN_ESPERA": {"EN_PROCESO", "RESUELTO"},
    "RESUELTO": {"EN_PROCESO"},                            # reabrir
    "ANULADO": set(),
}


@dataclass
class Hallazgo:
    nivel: str      # BLOQUEO | ADVERTENCIA | INFO
    regla: str
    mensaje: str

    def a_dict(self) -> dict:
        return asdict(self)


class Bloqueado(Exception):
    def __init__(self, hallazgos: list[Hallazgo]):
        super().__init__("; ".join(h.mensaje for h in hallazgos))
        self.hallazgos = hallazgos


class RequiereConfirmacion(Exception):
    def __init__(self, hallazgos: list[Hallazgo]):
        super().__init__("; ".join(h.mensaje for h in hallazgos))
        self.hallazgos = hallazgos


class ConflictoVersion(Exception):
    pass


class SinPermiso(Exception):
    pass


def bloquear(regla: str, mensaje: str):
    raise Bloqueado([Hallazgo("BLOQUEO", regla, mensaje)])


def puede_trabajar(ticket: dict, usuario: dict) -> bool:
    """T9: el jefe trabaja cualquier ticket; un técnico, los suyos y los disponibles."""
    return usuario["rol"] == "JEFE" or ticket["tecnico_id"] in (None, usuario["id"])


def exigir_permiso(ticket: dict, usuario: dict) -> None:
    if not puede_trabajar(ticket, usuario):
        raise SinPermiso(f"El ticket #{ticket['id']} está asignado a otro técnico. "
                         "Solo el jefe o el técnico asignado pueden modificarlo.")


def exigir_no_anulado(ticket: dict) -> None:
    if ticket["estado"] == "ANULADO":
        bloquear("T4", f"El ticket #{ticket['id']} está anulado y ya no se puede modificar.")


def validar_transicion(ticket: dict, nuevo: str, texto: str | None) -> None:
    actual = ticket["estado"]
    exigir_no_anulado(ticket)
    if nuevo not in TRANSICIONES.get(actual, set()):
        bloquear("T2", f"No se puede pasar de «{NOMBRE_ESTADO[actual]}» a «{NOMBRE_ESTADO.get(nuevo, nuevo)}».")
    vacio = not (texto or "").strip()
    if nuevo == "EN_ESPERA" and vacio:
        bloquear("T3", "Indique el motivo de la espera (por ejemplo: «esperando repuesto» o «el usuario no está»).")
    if nuevo == "RESUELTO" and vacio:
        bloquear("T3", "Describa la solución aplicada: queda como nota de resolución del ticket.")
    if actual == "RESUELTO" and vacio:
        bloquear("T3", "Indique por qué se reabre el ticket.")
