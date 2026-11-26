# Instalación en Windows

El sistema de Tickets se instala en **una sola PC**, que hace de servidor (hoy `172.31.60.254`, la misma de la
Pizarra de Interinatos). Los 5 técnicos y el jefe entran desde el navegador de su propia PC, **sin instalar nada**.

**No hace falta:** internet en el servidor, Docker, WSL, IIS, instalar Python ni ninguna base de datos.
**Sí hace falta:** una PC con Windows 10 u 11 de 64 bits.

```
   PCs de los técnicos y del jefe                PC servidor 172.31.60.254
 ┌──────┐ ┌──────┐ ┌──────┐   http://…:8091   ┌───────────────────────────────┐
 │ PC 1 │ │ PC 2 │ │ Jefe │ ────────────────▶ │ C:\Tickets  (puerto 8091)     │
 └──────┘ └──────┘ └──────┘   (navegador)     │  · se inicia solo al encender │
                                              │  · datos en un solo archivo   │
                                              │  · respaldo cada noche 23:45  │
                                              │ C:\Pizarra (8090) · XAMPP (80)│
                                              └───────────────────────────────┘
```

---

## Parte A · Instalar en el servidor (lo hace una persona, una sola vez)

### Paso 1 · Conseguir el paquete (en una PC con internet)

