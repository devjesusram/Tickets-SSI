# Flujo diario recomendado

Cómo registrar en el sistema todo lo que llega por **teléfono interno, WhatsApp, correo** o en persona, y cómo
organizarse los 5 técnicos y el jefe durante la jornada.

> **Regla de oro: todo pedido es un ticket.** Aunque se resuelva en dos minutos por teléfono, se carga (hay una
> casilla «Ya se resolvió en el momento» para eso). Así el jefe ve la carga real y queda historia de cada problema.

## 1. Roles en el día a día

| Quién | Qué hace |
|---|---|
| **Quien atiende** (cualquier técnico, o uno de turno) | Carga cada pedido apenas llega. Si sabe a quién corresponde, lo asigna; si no, lo deja «Sin asignar». |
| **Técnicos** | Miran **📋 Mis tickets** y **📥 Disponibles**. Toman pedidos, los trabajan, anotan lo que hacen y los resuelven con la solución. |
| **Jefe** | Revisa el **📊 Panel del jefe**: sin asignar, atrasados, carga por técnico. Reasigna cuando alguien está sobrecargado o ausente. |

Sugerencia: definir un **técnico de turno** por día (rotativo) que atienda el teléfono interno y el WhatsApp de la
oficina y cargue los tickets. Los demás trabajan sin interrupciones y miran «Disponibles».

## 2. Cómo cargar según el canal

En todos los casos: botón **+ Nuevo ticket** (o la tecla **N**). El formulario recuerda el último canal usado y, al
escribir un solicitante que ya pidió antes, completa solo su contacto y su área.

### 📞 Teléfono interno

1. **Mientras habla**, abra **+ Nuevo ticket** con canal **Teléfono interno**.
2. Complete: **Solicitante** (Apellido, Nombre), **Contacto** (su interno), **Área**, **Asunto** corto y lo que
   cuenta en **Descripción**. En **Referencia**, el interno desde el que llamó.
3. Antes de cortar, **confírmele la prioridad** y dígale el **número de ticket** que aparece al guardar
   («Su pedido es el número 128»). Así, si vuelve a llamar, se busca por número.
4. Si lo resolvió durante la llamada (blanqueo de contraseña, guiarlo para reconectar la impresora…), marque
   **«Ya se resolvió en el momento»** y escriba la solución: el ticket queda resuelto y a su nombre.

### 💬 WhatsApp

Para no mezclar el WhatsApp personal, conviene un **celular o número de la oficina** con **WhatsApp Web** abierto en
la PC del técnico de turno (o en la PC de la oficina).

1. Llega un mensaje → **+ Nuevo ticket** con canal **WhatsApp**.
2. En **Referencia**, el número o nombre del contacto. En **Descripción**, copie y pegue el texto del mensaje
   (Ctrl+C / Ctrl+V desde WhatsApp Web).
3. Si mandó una **foto** del error o un **audio**: descárguelo desde WhatsApp Web y **arrástrelo** a la zona de
   adjuntos del formulario (o adjúntelo luego desde la ficha del ticket).
4. Respóndale por WhatsApp con el número de ticket: *«Recibido, quedó registrado con el número 129. Le avisamos
   cuando esté resuelto.»*
5. Al resolver, avísele por el mismo WhatsApp.

> Respuesta rápida sugerida (WhatsApp Business permite guardarla como «respuesta rápida»):
> *«Hola, recibimos su pedido y quedó registrado con el número ___. Prioridad: ___. Le avisamos por este medio.»*

### ✉ Correo electrónico

1. En el programa de correo (Outlook, Thunderbird, webmail), **guarde el correo como archivo `.eml`** o
   **arrástrelo** desde Outlook/Thunderbird al escritorio. (En Outlook: Archivo → Guardar como → formato `.msg`
   también se puede adjuntar, pero solo el `.eml` completa los campos solo.)
2. En **+ Nuevo ticket**, **arrastre el `.eml` a la zona punteada**: el sistema completa el canal (Correo), el
   solicitante, su correo como contacto, el asunto, la descripción y la hora en que llegó, y adjunta el correo.
3. Revise los datos, elija área, categoría y prioridad, y guarde.
4. Responda el correo con el número de ticket (por ejemplo, poniendo `[Ticket 130]` al comienzo del asunto).

Si no puede guardar el `.eml`, cargue el ticket a mano y pegue el texto del correo en la descripción.

### 🙋 Presencial

Si alguien se acerca a la oficina o lo paran en un pasillo: cargue el ticket con canal **Presencial** apenas pueda.
Si lo carga más tarde, corrija el campo **Recibido** con la hora real, para que los tiempos sean correctos.

## 3. Cómo elegir la prioridad

| Prioridad | Cuándo | Objetivo |
|---|---|---|
| **Urgente** | Un despacho entero sin trabajar: sin red, sin sistema de gestión, audiencia por empezar sin equipos | 4 h |
| **Alta** | Una persona no puede trabajar (PC que no enciende, sin correo, sin acceso) | 24 h |
| **Media** | Se puede trabajar con dificultad (impresora que atasca, PC lenta) | 3 días |
| **Baja** | Pedidos que se pueden planificar (instalar un programa, mover un equipo) | 7 días |

