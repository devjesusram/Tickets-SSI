# Arquitectura del Sistema de Tickets

Este documento explica **cómo está armado** el sistema: dónde se guarda cada cosa, qué servicios de Windows usa
y cómo se evita que dos técnicos se pisen los cambios.

## 1. Vista general

```
   PCs de los 5 técnicos y del jefe                    PC servidor 172.31.60.254 (Windows, sin internet)
 ┌──────────┐ ┌──────────┐ ┌──────────┐            ┌───────────────────────────────────────────────────┐
 │ Técnico 1│ │ Técnico 2│ │   Jefe   │  http://   │ XAMPP ............ puertos 80 / 443  (no se toca) │
 │ navegador│ │ navegador│ │ navegador│ ─────────▶ │ C:\Pizarra ....... puerto 8090  (sistema hermano)  │
 └──────────┘ └──────────┘ └──────────┘  :8091     │ C:\Tickets ....... puerto 8091  ◀── este sistema   │
      (no se instala nada en las PCs)              │   · Programador de tareas: inicio, vigilancia,    │
                                                   │     respaldo 23:45 y resumen diario 13:30          │
                                                   │   · Firewall de Windows: regla para el 8091        │
                                                   └───────────────────────────────────────────────────┘
```

- **Una sola PC hace de servidor.** Los demás entran con el navegador (Chrome, Edge o Firefox). No hace falta
  instalar nada en las PCs de los técnicos ni compartir carpetas.
- **Sin internet y sin servidores de base de datos.** Todo viene dentro del ZIP: Python portátil, las librerías y
  el sistema. No se instala SQL Server, MySQL ni MongoDB.

## 2. Por qué un archivo SQLite y no JSON en una carpeta compartida

El pedido original sugería guardar los tickets en archivos JSON o CSV dentro de una carpeta compartida de red. Ese
esquema tiene un problema serio: si dos técnicos abren y guardan el mismo archivo desde dos PCs, **el último que
guarda borra lo del otro**, y Windows no ofrece un bloqueo confiable de archivos a través de la red (SMB) para
programas escritos en HTML/JS.

La solución elegida, igual que en la Pizarra:

| | JSON en carpeta compartida | Este sistema |
|---|---|---|
| Quién escribe los archivos | Cada PC, por la red | **Solo el servidor** (un único proceso) |
| Formato | Muchos archivos `.json` | **Un solo archivo** `C:\Tickets\datos\tickets.db` (SQLite, viene con Python) |
| Dos técnicos guardan a la vez | Se pisan los cambios | Se atienden **de a uno** (`BEGIN IMMEDIATE`) |
| Dos técnicos toman el mismo ticket | Quedan los dos | **Solo uno lo consigue**; el otro ve «ya lo tomó X» |
| Alguien editó mientras yo editaba | Se pierde un cambio | Aviso «el ticket cambió» (control por `version`) |
| Respaldo | Copiar la carpeta (puede salir a medias) | Copia segura en caliente, todas las noches |
| Programas necesarios | Ninguno | Ninguno (SQLite está dentro de Python) |

SQLite **no es un servidor**: es una librería que lee y escribe un archivo. No hay que instalarla, configurarla ni
mantenerla. Para copiar todos los datos alcanza con copiar ese archivo (mejor con `respaldo-ahora.bat`, que hace
una copia consistente aunque el sistema esté en uso).

### Cómo se evitan los conflictos (requisito de «bloqueo seguro»)

1. **Un solo escritor.** Los navegadores nunca tocan archivos: le piden los cambios al servidor por HTTP.
2. **Transacción exclusiva.** Cada guardado abre `BEGIN IMMEDIATE`: toma el permiso de escritura al empezar,
   valida con los datos actualizados y recién entonces guarda. Si en ese instante otro técnico está guardando,
   espera unos milisegundos su turno.
3. **«Tomar» atómico.** Tomar un ticket es una única orden
   `UPDATE … SET tecnico_id = yo WHERE id = N AND tecnico_id IS NULL`. Si dos técnicos hacen clic a la vez,
   la base solo deja que una de las dos se cumpla (regla T5). Hay una prueba automática que lo verifica con dos
   hilos simultáneos.
