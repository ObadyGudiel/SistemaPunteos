from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from openpyxl import load_workbook
from io import BytesIO
import psycopg2
import psycopg2.extras
import psycopg2.errors
import unicodedata
import os


app = FastAPI(title="Sistema de Punteos")


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# CONFIGURACIÓN POSTGRESQL / SUPABASE
# =========================
# En Render estos valores se colocan como Environment Variables.
# No escribas contraseñas directamente en el código.

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432"),
    "sslmode": os.getenv("DB_SSLMODE", "require")
}

DB_CLIENT_ENCODING = "UTF8"


def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding(DB_CLIENT_ENCODING)
    return conn


# =========================
# FUNCIONES AUXILIARES
# =========================

def convertir_decimal(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def limpiar_fila(fila):
    return {
        clave: convertir_decimal(valor)
        for clave, valor in dict(fila).items()
    }


def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )
    texto = " ".join(texto.split())
    return texto


def normalizar_encabezado(texto):
    if texto is None:
        return ""

    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )
    texto = texto.replace(" ", "_").replace("-", "_")
    return texto


def obtener_valor_fila(hoja, fila, indice_columna):
    if indice_columna is None:
        return None
    return hoja.cell(row=fila, column=indice_columna).value


def convertir_numero_excel(valor):
    if valor is None or valor == "":
        return 0

    try:
        return float(valor)
    except Exception:
        raise ValueError(f"Valor numérico inválido: {valor}")


def cerrar_conexion(cursor=None, conn=None):
    try:
        if cursor:
            cursor.close()
    except Exception:
        pass

    try:
        if conn:
            conn.close()
    except Exception:
        pass


# =========================
# MODELOS
# =========================

class LoginRequest(BaseModel):
    rol: str
    codigo: str
    nombre_completo: str


class NotaRequest(BaseModel):
    codigo_carnet: str
    carrera: str
    grado: str
    curso: str
    bimestre: str
    ciclo_escolar: int = 2026
    actitudinal: float
    zona: float
    examen: float
    observacion: Optional[str] = None


# =========================
# RUTA PRINCIPAL
# =========================

@app.get("/")
def inicio():
    return {
        "mensaje": "API del Sistema de Punteos funcionando correctamente"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# =========================
# LOGIN
# =========================

@app.post("/login")
def login(data: LoginRequest):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        rol = data.rol.lower().strip()
        codigo = data.codigo.strip()
        nombre_ingresado = normalizar_texto(data.nombre_completo)

        if rol == "docente":
            query = """
                SELECT 
                    codigo_docente,
                    nombre_completo
                FROM docentes
                WHERE codigo_docente = %s
                  AND estado = TRUE;
            """

            cursor.execute(query, (codigo,))
            docente = cursor.fetchone()

            if not docente:
                raise HTTPException(
                    status_code=404,
                    detail="Docente no encontrado"
                )

            nombre_docente = normalizar_texto(docente["nombre_completo"])

            if nombre_ingresado != nombre_docente:
                raise HTTPException(
                    status_code=401,
                    detail="Nombre completo incorrecto"
                )

            return {
                "rol": "docente",
                "codigo": docente["codigo_docente"],
                "nombre_completo": docente["nombre_completo"]
            }

        elif rol == "estudiante":
            query = """
                SELECT 
                    codigo_carnet,
                    nombres,
                    apellidos
                FROM alumnos
                WHERE codigo_carnet = %s
                  AND estado = TRUE;
            """

            cursor.execute(query, (codigo,))
            estudiante = cursor.fetchone()

            if not estudiante:
                raise HTTPException(
                    status_code=404,
                    detail="Estudiante no encontrado"
                )

            nombre_forma_1 = normalizar_texto(
                f"{estudiante['nombres']} {estudiante['apellidos']}"
            )

            nombre_forma_2 = normalizar_texto(
                f"{estudiante['apellidos']} {estudiante['nombres']}"
            )

            if nombre_ingresado != nombre_forma_1 and nombre_ingresado != nombre_forma_2:
                raise HTTPException(
                    status_code=401,
                    detail="Nombre completo incorrecto"
                )

            return {
                "rol": "estudiante",
                "codigo": estudiante["codigo_carnet"],
                "nombres": estudiante["nombres"],
                "apellidos": estudiante["apellidos"]
            }

        else:
            raise HTTPException(
                status_code=400,
                detail="Rol inválido. Debe ser docente o estudiante"
            )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el servidor: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)


# =========================
# CONSULTAR PUNTEOS DEL ESTUDIANTE
# =========================

