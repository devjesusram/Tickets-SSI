# Sistema de Tickets de tareas · Sección de Servicios Informáticos

Sistema web interno para registrar y seguir los **pedidos de soporte y tareas** que llegan a la Sección de Servicios
Informáticos de la **Circunscripción Judicial de Cordillera** por **teléfono interno, WhatsApp, correo** o en persona.
Pensado para un equipo de **5 técnicos y 1 jefe**.

**Desarrollado por la Sección de Servicios Informáticos** · Circunscripción Judicial de Cordillera · con la asistencia
de **Claude** (inteligencia artificial de Anthropic).

Es el sistema **hermano de la [Pizarra de Interinatos](https://github.com/devjesusram/pizarra-interinatos-csj)**: misma
base técnica, mismos colores y componentes, misma forma de instalarse. Los dos conviven en el mismo servidor.

**Liviano y sin internet:** corre en una PC con Windows 10/11, sin internet, sin Docker, sin instalar Python y **sin
servidores de base de datos**: los datos quedan en un solo archivo dentro de `C:\Tickets\datos`. Los técnicos entran
desde el navegador.

👉 **Instalación paso a paso:** [docs/INSTALACION-WINDOWS.md](docs/INSTALACION-WINDOWS.md)
👉 **Flujo diario (teléfono, WhatsApp, correo):** [docs/FLUJO-DIARIO.md](docs/FLUJO-DIARIO.md)
👉 **Arquitectura y manejo de conflictos:** [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)

## Qué hace

- **Registro rápido de tickets** (tecla **N**): canal de origen (📞 Teléfono interno, 💬 WhatsApp, ✉ Correo,
  🙋 Presencial) y su referencia, solicitante y área (se completan solos si ya pidió antes), asunto, descripción,
  categoría, prioridad y técnico asignado o «sin asignar».
  - **Correo:** arrastrando el `.eml` se completan solos el solicitante, el asunto, la descripción y la hora, y se
    adjunta el correo.
  - **WhatsApp:** se pega el texto y se adjuntan las fotos o audios.
  - **Resuelto en el momento:** una casilla para los pedidos que se solucionan durante la llamada.
- **Estados:** Nuevo / sin asignar → Asignado → En proceso → En espera → Resuelto (y reabrir). No se borra: se
  **anula** con motivo.
- **Vista del técnico:**
  - **📋 Mis tickets** en columnas por estado, con botones rápidos Iniciar / Resolver.
  - **📥 Disponibles**, con botón **✋ Tomar**.
  - Notas, adjuntos e historial completo de cada ticket.
- **Vista del jefe (📊 Panel):**
  - Carga por técnico: asignados, en proceso, en espera, atrasados, ticket más antiguo, resueltos hoy, en la semana
    y en el período, tiempo medio y porcentaje dentro del objetivo.
  - Abiertos por estado y prioridad; pedidos por canal, categoría y área.
  - Listas de atrasados y sin asignar.
  - Resumen del día imprimible y exportación a Excel (CSV).
- **Tiempos objetivo por prioridad** (Urgente 4 h, Alta 24 h, Media 72 h, Baja 168 h, configurables): lo que los
  supera se marca **⏰ Atrasado**.
- **Varios técnicos a la vez sin conflictos:**
  - Las escrituras se atienden de a una.
  - Si dos técnicos «toman» el mismo ticket, solo uno lo consigue.
  - Si dos editan lo mismo, el segundo recibe un aviso.
  - Ver [ARQUITECTURA.md](docs/ARQUITECTURA.md#cómo-se-evitan-los-conflictos-requisito-de-bloqueo-seguro).
- **Actualización automática:**
  - Cada 15 segundos cada pantalla busca cambios y se redibuja sola.
  - Aviso sonoro 🔔 y número en la pestaña cuando entra un ticket nuevo o le asignan uno.
- **Modo TV** para un monitor de la oficina.
- **Usuarios propios** (sin Active Directory) con roles TÉCNICO / JEFE y **auditoría** de todo.
- **Respaldo automático** todas las noches (23:45) y restauración con doble clic.
- **Resumen diario automático** en HTML (y por correo, si hay un servidor de correo interno).
- **Manual de usuario** incluido en `/manual`, sin internet.

### Reglas

| Regla | Qué controla | Resultado |
|---|---|---|
| T1 | El técnico asignado existe y está activo | ⛔ Bloquea |
| T2 | Cambio de estado no permitido | ⛔ Bloquea |
| T3 | «En espera» exige motivo; «Resuelto» exige solución; reabrir exige motivo | ⛔ Bloquea |
| T4 | Un ticket anulado no se modifica | ⛔ Bloquea |
| T5 | Dos técnicos toman el mismo ticket a la vez | ⛔ El segundo recibe «ya lo tomó…» |
| T6 | Posible duplicado (mismo solicitante, o mismo área y categoría, con tickets abiertos) | ⚠ Pide confirmación |
| T7 | Fecha de recepción futura / de hace más de 30 días | ⛔ Bloquea / ⚠ Pide confirmación |
| T8 | Otro usuario modificó el ticket mientras se editaba | ⛔ Bloquea |
| T9 | Un técnico trabaja sus tickets y los disponibles; los de otro, solo el jefe (todos pueden dejar notas) | ⛔ Bloquea |

## Instalación en el servidor (resumen)

| | Valor |
|---|---|
| Servidor | (Windows, sin internet, con XAMPP |
| Tareas programadas | «Tickets de Soporte», «… - Respaldo» (23:45), «… - Resumen» (13:30) |
| Cookie de sesión | `tickets_sesion` (la Pizarra usa `pizarra_sesion`) |

1. Descomprimir `Tickets-Windows-X.Y.Z.zip`.
2. `1-crear-administrador.bat` → usuario del jefe.
3. `3-instalar-como-servicio.bat` (como administrador).
4. Entrar como jefe → Administración → crear los 5 técnicos y las áreas.

Detalle completo en [docs/INSTALACION-WINDOWS.md](docs/INSTALACION-WINDOWS.md).

## Estructura

```
├── app/
│   ├── esquema.sql        # tablas SQLite (tickets, notas, adjuntos, áreas, categorías, usuarios, auditoría)
│   ├── reglas.py          # estados, transiciones y reglas T1–T9
│   ├── servicios.py       # alta, tomar, asignar, estados, anular, notas y adjuntos (con historial y auditoría)
│   ├── indicadores.py     # listas, panel del jefe, tiempos y resumen diario
│   ├── main.py            # API (FastAPI) y páginas
│   ├── servidor.py        # arranque del servidor web (python -m app.servidor)
│   ├── auth.py            # usuarios propios (contraseñas con scrypt) y sesiones
│   ├── cli.py             # crear-admin, demo, respaldo, restaurar, resumen
│   ├── config.py          # configuración (configuracion.txt / variables de entorno)
│   ├── db.py              # SQLite, transacciones exclusivas y actualizaciones de la base
│   └── static/            # interfaz (HTML + CSS + JavaScript, sin dependencias externas) y manual
├── windows/               # archivos .bat y .ps1 que van en el paquete de Windows
├── scripts/armar_paquete_windows.py   # arma dist/Tickets-Windows-<versión>.zip
├── tests/                 # pruebas automáticas
└── docs/                  # instalación, flujo diario y arquitectura
```

## Armar el paquete para Windows

En cualquier computadora con internet y Python 3.12 o superior (Linux, macOS o Windows):

```bash
python scripts/armar_paquete_windows.py
```

Genera `dist/Tickets-Windows-<versión>.zip` (unos 20 MB), con Python portátil y todas las librerías incluidas.

## Desarrollo

```bash
pip install -r requirements-dev.txt     # dependencias
python -m pytest -q                     # pruebas (cada una usa una base temporal)
python -m app.cli crear-admin jefe "Jefe de Prueba"
python -m app.cli demo                  # datos ficticios para probar
python -m app.servidor                  # http://localhost:8091  (API en /api/docs)
```

Los datos de ejemplo y las capturas del manual usan siempre **nombres ficticios**.
