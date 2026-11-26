-- Sistema de Tickets de tareas · Sección de Servicios Informáticos
-- Base SQLite (un solo archivo). Fechas y horas en UTC con formato ISO (aaaa-mm-ddThh:mm:ssZ).

-- ── Usuarios y sesiones ───────────────────────────────────────────────
-- TECNICO: carga tickets, toma los disponibles y trabaja los suyos.
-- JEFE: además asigna/reasigna, anula, ve el panel general y administra.
CREATE TABLE usuarios (
  id         INTEGER PRIMARY KEY,
  usuario    TEXT NOT NULL UNIQUE,
  nombre     TEXT NOT NULL,
  rol        TEXT NOT NULL CHECK (rol IN ('JEFE','TECNICO')),
  hash_clave TEXT NOT NULL,
  activo     INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
  creado_en  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE sesiones (
  token      TEXT PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  expira     TEXT NOT NULL
);

-- ── Catálogos ─────────────────────────────────────────────────────────
-- Áreas / dependencias que piden soporte (juzgados, oficinas, etc.)
CREATE TABLE areas (
  id        INTEGER PRIMARY KEY,
  nombre    TEXT NOT NULL UNIQUE,
  localidad TEXT,
  interno   TEXT,                       -- número de teléfono interno habitual
  activo    INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE categorias (
  id     INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

-- ── Tickets ───────────────────────────────────────────────────────────
CREATE TABLE tickets (
  id                INTEGER PRIMARY KEY,
  canal             TEXT NOT NULL CHECK (canal IN ('TELEFONO','WHATSAPP','CORREO','PRESENCIAL')),
  canal_referencia  TEXT,               -- nº de WhatsApp, asunto del correo, interno que llamó…
  solicitante       TEXT NOT NULL,      -- persona que pidió
  contacto          TEXT,               -- interno, celular o correo para responderle
  area_id           INTEGER REFERENCES areas(id),
  categoria_id      INTEGER REFERENCES categorias(id),
  asunto            TEXT NOT NULL,
  descripcion       TEXT,
  prioridad         TEXT NOT NULL DEFAULT 'MEDIA' CHECK (prioridad IN ('BAJA','MEDIA','ALTA','URGENTE')),
  estado            TEXT NOT NULL DEFAULT 'NUEVO'
                    CHECK (estado IN ('NUEVO','ASIGNADO','EN_PROCESO','EN_ESPERA','RESUELTO','ANULADO')),
  tecnico_id        INTEGER REFERENCES usuarios(id),
  motivo_espera     TEXT,
  solucion          TEXT,
  motivo_anulacion  TEXT,
  recibido_en       TEXT NOT NULL,      -- cuándo llegó el pedido (puede ser antes de cargarlo)
  asignado_en       TEXT,
  iniciado_en       TEXT,               -- primera vez que pasó a EN_PROCESO
  resuelto_en       TEXT,
  version           INTEGER NOT NULL DEFAULT 1,
  creado_por        INTEGER REFERENCES usuarios(id),
  creado_en         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  modificado_por    INTEGER REFERENCES usuarios(id),
  modificado_en     TEXT,
  -- Coherencia entre estado y técnico (también lo controla la aplicación)
  CHECK (estado <> 'NUEVO' OR tecnico_id IS NULL),
  CHECK (estado NOT IN ('ASIGNADO','EN_PROCESO','EN_ESPERA','RESUELTO') OR tecnico_id IS NOT NULL),
  CHECK (estado <> 'RESUELTO' OR (solucion IS NOT NULL AND trim(solucion) <> '')),
  CHECK (estado <> 'ANULADO' OR (motivo_anulacion IS NOT NULL AND trim(motivo_anulacion) <> ''))
);
CREATE INDEX tickets_estado_idx ON tickets (estado, prioridad);
CREATE INDEX tickets_tecnico_idx ON tickets (tecnico_id, estado);
CREATE INDEX tickets_recibido_idx ON tickets (recibido_en);

-- Historial de cada ticket: notas de los técnicos y cambios de estado/asignación
CREATE TABLE notas (
  id         INTEGER PRIMARY KEY,
  ticket_id  INTEGER NOT NULL REFERENCES tickets(id),
  tipo       TEXT NOT NULL CHECK (tipo IN ('NOTA','ESTADO','ASIGNACION','EDICION','ADJUNTO')),
  texto      TEXT NOT NULL,
  usuario_id INTEGER REFERENCES usuarios(id),
  creado_en  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX notas_ticket_idx ON notas (ticket_id, id);

-- Archivos adjuntos (correo .eml, captura de WhatsApp, PDF…)
CREATE TABLE adjuntos (
  id         INTEGER PRIMARY KEY,
  ticket_id  INTEGER NOT NULL REFERENCES tickets(id),
  nombre     TEXT NOT NULL,              -- nombre original
  archivo    TEXT NOT NULL UNIQUE,       -- nombre en datos/adjuntos
  bytes      INTEGER NOT NULL,
  subido_por INTEGER REFERENCES usuarios(id),
  creado_en  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX adjuntos_ticket_idx ON adjuntos (ticket_id);

-- ── Auditoría ─────────────────────────────────────────────────────────
CREATE TABLE auditoria (
  id                       INTEGER PRIMARY KEY,
  tabla                    TEXT NOT NULL,
  registro_id              INTEGER NOT NULL,
  accion                   TEXT NOT NULL,              -- CREAR | MODIFICAR | ESTADO | ASIGNAR | ANULAR | ELIMINAR…
  datos                    TEXT NOT NULL,              -- JSON
  advertencias_confirmadas TEXT,                       -- JSON
  usuario_id               INTEGER REFERENCES usuarios(id),
  ts                       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX auditoria_ts_idx ON auditoria (ts DESC);

CREATE TABLE version_esquema (
  version     INTEGER PRIMARY KEY,
  aplicado_en TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
INSERT INTO version_esquema (version) VALUES (1);

-- ── Datos base ────────────────────────────────────────────────────────
INSERT INTO categorias (nombre) VALUES
  ('Computadora / hardware'),
  ('Impresora / escáner'),
  ('Red / internet'),
  ('Correo electrónico'),
  ('Sistema de gestión judicial'),
  ('Usuario y contraseña'),
  ('Programas / software'),
  ('Telefonía'),
  ('Audiencias / videoconferencia'),
  ('Otro');