@app.get("/estudiantes/{codigo_carnet}")
def obtener_estudiante(codigo_carnet: str):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            SELECT 
                codigo_carnet,
                apellidos,
                nombres,
                carrera,
                grado,
                curso,
                ciclo_escolar,
                primer_bimestre,
                segundo_bimestre,
                tercer_bimestre,
                cuarto_bimestre,
                promedio_final,
                estado
            FROM vista_promedio_alumnos
            WHERE codigo_carnet = %s
            ORDER BY curso;
        """

        cursor.execute(query, (codigo_carnet,))
        resultados = cursor.fetchall()

        if not resultados:
            raise HTTPException(
                status_code=404,
                detail="No se encontró información para este código de carnet"
            )

        estudiante = resultados[0]

        cursos = []

        for fila in resultados:
            cursos.append({
                "curso": fila["curso"],
                "primer_bimestre": convertir_decimal(fila["primer_bimestre"]),
                "segundo_bimestre": convertir_decimal(fila["segundo_bimestre"]),
                "tercer_bimestre": convertir_decimal(fila["tercer_bimestre"]),
                "cuarto_bimestre": convertir_decimal(fila["cuarto_bimestre"]),
                "promedio_final": convertir_decimal(fila["promedio_final"]),
                "estado": fila["estado"]
            })

        return {
            "codigo_carnet": estudiante["codigo_carnet"],
            "apellidos": estudiante["apellidos"],
            "nombres": estudiante["nombres"],
            "carrera": estudiante["carrera"],
            "grado": estudiante["grado"],
            "ciclo_escolar": estudiante["ciclo_escolar"],
            "cursos": cursos
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el servidor: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)


# =========================
# DOCENTE: VER TODOS LOS PUNTEOS
# =========================

@app.get("/docente/punteos")
def ver_todos_los_punteos(
    carrera: Optional[str] = Query(None),
    grado: Optional[str] = Query(None),
    curso: Optional[str] = Query(None),
    ciclo_escolar: Optional[int] = Query(None)
):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        condiciones = []
        parametros = []

        if carrera:
            condiciones.append("carrera = %s")
            parametros.append(carrera)

        if grado:
            condiciones.append("grado = %s")
            parametros.append(grado)

        if curso:
            condiciones.append("curso = %s")
            parametros.append(curso)

        if ciclo_escolar:
            condiciones.append("ciclo_escolar = %s")
            parametros.append(ciclo_escolar)

        where_sql = ""

        if condiciones:
            where_sql = "WHERE " + " AND ".join(condiciones)

        query = f"""
            SELECT *
            FROM vista_promedio_alumnos
            {where_sql}
            ORDER BY carrera, grado, apellidos, nombres, curso;
        """

        cursor.execute(query, parametros)
        resultados = cursor.fetchall()

        return [limpiar_fila(fila) for fila in resultados]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el servidor: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)


# =========================
# DOCENTE: INSERTAR NOTA
# =========================

@app.post("/docente/notas")
def insertar_nota(data: NotaRequest):
    conn = None
    cursor = None

    try:
        if data.actitudinal + data.zona + data.examen > 100:
            raise HTTPException(
                status_code=400,
                detail="La suma de actitudinal, zona y examen no puede ser mayor a 100"
            )

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            INSERT INTO notas (
                id_asignacion,
                id_curso,
                id_bimestre,
                actitudinal,
                zona,
                examen,
                observacion
            )
            SELECT 
                asi.id_asignacion,
                cu.id_curso,
                bi.id_bimestre,
                %s,
                %s,
                %s,
                %s
            FROM asignaciones asi
            INNER JOIN alumnos a ON asi.id_alumno = a.id_alumno
            INNER JOIN carreras ca ON asi.id_carrera = ca.id_carrera
            INNER JOIN grados gr ON asi.id_grado = gr.id_grado
            INNER JOIN ciclos_escolares ce ON asi.id_ciclo = ce.id_ciclo
            INNER JOIN cursos cu ON cu.nombre = %s
            INNER JOIN bimestres bi ON bi.nombre = %s
            WHERE a.codigo_carnet = %s
              AND ca.nombre = %s
              AND gr.nombre = %s
              AND ce.anio = %s
            RETURNING id_nota;
        """

        cursor.execute(query, (
            data.actitudinal,
            data.zona,
            data.examen,
            data.observacion,
            data.curso,
            data.bimestre,
            data.codigo_carnet,
            data.carrera,
            data.grado,
            data.ciclo_escolar
        ))

        nota = cursor.fetchone()

        if not nota:
            conn.rollback()
            raise HTTPException(
                status_code=404,
                detail="No se encontró alumno, carrera, grado, curso o bimestre"
            )

        conn.commit()

        return {
            "mensaje": "Nota insertada correctamente",
            "id_nota": nota["id_nota"]
        }

    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=409,
            detail="Ya existe una nota registrada para este alumno, curso y bimestre. Use actualizar."
        )

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error en el servidor: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)


