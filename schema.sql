
CREATE TABLE IF NOT EXISTS roles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL
);

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
  username TEXT PRIMARY KEY,
  password TEXT NOT NULL,
  rol_id INTEGER NOT NULL,
  FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE RESTRICT
);

-- Tabla de Cargos
CREATE TABLE IF NOT EXISTS cargos (
  id_cargo INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre_cargo TEXT NOT NULL UNIQUE
);

-- Tabla de Grados
CREATE TABLE IF NOT EXISTS grados (
  id_grado INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre_grado TEXT NOT NULL UNIQUE
);

-- Tabla de Secciones
CREATE TABLE IF NOT EXISTS secciones (
  id_seccion INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre_seccion TEXT NOT NULL UNIQUE
);

-- Tabla de Docentes
CREATE TABLE IF NOT EXISTS docentes (
  dni TEXT PRIMARY KEY,
  nombres TEXT NOT NULL,
  apellido_paterno TEXT NOT NULL,
  apellido_materno TEXT NOT NULL,
  tipo TEXT DEFAULT 'Titular' CHECK (tipo IN ('Titular', 'Sustituto')),
  cargo_id INTEGER NOT NULL,
  grado_id INTEGER,
  seccion_id INTEGER,
  FOREIGN KEY (cargo_id) REFERENCES cargos(id_cargo) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (grado_id) REFERENCES grados(id_grado) ON DELETE SET NULL ON UPDATE CASCADE,
  FOREIGN KEY (seccion_id) REFERENCES secciones(id_seccion) ON DELETE SET NULL ON UPDATE CASCADE
);

-- Horarios asignados a docentes
CREATE TABLE IF NOT EXISTS horarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dni TEXT NOT NULL,
  dia_semana TEXT NOT NULL,
  hora_inicio TEXT NOT NULL, -- HH:MM
  hora_fin TEXT NOT NULL,     -- HH:MM
  FOREIGN KEY (dni) REFERENCES docentes(dni) ON DELETE CASCADE,
  UNIQUE(dni, dia_semana) -- Evita horarios duplicados para el mismo día
);

-- Asistencias
CREATE TABLE IF NOT EXISTS asistencias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dni TEXT NOT NULL,
  fecha TEXT NOT NULL, 
  hora_registro TEXT
  hora_salida TEXT,         
  estado TEXT NOT NULL CHECK (estado IN ('A tiempo', 'Tarde', 'Inasistencia')),
  FOREIGN KEY (dni) REFERENCES docentes(dni) ON DELETE CASCADE
);


CREATE UNIQUE INDEX IF NOT EXISTS idx_unica_asistencia_por_dia ON asistencias(dni, date(fecha));

-- Justificaciones
CREATE TABLE IF NOT EXISTS justificaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asistencia_id INTEGER NOT NULL UNIQUE,
  motivo TEXT NOT NULL,
  archivo_justificante TEXT,
  estado TEXT DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Aprobada', 'Rechazada')),
  FOREIGN KEY (asistencia_id) REFERENCES asistencias(id) ON DELETE CASCADE
);

-- Advertencias
CREATE TABLE IF NOT EXISTS advertencias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dni TEXT NOT NULL,
  motivo TEXT NOT NULL,
  fecha TEXT NOT NULL, 
  FOREIGN KEY (dni) REFERENCES docentes(dni) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_advertencia_unica ON advertencias(dni, motivo, fecha);

-- Fechas no laborables
CREATE TABLE IF NOT EXISTS fechas_no_laborables (
  fecha TEXT PRIMARY KEY,             
  descripcion TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('Feriado', 'Institucional'))
);

-- Tabla de permisos de docentes
CREATE TABLE IF NOT EXISTS permisos_docentes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dni TEXT NOT NULL,
  fecha_inicio TEXT NOT NULL,
  fecha_fin TEXT NOT NULL,    
  motivo TEXT NOT NULL,
  observaciones TEXT,
  FOREIGN KEY (dni) REFERENCES docentes(dni) ON DELETE CASCADE
);

-- Tabla de sustituciones 
CREATE TABLE IF NOT EXISTS sustituciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  permiso_id INTEGER NOT NULL,
  sustituto_dni TEXT NOT NULL,
  fecha_inicio TEXT NOT NULL, 
  fecha_fin TEXT NOT NULL,    
  FOREIGN KEY (permiso_id) REFERENCES permisos_docentes(id) ON DELETE CASCADE,
  FOREIGN KEY (sustituto_dni) REFERENCES docentes(dni) ON DELETE CASCADE
);