Los tiempos objetivo se cambian en `configuracion.txt`.

## 4. El día del técnico

1. **Al llegar:** abrir el sistema (dejar la pestaña abierta todo el día; avisa con sonido 🔔).
2. **📋 Mis tickets:** columnas *Asignados (por empezar)*, *En proceso*, *En espera* y *Resueltos*. Primero los
   marcados **Urgente** o **⏰ Atrasado** (aparecen arriba).
3. **📥 Disponibles:** si tiene capacidad, **✋ Tomar** un ticket sin asignar. Si otro compañero lo tomó un segundo
   antes, el sistema avisa «ya lo tomó…»: no se duplican esfuerzos.
4. **Al empezar a trabajar:** **▶ Iniciar** (pasa a *En proceso*).
5. **Mientras trabaja:** agregue **notas** con lo que hizo («se cambió el cable», «se llamó, no estaba»). Las ven
   todos y quedan como historia.
6. **Si depende de otro** (repuesto, proveedor, el usuario no está): **⏸ En espera** con el motivo. No cuenta como
   atrasado mientras espera.
7. **Al terminar:** **✔ Resolver** escribiendo la **solución** (obligatoria). Sirve para el próximo caso parecido:
   en **🔍 Historial** se busca por texto, también dentro de las soluciones y notas.
8. **Si no puede atenderlo** (sale de comisión, no es su tema): **👥 Reasignar / liberar** → elija un compañero o
   «Liberar», y vuelve a *Disponibles*.
9. **Si vuelve a fallar:** abra el ticket resuelto y **↺ Reabrir** con el motivo, en lugar de crear uno nuevo.

Un técnico **no puede cambiar** los tickets de otro técnico (solo el jefe), pero **sí puede dejar notas** en ellos.

## 5. El día del jefe

- **Durante la mañana**, mire el **📊 Panel del jefe** (o deje una pantalla en **Modo TV**):
  - **Sin asignar** (ámbar): repártalos si nadie los toma. La pestaña *Disponibles* se resalta cuando un ticket
    espera más de 30 minutos.
  - **Atrasados** (rojo): pregunte qué falta o reasigne.
  - **Carga por técnico**: asignados, en proceso, en espera, atrasados y el ticket más antiguo de cada uno.
  - Clic en un número abre la lista filtrada.
- **Al cierre (13:30)** se genera solo el **resumen del día** en `C:\Tickets\reportes` (y por correo, si se
  configuró). También con **🖨 Resumen del día** en el panel.
- **Cada mes**: **⇩ Exportar período (CSV)** para Excel: cantidad de pedidos por área, categoría y canal, tiempos de
  resolución y porcentaje dentro del objetivo. Sirve para informes y para planificar compras (por ejemplo, si una
  impresora aparece todas las semanas).
- **Duplicados**: si se cargó dos veces el mismo pedido, anule uno con el motivo «duplicado del #…». El sistema
  avisa cuando hay tickets abiertos del mismo solicitante o del mismo área y categoría.

## 6. Avisos y automatizaciones con Windows

| Qué | Cómo |
|---|---|
| Aviso de ticket nuevo o asignado | En el navegador: sonido 🔔, mensaje abajo y número en el título de la pestaña. Se consulta al servidor cada 15 segundos. |
| Pantalla para la oficina | **Modo TV** en un monitor: sin asignar, urgentes, atrasados y carga de cada técnico, actualizado solo. |
| Resumen diario | Tarea programada «Tickets de Soporte - Resumen» (lunes a viernes, 13:30) → `reportes\resumen-AAAA-MM-DD.html`. |
| Resumen por correo | Igual, si se completa el servidor de correo interno en `configuracion.txt`. |
| Respaldo | Tarea programada «Tickets de Soporte - Respaldo», todas las noches a las 23:45. |
| Sistema siempre disponible | Tarea programada «Tickets de Soporte»: arranca con la PC y se relanza cada 5 minutos si se detuvo. |

> **¿Por qué no se cargan solos los WhatsApp y los correos?** El servidor no tiene internet, y conectar WhatsApp
> automáticamente requiere servicios externos pagos. Leer un buzón de correo automáticamente es posible solo si hay
> un servidor de correo interno accesible desde el servidor; podría agregarse en una versión futura. Mientras tanto,
> arrastrar el `.eml` completa casi todo el formulario en un segundo.

## 7. Resumen en una hoja (para pegar junto al teléfono)

```
 TODO PEDIDO ES UN TICKET  ·  http://172.31.60.254:8091  ·  tecla N = nuevo ticket

 📞 Teléfono   → cargar mientras habla · decirle el Nº · si se resolvió: casilla "Ya se resolvió"
 💬 WhatsApp   → pegar el texto · adjuntar foto/audio · responder con el Nº
 ✉ Correo      → arrastrar el .eml al formulario · responder con [Ticket Nº]
 🙋 Presencial → cargar apenas pueda · corregir la hora de "Recibido"

 Técnico: Tomar → Iniciar → notas → (En espera con motivo) → Resolver con la solución
 Urgente 4 h · Alta 24 h · Media 3 días · Baja 7 días
```
