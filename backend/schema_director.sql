-- Ejecutar este archivo en Supabase SQL Editor antes de publicar el nuevo backend.
-- Crea login por usuario/contraseña, rol director y asignaciones de cursos a docentes.

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario SERIAL PRIMARY KEY,
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('director', 'docente', 'estudiante')),
    usuario VARCHAR(100) NOT NULL,
    nombre_completo TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_temporal TEXT,
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (rol, usuario)
);

CREATE TABLE IF NOT EXISTS docentes_cursos (
    id_docente_curso SERIAL PRIMARY KEY,
    id_docente INTEGER NOT NULL REFERENCES docentes(id_docente),
    id_carrera INTEGER NOT NULL REFERENCES carreras(id_carrera),
    id_grado INTEGER NOT NULL REFERENCES grados(id_grado),
    id_curso INTEGER NOT NULL REFERENCES cursos(id_curso),
    id_ciclo INTEGER NOT NULL REFERENCES ciclos_escolares(id_ciclo),
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (id_docente, id_carrera, id_grado, id_curso, id_ciclo)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_docentes_codigo_docente
    ON docentes (codigo_docente);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alumnos_codigo_carnet
    ON alumnos (codigo_carnet);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cursos_nombre
    ON cursos (nombre);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cursos_por_grado_unico
    ON cursos_por_grado (id_carrera, id_grado, id_curso);

CREATE TABLE IF NOT EXISTS asistencias (
    id_asistencia SERIAL PRIMARY KEY,
    id_alumno INTEGER NOT NULL REFERENCES alumnos(id_alumno),
    codigo_carnet VARCHAR(100),
    fecha DATE NOT NULL,
    hora_entrada TIME,
    hora_salida TIME,
    registrado_por_rol VARCHAR(20) CHECK (registrado_por_rol IN ('docente')),
    registrado_por_codigo VARCHAR(100),
    creado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (id_alumno, fecha)
);

CREATE INDEX IF NOT EXISTS idx_asistencias_fecha
    ON asistencias (fecha);

CREATE INDEX IF NOT EXISTS idx_asistencias_alumno_fecha
    ON asistencias (id_alumno, fecha);

CREATE INDEX IF NOT EXISTS idx_asistencias_carnet_fecha
    ON asistencias (codigo_carnet, fecha);

-- Cuenta inicial del director.
-- Usuario: director
-- Contraseña: Director2026!
INSERT INTO usuarios (
    rol,
    usuario,
    nombre_completo,
    password_hash,
    password_temporal,
    estado
)
VALUES (
    'director',
    'director',
    'Director del Instituto',
    'pbkdf2_sha256$100000$1zxRncT2MdHUzA9RrJGNug==$AjhPExTxmc9dCZCSrilkunM3QC7qSBn+i0G+XZrwDhI=',
    'Director2026!',
    TRUE
)
ON CONFLICT (rol, usuario)
DO UPDATE SET
    nombre_completo = EXCLUDED.nombre_completo,
    password_hash = EXCLUDED.password_hash,
    password_temporal = EXCLUDED.password_temporal,
    estado = TRUE;

-- Crea cuentas para docentes que ya existen.
-- Usuario: codigo_docente
-- Contraseña inicial: Docente2026!
INSERT INTO usuarios (
    rol,
    usuario,
    nombre_completo,
    password_hash,
    password_temporal,
    estado
)
SELECT
    'docente',
    d.codigo_docente,
    d.nombre_completo,
    'pbkdf2_sha256$100000$M10fM7SBEq04qWUgmVMXeA==$R17bWv/PsuCF27jR8jDsiocVBwNbACkAGeG3zHR4Hrg=',
    'Docente2026!',
    COALESCE(d.estado, TRUE)
FROM docentes d
ON CONFLICT (rol, usuario)
DO UPDATE SET
    nombre_completo = EXCLUDED.nombre_completo,
    estado = EXCLUDED.estado;

-- Crea cuentas para estudiantes que ya existen.
-- Usuario: codigo_carnet
-- Contraseña inicial: Estudiante2026!
INSERT INTO usuarios (
    rol,
    usuario,
    nombre_completo,
    password_hash,
    password_temporal,
    estado
)
SELECT
    'estudiante',
    a.codigo_carnet,
    TRIM(a.nombres || ' ' || a.apellidos),
    'pbkdf2_sha256$100000$a0ptEDvgj4woTyH3bbsovw==$XDznRd++nMduhT2zPWxAFKDghwhaE+0kgVGZIxo8Rnc=',
    'Estudiante2026!',
    COALESCE(a.estado, TRUE)
FROM alumnos a
ON CONFLICT (rol, usuario)
DO UPDATE SET
    nombre_completo = EXCLUDED.nombre_completo,
    estado = EXCLUDED.estado;

-- Si actualmente solo existe un docente, se le asignan los cursos ya registrados por carrera/grado.
-- Si hay varios docentes, esta parte no asigna automáticamente para evitar asignaciones incorrectas.
INSERT INTO docentes_cursos (
    id_docente,
    id_carrera,
    id_grado,
    id_curso,
    id_ciclo,
    estado
)
SELECT
    d.id_docente,
    cpg.id_carrera,
    cpg.id_grado,
    cpg.id_curso,
    ce.id_ciclo,
    TRUE
FROM docentes d
CROSS JOIN cursos_por_grado cpg
CROSS JOIN ciclos_escolares ce
WHERE d.estado = TRUE
  AND (SELECT COUNT(*) FROM docentes WHERE estado = TRUE) = 1
ON CONFLICT (id_docente, id_carrera, id_grado, id_curso, id_ciclo)
DO UPDATE SET estado = TRUE;