4. **Versión de cada ticket.** Cada ticket tiene un número `version` que sube con cada cambio. Si un técnico tiene
   abierta la ficha y otro la modifica, al guardar el primero recibe «otro usuario modificó el ticket» (regla T8)
   en lugar de pisar el cambio.
5. **Reglas también en la base.** La propia base rechaza estados incoherentes (por ejemplo, «En proceso» sin
   técnico o «Resuelto» sin solución), aunque alguien intentara saltarse la aplicación.

## 3. Carpetas y archivos en el servidor

```
C:\Tickets\
├── 1-crear-administrador.bat     crea el usuario JEFE
├── 2-probar-en-esta-ventana.bat  modo prueba (funciona con la ventana abierta)
├── 3-instalar-como-servicio.bat  tareas programadas + firewall (como administrador)
├── respaldo-ahora.bat · restaurar-respaldo.bat · resumen-ahora.bat
├── cargar-datos-de-ejemplo.bat · desinstalar-servicio.bat
├── configuracion.txt             puerto, tiempos objetivo, correo del resumen
├── LEAME.txt · INSTALACION-WINDOWS.md · FLUJO-DIARIO.md
├── app\                          el sistema (Python + HTML/CSS/JS)
├── python\                       Python 3.13 portátil con las librerías
├── windows\                      instalar-servicio.ps1 / desinstalar-servicio.ps1
├── datos\
│   ├── tickets.db                LA BASE (todos los tickets, notas, usuarios, auditoría)
│   ├── adjuntos\                 correos .eml, capturas de WhatsApp, PDF…
│   └── registros\tickets.log     registro de funcionamiento y errores
├── respaldos\                    tickets-db-AAAAMMDD-HHMM.db + tickets-adjuntos-AAAAMMDD-HHMM.zip
└── reportes\                     resumen-AAAA-MM-DD.html (uno por día hábil)
```

### Permisos de Windows recomendados