# =========================
# DOCENTE: ACTUALIZAR NOTA
# =========================

@app.put("/docente/notas")
def actualizar_nota(data: NotaRequest):
    conn = None
    cursor = None

    try:
        if data.actitudinal + data.zona + data.examen > 100:
            raise HTTPException(
                status_code=400,
                detail="La suma de actitudinal, zona y examen no puede ser mayor a 100"
            )

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            UPDATE notas n
            SET 
                actitudinal = %s,
                zona = %s,
                examen = %s,
                observacion = %s
            FROM asignaciones asi
            INNER JOIN alumnos a ON asi.id_alumno = a.id_alumno
            INNER JOIN carreras ca ON asi.id_carrera = ca.id_carrera
            INNER JOIN grados gr ON asi.id_grado = gr.id_grado
            INNER JOIN ciclos_escolares ce ON asi.id_ciclo = ce.id_ciclo
            INNER JOIN cursos cu ON cu.nombre = %s
            INNER JOIN bimestres bi ON bi.nombre = %s
            WHERE n.id_asignacion = asi.id_asignacion
              AND n.id_curso = cu.id_curso
              AND n.id_bimestre = bi.id_bimestre
              AND a.codigo_carnet = %s
              AND ca.nombre = %s
              AND gr.nombre = %s
              AND ce.anio = %s
            RETURNING n.id_nota;
        """

        cursor.execute(query, (
            data.actitudinal,
            data.zona,
            data.examen,
            data.observacion,
            data.curso,
            data.bimestre,
            data.codigo_carnet,
            data.carrera,
            data.grado,
            data.ciclo_escolar
        ))

        nota = cursor.fetchone()

        if not nota:
            conn.rollback()
            raise HTTPException(
                status_code=404,
                detail="No se encontró la nota para actualizar"
            )

        conn.commit()

        return {
            "mensaje": "Nota actualizada correctamente",
            "id_nota": nota["id_nota"]
        }

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error en el servidor: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)


# =========================
# DOCENTE: ELIMINAR NOTA
# =========================

@app.delete("/docente/notas")
def eliminar_nota(
    codigo_carnet: str,
    carrera: str,
    grado: str,
    curso: str,
    bimestre: str,
    ciclo_escolar: int = 2026
):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            DELETE FROM notas n
            USING asignaciones asi,
                  alumnos a,
                  carreras ca,
                  grados gr,
                  ciclos_escolares ce,
                  cursos cu,
                  bimestres bi
            WHERE n.id_asignacion = asi.id_asignacion
              AND asi.id_alumno = a.id_alumno
              AND asi.id_carrera = ca.id_carrera
              AND asi.id_grado = gr.id_grado
              AND asi.id_ciclo = ce.id_ciclo
              AND n.id_curso = cu.id_curso
              AND n.id_bimestre = bi.id_bimestre
              AND a.codigo_carnet = %s
              AND ca.nombre = %s
              AND gr.nombre = %s
              AND cu.nombre = %s
              AND bi.nombre = %s
              AND ce.anio = %s
            RETURNING n.id_nota;
        """

        cursor.execute(query, (
            codigo_carnet,
            carrera,
            grado,
            curso,
            bimestre,
            ciclo_escolar
        ))

        nota = cursor.fetchone()

        if not nota:
            conn.rollback()
            raise HTTPException(
                status_code=404,
                detail="No se encontró la nota para eliminar"
            )

        conn.commit()

        return {
            "mensaje": "Nota eliminada correctamente",
            "id_nota": nota["id_nota"]
        }

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error en el servidor: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)


# =========================
# DOCENTE: IMPORTAR EXCEL
# =========================