Descargue el archivo **`Tickets-Windows-X.Y.Z.zip`** (unos 20 MB) desde la sección **Releases** del repositorio
en GitHub. Si no está publicado, ármelo usted (ver [«Armar el paquete»](#armar-el-paquete-para-windows) al final).

> **Antes de descomprimir:** clic derecho en el ZIP → **Propiedades** → si abajo aparece la casilla
> **«Desbloquear»**, márquela → **Aceptar**. Así Windows no muestra advertencias con cada archivo.

Lleve el ZIP a la PC servidor (pendrive o carpeta compartida).

### Paso 2 · Descomprimir en `C:\Tickets`

1. En la PC servidor, clic derecho en el ZIP → **Extraer todo…** → destino **`C:\`**.
2. Debe quedar la carpeta **`C:\Tickets`**, con `1-crear-administrador.bat`, `LEAME.txt` y la carpeta `python`.

No la ponga en «Archivos de programa» ni en el Escritorio: el sistema necesita escribir en su carpeta.
**No toque** `C:\Pizarra`: los dos sistemas son independientes.

### Paso 3 · Crear el usuario del jefe

Doble clic en **`1-crear-administrador.bat`** y complete:

- **Usuario**, por ejemplo `jefe`.
- **Nombre y apellido.**
- **Contraseña**, dos veces, de al menos 8 caracteres (al escribirla no se ve nada; es normal).

> Si aparece **«Windows protegió su PC»**: **Más información → Ejecutar de todas formas**.

### Paso 4 · Probar (opcional, recomendado)

Doble clic en **`2-probar-en-esta-ventana.bat`**. Se abre una ventana negra y el navegador en
`http://localhost:8091`. Entre con el usuario del jefe.

Para practicar con datos ficticios: cierre la ventana negra, ejecute **`cargar-datos-de-ejemplo.bat`** y vuelva a
abrir el modo prueba. Se crean 5 técnicos de ejemplo (`tecnico1` … `tecnico5`, contraseña `practica123`) y unos 40
tickets inventados.

**Cierre la ventana negra antes de seguir.**

### Paso 5 · Dejarlo funcionando siempre

Clic derecho en **`3-instalar-como-servicio.bat`** → **Ejecutar como administrador**. Esto:

1. Crea la tarea programada **«Tickets de Soporte»**: el sistema se inicia solo al encender la PC, aunque nadie
   inicie sesión, y si se detiene vuelve a arrancar en menos de 5 minutos.
2. Programa el **respaldo** todas las noches a las **23:45** (la Pizarra lo hace a las 23:30).
3. Programa el **resumen diario** de lunes a viernes a las 13:30, en `C:\Tickets\reportes`.
4. Abre el **puerto 8091** en el Firewall de Windows.
5. Verifica que el puerto no lo use otro programa (XAMPP usa 80/443 y la Pizarra 8090, así que no chocan).

Si la ventana dice **«LISTO: el sistema de Tickets está funcionando»**, ya está.

### Paso 6 · Cargar usuarios y áreas

Entre como jefe en `http://172.31.60.254:8091` → **👤 → ⚙ Administración**:

1. **Usuarios → + Usuario**: cree uno por técnico, con rol **Técnico**. Use usuarios simples, sin espacios ni
   acentos (por ejemplo `aperez`). Dele a cada uno una contraseña inicial y pídale que la cambie en
   **👤 → 🔑 Cambiar contraseña**.
   - **Técnico:** carga tickets, toma los disponibles, trabaja los suyos y puede pasarlos a un compañero.
   - **Jefe:** además asigna y reasigna cualquier ticket, anula, ve el **📊 Panel del jefe** y administra.
2. **Áreas**: cargue los juzgados y oficinas que piden soporte, con su localidad y su interno.
3. **Categorías**: ya vienen 10 cargadas (computadora, impresora, red, correo, sistema de gestión…). Ajústelas si
   quiere.

Si practicó con los datos de ejemplo, antes de empezar en serio vea [«Empezar con los datos reales»](#si-cargó-datos-de-ejemplo-y-quiere-empezar-con-los-datos-reales).

---

## Parte B · En la PC de cada técnico y del jefe (2 minutos cada una)

No se instala nada. En cada PC:

1. Abra **Chrome, Edge o Firefox** y entre a **`http://172.31.60.254:8091`**.
2. Ingrese con su usuario y contraseña.
3. Cree un **acceso directo**: achique la ventana del navegador y **arrastre el ícono que está a la izquierda de la
   dirección** (el candado o la «i») hasta el escritorio. Queda un ícono que abre el sistema con doble clic.
   (En Chrome y Edge también se puede usar el menú del navegador → «Crear acceso directo» / «Instalar este sitio
   como aplicación»; el nombre exacto cambia según la versión.)
4. Para recibir avisos, **deje la pestaña abierta** durante la jornada (puede estar minimizada). Cuando entra un
   ticket nuevo o le asignan uno, suena un aviso y el título de la pestaña muestra un número, por ejemplo
   «(2) Tickets de Soporte». El botón 🔔 de la barra activa o silencia el sonido.
5. (Opcional, en la PC de la oficina con monitor grande) botón **Modo TV**: muestra los tickets sin asignar y la
   carga de cada técnico, y se actualiza solo.

> Si el navegador usa un proxy institucional y no abre la dirección, agregue `172.31.60.254` a las excepciones del
> proxy (en Windows: Configuración → Red e Internet → Proxy → «No usar el proxy para…»).

---

## Respaldos

- **Automático:** todas las noches a las 23:45, en `C:\Tickets\respaldos`. Se guardan los últimos 30 días.
- **Manual:** doble clic en **`respaldo-ahora.bat`** (se puede con el sistema en uso).
- Cada respaldo son dos archivos: `tickets-db-AAAAMMDD-HHMM.db` (los datos) y `tickets-adjuntos-AAAAMMDD-HHMM.zip`.

⚠ **Copie la carpeta `respaldos` a otro equipo o a un disco externo con frecuencia.** Si la PC servidor se daña,
los respaldos que están en ella se pierden con ella.

### Restaurar un respaldo

1. Clic derecho en **`restaurar-respaldo.bat`** → **Ejecutar como administrador**.
2. Arrastre a la ventana el archivo `tickets-db-….db` que quiere recuperar y presione Enter.
3. Escriba **SI** para confirmar.

Los adjuntos del mismo respaldo se restauran solos. Antes se guarda una copia de los datos actuales en
`respaldos\antes-de-restaurar`, por si se equivoca de archivo.

## Resumen diario y correo (opcional)

Cada día hábil a las 13:30 se guarda `C:\Tickets\reportes\resumen-AAAA-MM-DD.html` con lo recibido, lo resuelto,
la carga de cada técnico, los atrasados y los sin asignar. Se abre con doble clic. El jefe también lo ve en
**📊 Panel del jefe → 🖨 Resumen del día**.

Para que además llegue **por correo**, complete en `configuracion.txt` los datos del servidor de correo **interno**
de la institución (`SMTP_SERVIDOR`, `SMTP_PUERTO`, `RESUMEN_DESTINATARIOS`…) y vuelva a ejecutar
`3-instalar-como-servicio.bat`. Pruébelo con **`resumen-ahora.bat`**. Si el servidor no tiene salida a ningún
servidor de correo, deje esos campos vacíos: el resumen queda igual en la carpeta `reportes`.

Para cambiar la hora, modifique `HORA_RESUMEN` en `configuracion.txt` y vuelva a ejecutar el instalador.

## Si cargó datos de ejemplo y quiere empezar con los datos reales

1. Clic derecho en **`desinstalar-servicio.bat`** → **Ejecutar como administrador** (o cierre la ventana del modo
   prueba).
2. **Borre la carpeta `C:\Tickets\datos`.** Se pierden todos los datos de ejemplo.
3. Repita los pasos 3, 5 y 6.

## Actualizar a una versión nueva

1. Haga un respaldo con `respaldo-ahora.bat`.
2. Ejecute `desinstalar-servicio.bat` como administrador.
3. Descomprima el ZIP nuevo en una carpeta aparte y copie a `C:\Tickets` **solo** las carpetas `app`, `python` y
   `windows` y los archivos `.bat`, reemplazando los anteriores. **No toque** `datos`, `respaldos`, `reportes` ni
   `configuracion.txt`.
4. Ejecute `3-instalar-como-servicio.bat` como administrador.

Si la versión nueva cambia la base de datos, se actualiza sola al iniciar, y antes se guarda una copia en
`respaldos\antes-de-actualizar`.

## Mudar el sistema a otra PC

1. En la PC vieja: `respaldo-ahora.bat`.
2. En la PC nueva: pasos 2 y 5 de esta guía.
3. Restaure el respaldo en la PC nueva y avise a los técnicos la nueva dirección.

## Problemas frecuentes

| Problema | Solución |
|---|---|
| Desde otra PC no abre `http://172.31.60.254:8091` | Verifique en el servidor que funcione `http://localhost:8091`. Si allí funciona, revise el firewall (vuelva a ejecutar `3-instalar-como-servicio.bat`) o el proxy del navegador. |
| El instalador dice que el puerto está ocupado | Cierre la ventana de `2-probar-en-esta-ventana.bat`. Si es otro programa, cambie `PUERTO` en `configuracion.txt` (ej. `8092`) y vuelva a instalar. |
| Entrar a la Pizarra me cierra la sesión de Tickets | No debería pasar: usan cookies distintas (`pizarra_sesion` / `tickets_sesion`). Si pasa, borre las cookies de `172.31.60.254` en el navegador. |
| Un técnico olvidó la contraseña | El jefe: **Administración → Usuarios → Editar → Nueva contraseña**. |
| El jefe olvidó la contraseña | En el servidor, `1-crear-administrador.bat` con el mismo usuario: le pone una nueva. |
| No suena el aviso | Haga clic una vez en la página (los navegadores no permiten sonidos hasta la primera interacción) y verifique que el botón muestre 🔔 y no 🔕. |
| Ver errores | `C:\Tickets\datos\registros\tickets.log`. |

---

## Armar el paquete para Windows

En cualquier computadora **con internet** y Python 3.12 o superior (Windows, Linux o macOS), dentro de la carpeta
del repositorio:

```bash
python scripts/armar_paquete_windows.py
```

Genera `dist/Tickets-Windows-<versión>.zip` con Python 3.13 portátil y todas las librerías para Windows de 64 bits.