- `C:\Tickets` debe poder escribirse por la cuenta **SYSTEM** (lo es por defecto en `C:\`). Por eso no se instala
  en «Archivos de programa».
- **No comparta** `C:\Tickets\datos` en la red: nadie necesita entrar ahí, y así nadie puede borrar o copiar la
  base por error. Todo el acceso es por el navegador, con usuario y contraseña.
- Si quiere que el jefe vea los resúmenes diarios sin entrar al sistema, puede compartir **solo**
  `C:\Tickets\reportes` en modo **lectura** para su usuario de Windows.
- Copie `C:\Tickets\respaldos` a otro equipo o disco externo con frecuencia.

## 4. Servicios de Windows que se usan

| Servicio de Windows | Para qué | Nombre |
|---|---|---|
| Programador de tareas | Inicia el sistema al encender la PC (como SYSTEM, sin que nadie inicie sesión) y lo relanza cada 5 min si se cayó | «Tickets de Soporte» |
| Programador de tareas | Respaldo de la base y adjuntos, todas las noches a las **23:45** (la Pizarra usa 23:30) | «Tickets de Soporte - Respaldo» |
| Programador de tareas | Resumen diario en `reportes\` (y por correo si se configura), lunes a viernes a las 13:30 | «Tickets de Soporte - Resumen» |
| Firewall de Windows | Permite conexiones entrantes al puerto 8091 | «Tickets de Soporte» |

No se usa IIS ni XAMPP: el sistema trae su propio servidor web liviano (uvicorn) que escucha en el puerto 8091.

## 5. Convivencia con la Pizarra de Interinatos

| | Pizarra | Tickets |
|---|---|---|
| Carpeta | `C:\Pizarra` | `C:\Tickets` |
| Puerto | 8090 | **8091** |
| Tareas programadas | «Pizarra de Interinatos…» | «Tickets de Soporte…» |
| Respaldo nocturno | 23:30 | **23:45** |
| Cookie de sesión | `pizarra_sesion` | **`tickets_sesion`** |
| Base de datos | `datos\pizarra.db` | `datos\tickets.db` |

La cookie tiene otro nombre porque el navegador comparte las cookies por IP aunque cambie el puerto: con el mismo
nombre, entrar a un sistema cerraría la sesión del otro. Los usuarios de los dos sistemas son independientes.

## 6. Datos que se guardan

| Tabla | Contenido |
|---|---|
| `tickets` | Canal (teléfono interno, WhatsApp, correo, presencial) y referencia, solicitante, contacto, área, categoría, asunto, descripción, prioridad, estado, técnico, motivo de espera, solución, horas clave (recibido, asignado, iniciado, resuelto) |
| `notas` | Historial de cada ticket: notas de los técnicos y cada cambio de estado o de asignación |
| `adjuntos` | Archivos adjuntos (el archivo en sí queda en `datos\adjuntos`) |
| `areas`, `categorias` | Catálogos que mantiene el jefe |
| `usuarios`, `sesiones` | Usuarios propios (contraseñas cifradas con scrypt), sin Active Directory |
| `auditoria` | Quién hizo qué y cuándo, con los datos antes/después y las advertencias confirmadas |

**No se borra, se anula:** un ticket cargado por error o duplicado se anula con un motivo. Los usuarios, áreas y
categorías solo se pueden eliminar si nunca se usaron; si ya se usaron, se desactivan.

## 7. Estados y reglas

```
                 tomar / asignar               iniciar
   NUEVO ─────────────────────────▶ ASIGNADO ───────────▶ EN PROCESO ──┐
  (sin asignar) ◀─── liberar ──────    │  │                  │  ▲      │ resolver
                                       │  └── en espera ──▶ EN ESPERA  │ (con solución)
                                       │                     │         ▼
                                       └──────── resolver ───┴────▶ RESUELTO ── reabrir ──▶ EN PROCESO
   Cualquier estado ── anular (jefe o quien lo cargó, con motivo) ──▶ ANULADO
```

| Regla | Qué controla | Resultado |
|---|---|---|
| T1 | El técnico asignado existe y está activo | ⛔ Bloquea |
| T2 | Cambio de estado no permitido (ej.: resolver uno ya resuelto, reasignar uno resuelto) | ⛔ Bloquea |
| T3 | «En espera» exige motivo; «Resuelto» exige la solución; reabrir exige motivo | ⛔ Bloquea |
| T4 | Un ticket anulado no se modifica | ⛔ Bloquea |
| T5 | Dos técnicos toman el mismo ticket a la vez | ⛔ El segundo ve «ya lo tomó X» |
| T6 | Posible duplicado: tickets abiertos del mismo solicitante o del mismo área y categoría | ⚠ Pide confirmación |
| T7 | Fecha de recepción futura / con más de 30 días | ⛔ Bloquea / ⚠ Pide confirmación |
| T8 | Otro usuario modificó el ticket mientras se editaba | ⛔ Bloquea |
| T9 | Un técnico trabaja sus tickets y los disponibles; los de otro, solo el jefe (todos pueden dejar notas) | ⛔ Bloquea (403) |

**Tiempo objetivo por prioridad** (configurable): Urgente 4 h · Alta 24 h · Media 72 h · Baja 168 h, en horas
corridas desde que se recibió el pedido. Pasado ese tiempo el ticket aparece como **atrasado** (salvo si está
«En espera», porque depende de un tercero).

## 8. Componentes del código

| Archivo | Qué hace |
|---|---|
| `app/config.py` | Lee `configuracion.txt` y variables de entorno |
| `app/db.py` | Conexión SQLite, transacciones exclusivas, actualizaciones de la base con respaldo previo |
| `app/esquema.sql` | Tablas y restricciones |
| `app/reglas.py` | Estados, transiciones y reglas T1–T9 |
| `app/servicios.py` | Alta, edición, tomar, asignar, cambiar estado, anular, notas y adjuntos (con historial y auditoría) |
| `app/indicadores.py` | Listas, panel del jefe, tiempos y resumen diario |
| `app/main.py` | API web (FastAPI) y páginas |
| `app/auth.py` | Usuarios, contraseñas y sesiones (cookie `tickets_sesion`) |
| `app/cli.py` | `crear-admin`, `demo`, `respaldo`, `restaurar`, `resumen` |
| `app/servidor.py` | Arranque del servidor web y archivo de registro |
| `app/static/` | Interfaz: HTML, CSS y JavaScript sin dependencias externas, y el manual |
| `windows/` | Instaladores `.bat`/`.ps1` y configuración |
| `scripts/armar_paquete_windows.py` | Arma el ZIP con Python portátil |
| `tests/` | Pruebas automáticas (pytest) |