@app.post("/docente/importar-excel")
async def importar_excel(
    archivo: UploadFile = File(...),
    carrera: str = Form(...),
    grado: str = Form(...),
    curso: str = Form(...),
    bimestre: str = Form(...),
    ciclo_escolar: int = Form(2026)
):
    conn = None
    cursor = None

    try:
        if not archivo.filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail="Solo se permiten archivos Excel con extensión .xlsx"
            )

        contenido = await archivo.read()
        libro = load_workbook(filename=BytesIO(contenido), data_only=True)
        hoja = libro.active

        encabezados = {}

        for columna in range(1, hoja.max_column + 1):
            valor = hoja.cell(row=1, column=columna).value
            encabezados[normalizar_encabezado(valor)] = columna

        col_codigo = (
            encabezados.get("codigo_carnet")
            or encabezados.get("codigo")
            or encabezados.get("carnet")
        )

        col_actitudinal = encabezados.get("actitudinal")
        col_zona = encabezados.get("zona")
        col_examen = encabezados.get("examen")
        col_observacion = encabezados.get("observacion")

        if not col_codigo or not col_actitudinal or not col_zona or not col_examen:
            raise HTTPException(
                status_code=400,
                detail="El Excel debe tener las columnas: codigo_carnet, actitudinal, zona y examen"
            )

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        procesados = 0
        errores = []

        for fila in range(2, hoja.max_row + 1):
            codigo_carnet = obtener_valor_fila(hoja, fila, col_codigo)

            if codigo_carnet is None or str(codigo_carnet).strip() == "":
                continue

            codigo_carnet = str(codigo_carnet).strip()

            try:
                actitudinal = convertir_numero_excel(
                    obtener_valor_fila(hoja, fila, col_actitudinal)
                )

                zona = convertir_numero_excel(
                    obtener_valor_fila(hoja, fila, col_zona)
                )

                examen = convertir_numero_excel(
                    obtener_valor_fila(hoja, fila, col_examen)
                )

                observacion = obtener_valor_fila(hoja, fila, col_observacion)

                if observacion is not None:
                    observacion = str(observacion).strip()

                total = actitudinal + zona + examen

                if total > 100:
                    errores.append({
                        "fila": fila,
                        "codigo_carnet": codigo_carnet,
                        "error": "La suma de actitudinal, zona y examen supera 100"
                    })
                    continue

                query = """
                    INSERT INTO notas (
                        id_asignacion,
                        id_curso,
                        id_bimestre,
                        actitudinal,
                        zona,
                        examen,
                        observacion
                    )
                    SELECT 
                        asi.id_asignacion,
                        cu.id_curso,
                        bi.id_bimestre,
                        %s,
                        %s,
                        %s,
                        %s
                    FROM asignaciones asi
                    INNER JOIN alumnos a ON asi.id_alumno = a.id_alumno
                    INNER JOIN carreras ca ON asi.id_carrera = ca.id_carrera
                    INNER JOIN grados gr ON asi.id_grado = gr.id_grado
                    INNER JOIN ciclos_escolares ce ON asi.id_ciclo = ce.id_ciclo
                    INNER JOIN cursos cu ON cu.nombre = %s
                    INNER JOIN bimestres bi ON bi.nombre = %s
                    WHERE a.codigo_carnet = %s
                      AND ca.nombre = %s
                      AND gr.nombre = %s
                      AND ce.anio = %s
                    ON CONFLICT (id_asignacion, id_curso, id_bimestre)
                    DO UPDATE SET
                        actitudinal = EXCLUDED.actitudinal,
                        zona = EXCLUDED.zona,
                        examen = EXCLUDED.examen,
                        observacion = EXCLUDED.observacion
                    RETURNING id_nota;
                """

                cursor.execute(query, (
                    actitudinal,
                    zona,
                    examen,
                    observacion,
                    curso,
                    bimestre,
                    codigo_carnet,
                    carrera,
                    grado,
                    ciclo_escolar
                ))

                resultado = cursor.fetchone()

                if not resultado:
                    errores.append({
                        "fila": fila,
                        "codigo_carnet": codigo_carnet,
                        "error": "No se encontró el alumno con esa carrera, grado o ciclo escolar"
                    })
                    continue

                procesados += 1

            except Exception as e:
                errores.append({
                    "fila": fila,
                    "codigo_carnet": codigo_carnet,
                    "error": str(e)
                })

        conn.commit()

        return {
            "mensaje": "Importación finalizada",
            "procesados": procesados,
            "errores": errores
        }

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error al importar Excel: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)


# =========================
# CATÁLOGOS
# =========================

@app.get("/catalogos")
def obtener_catalogos():
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT nombre, tipo FROM carreras ORDER BY nombre;")
        carreras = cursor.fetchall()

        cursor.execute("SELECT nombre, numero FROM grados ORDER BY numero;")
        grados = cursor.fetchall()

        cursor.execute("SELECT nombre FROM cursos ORDER BY nombre;")
        cursos = cursor.fetchall()

        cursor.execute("SELECT nombre, numero FROM bimestres ORDER BY numero;")
        bimestres = cursor.fetchall()

        cursor.execute("SELECT anio FROM ciclos_escolares ORDER BY anio DESC;")
        ciclos = cursor.fetchall()

        return {
            "carreras": [limpiar_fila(fila) for fila in carreras],
            "grados": [limpiar_fila(fila) for fila in grados],
            "cursos": [limpiar_fila(fila) for fila in cursos],
            "bimestres": [limpiar_fila(fila) for fila in bimestres],
            "ciclos": [limpiar_fila(fila) for fila in ciclos]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el servidor: {str(e)}"
        )

    finally:
        cerrar_conexion(cursor, conn)