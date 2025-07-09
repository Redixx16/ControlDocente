 
import os
import io
import locale
import sqlite3
import uuid
from datetime import datetime, time, timedelta
import platform
import subprocess


  Imports de Flask y Werkzeug
from flask import (
    Blueprint, render_template, request, redirect, send_file, url_for, 
    flash, session, current_app, jsonify,send_from_directory, abort
)
from werkzeug.utils import secure_filename

  Imports de ReportLab
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Line

  Imports de tu Proyecto
from db import get_db
from utils.format import formatear_fecha, formatear_hora, validar_dni
from utils.roles import requiere_rol

EXTENSIONES_PERMITIDAS = {'.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
attendance_bp = Blueprint('attendance', __name__)

MIN_WORK_DURATION_MINUTES = 60


@attendance_bp.before_request
def require_login():
    rutas_publicas = ['attendance.index']
    if request.endpoint not in rutas_publicas and not session.get('usuario'):
        return redirect(url_for('auth.login'))

@attendance_bp.route('/generar_inasistencias', methods=['POST'])
@requiere_rol(1, 2)
def generar_inasistencias_route():
      Esta función se mantiene, solo llama al helper que vamos a modificar
    fecha = request.form.get('fecha') or datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    
    feriado = db.execute("SELECT descripcion FROM fechas_no_laborables WHERE fecha = ?", (fecha,)).fetchone()
    if feriado:
        return jsonify({'status': 'info', 'mensaje': f"📅 {feriado['descripcion']}. Es un día no laborable."})

    ya_existen = db.execute("SELECT COUNT(*) FROM asistencias WHERE DATE(fecha) = ? AND estado = 'Inasistencia'", (fecha,)).fetchone()[0]
    if ya_existen:
        return jsonify({'status': 'info', 'mensaje': f"Ya se registraron inasistencias para {fecha}."})

    n = generar_inasistencias_faltantes(fecha)
    return jsonify({'status': 'success', 'mensaje': f"Se registraron {n} inasistencias para {fecha}."})


  En routes/attendance.py

@attendance_bp.route('/', methods=['GET', 'POST'])
def index():
    mensaje = None
    if request.method == 'POST':
        dni = request.form['codigo'].strip()
        db = get_db()
        
        if not validar_dni(dni):
            mensaje = {'texto': 'El DNI debe tener 8 dígitos numéricos', 'tipo': 'danger'}
            return render_template('index.html', mensaje=mensaje)

        docente_info = db.execute("SELECT nombres || ' ' || apellido_paterno AS nombre FROM docentes WHERE dni = ?", (dni,)).fetchone()

        if not docente_info:
            mensaje = {'texto': '⛔ DNI no encontrado. Por favor, regístrese primero.', 'tipo': 'danger'}
            return render_template('index.html', mensaje=mensaje)
            
        nombre = docente_info['nombre']
        ahora = datetime.now()
        fecha_actual = ahora.strftime('%Y-%m-%d')
        
        if db.execute("SELECT 1 FROM fechas_no_laborables WHERE fecha = ?", (fecha_actual,)).fetchone():
            mensaje = {'texto': '⛔ Hoy es feriado. No se puede registrar asistencia.', 'tipo': 'info'}
            return render_template('index.html', mensaje=mensaje)

        permiso_activo = db.execute("""
            SELECT 1 FROM permisos_docentes
            WHERE dni = ? AND (? BETWEEN fecha_inicio AND fecha_fin)
        """, (dni, fecha_actual)).fetchone()

        if permiso_activo:
            mensaje = {'texto': f"🚫 {nombre} tiene un permiso activo hoy. No se puede registrar.", 'tipo': 'info'}
            return render_template('index.html', mensaje=mensaje)
        
         
        
        registro_hoy = db.execute(
             
            "SELECT id, fecha, hora_salida FROM asistencias WHERE dni = ? AND DATE(fecha) = ?",
            (dni, fecha_actual)
        ).fetchone()

        if registro_hoy:
             
            
            if registro_hoy['hora_salida']:
                 
                mensaje = {'texto': f"✅ {nombre}, ya registraste tu entrada y salida por hoy.", 'tipo': 'info'}
            else:
 
                
                 
                fecha_ingreso = datetime.strptime(registro_hoy['fecha'], '%Y-%m-%d %H:%M:%S')
                
                 
                tiempo_transcurrido = ahora - fecha_ingreso

                if tiempo_transcurrido < timedelta(minutes=MIN_WORK_DURATION_MINUTES):
                     
                    hora_ingreso_str = fecha_ingreso.strftime('%H:%M:%S')
                    mensaje = {'texto': f"👍 {nombre}, ya registraste tu entrada hoy a las {hora_ingreso_str}.", 'tipo': 'info'}
                else:
                     
                    hora_salida_str = ahora.strftime('%H:%M:%S')
                    db.execute(
                        "UPDATE asistencias SET hora_salida = ? WHERE id = ?",
                        (hora_salida_str, registro_hoy['id'])
                    )
                    db.commit()
                    mensaje = {'texto': f"👋 ¡Hasta luego, {nombre}! Tu salida ha sido registrada a las {hora_salida_str}.", 'tipo': 'success'}
        else:
             
            
            hora_actual_str = ahora.strftime('%H:%M:%S')
            hora_actual = ahora.time()
            dia_semana_full = ahora.strftime('%A')
            dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miercoles', 'Thursday': 'Jueves', 'Friday': 'Viernes'}
            dia_semana = dias_es.get(dia_semana_full, dia_semana_full)

            horario_efectivo = None
            horario_regular = db.execute("SELECT hora_inicio FROM horarios WHERE dni = ? AND dia_semana = ?", (dni, dia_semana)).fetchone()
            if horario_regular:
                horario_efectivo = horario_regular['hora_inicio']
            else:
                sustitucion_activa = db.execute("""
                    SELECT pd.dni AS titular_dni FROM sustituciones s 
                    JOIN permisos_docentes pd ON s.permiso_id = pd.id
                    WHERE s.sustituto_dni = ? AND (? BETWEEN s.fecha_inicio AND s.fecha_fin)
                """, (dni, fecha_actual)).fetchone()
                if sustitucion_activa:
                    horario_titular = db.execute("SELECT hora_inicio FROM horarios WHERE dni = ? AND dia_semana = ?", (sustitucion_activa['titular_dni'], dia_semana)).fetchone()
                    if horario_titular:
                        horario_efectivo = horario_titular['hora_inicio']

            if not horario_efectivo:
                mensaje = {'texto': '⛔ No tienes un horario asignado para hoy. No se puede registrar asistencia.', 'tipo': 'danger'}
                return render_template('index.html', mensaje=mensaje)

            hora_inicio_programada = datetime.strptime(horario_efectivo, '%H:%M').time()
            tolerancia = timedelta(minutes=5)
            
             
            hora_inicio_dt = datetime.combine(datetime.today(), hora_inicio_programada)
            
            estado = 'Tarde' if ahora > (hora_inicio_dt + tolerancia) else 'A tiempo'
            fecha_hora_completa = ahora.strftime('%Y-%m-%d %H:%M:%S')
            
            db.execute(
                "INSERT INTO asistencias (dni, fecha, hora_registro, estado) VALUES (?, ?, ?, ?)",
                (dni, fecha_hora_completa, hora_actual_str, estado)
            )
            db.commit()
            
            if estado == 'Tarde':
                total_tardanzas = db.execute("SELECT COUNT(*) FROM asistencias WHERE dni = ? AND estado = 'Tarde'", (dni,)).fetchone()[0]
                if total_tardanzas > 0 and total_tardanzas % 3 == 0:
                    db.execute("INSERT INTO advertencias (dni, motivo, fecha) VALUES (?, ?, ?)",(dni, f"Acumulación de {total_tardanzas} tardanzas", fecha_actual))
                    db.commit()
                    mensaje = {'texto': f"🚨 {nombre} llegó tarde. Se generó advertencia por acumulación de tardanzas.", 'tipo': 'danger'}
                else:
                    mensaje = {'texto': f"⚠️ {nombre}, tu ingreso se registró tarde a las {hora_actual_str}.", 'tipo': 'warning'}
            else:
                mensaje = {'texto': f"✅ ¡Bienvenido, {nombre}! Tu ingreso ha sido registrado a las {hora_actual_str}.", 'tipo': 'success'}

    return render_template('index.html', mensaje=mensaje)


@attendance_bp.route('/asistencias', methods=['GET', 'POST'])
@requiere_rol(1, 2)
def asistencias():
     
     
    fecha_filtro = request.form.get('fecha') if request.method=='POST' else None
    db = get_db()
    c = db.cursor()
    
     
    base = """
        SELECT a.id, a.dni,
               d.nombres || ' ' || d.apellido_paterno || ' ' || d.apellido_materno AS nombre,
               a.fecha, a.hora_registro, a.estado,
               COALESCE(cr.nombre_cargo, 'N/A') as nombre_cargo,
               COALESCE(g.nombre_grado, '') as nombre_grado,
               COALESCE(s.nombre_seccion, '') as nombre_seccion
        FROM asistencias a
        JOIN docentes d ON a.dni = d.dni
        LEFT JOIN cargos cr ON d.cargo_id = cr.id_cargo
        LEFT JOIN grados g ON d.grado_id = g.id_grado
        LEFT JOIN secciones s ON d.seccion_id = s.id_seccion
    """
    if fecha_filtro:
        regs = c.execute(base + " WHERE DATE(a.fecha)=? ORDER BY a.fecha DESC", (fecha_filtro,)).fetchall()
    else:
        regs = c.execute(base + " ORDER BY a.fecha DESC").fetchall()

    registros = []
    for r in regs:
         
        grado_str = r['nombre_grado'].replace(" Grado", "°") if r['nombre_grado'] and r['nombre_grado'] != 'N/A' else ''
        seccion_str = f'"{r["nombre_seccion"]}"' if r['nombre_seccion'] and r['nombre_seccion'] != 'N/A' else ''
        grado_seccion = f"{grado_str} {seccion_str}".strip()

        registros.append((
            r['id'],
            r['dni'],
            r['nombre'],
            r['nombre_cargo'],  
            grado_seccion,      
            formatear_fecha(r['fecha']),
            r['hora_registro'] if r['hora_registro'] else '—',
            r['estado']
        ))
        
    return render_template('asistencias.html', registros=registros, fecha_filtro=fecha_filtro)


@attendance_bp.route('/asistencias_semanal')
@requiere_rol(1, 2)
def asistencias_semanal():
    offset = int(request.args.get('semana_offset', 0))
    hoy = datetime.now()
    lunes = (hoy - timedelta(days=hoy.weekday())) + timedelta(weeks=offset)
    semana = [(lunes + timedelta(days=i)).date() for i in range(5)]

    db = get_db()
    
    fechas_semana_str = [dia.strftime('%Y-%m-%d') for dia in semana]
    if fechas_semana_str:
        placeholders = ','.join('?' for _ in fechas_semana_str)
        dias_no_laborables = {row['fecha'] for row in db.execute(f"SELECT fecha FROM fechas_no_laborables WHERE fecha IN ({placeholders})", fechas_semana_str).fetchall()}
    else:
        dias_no_laborables = set()

    docs = db.execute("SELECT dni, nombres || ' ' || apellido_paterno || ' ' || apellido_materno AS nombre FROM docentes ORDER BY apellido_paterno, apellido_materno").fetchall()

    asistencias = {}
    for d_docente in docs:
        dni = d_docente['dni']
        asistencias[dni] = {'nombre': d_docente['nombre'], 'dias': {}, 'atiempo': 0, 'tarde': 0, 'inasist': 0, 'justif': 0}
        
        for dia_obj in semana:
            dia_str = dia_obj.strftime('%Y-%m-%d')
            dia_nombre_bd = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"][dia_obj.weekday()]

             
            if dia_str in dias_no_laborables:
                asistencias[dni]['dias'][dia_obj] = "🔕"
                continue

             
            if db.execute("SELECT 1 FROM permisos_docentes WHERE dni = ? AND (? BETWEEN fecha_inicio AND fecha_fin)", (dni, dia_str)).fetchone():
                asistencias[dni]['dias'][dia_obj] = "🅿"
                asistencias[dni]['justif'] += 1
                continue

             
            deberia_trabajar_hoy = False
            if db.execute("SELECT 1 FROM horarios WHERE dni = ? AND dia_semana = ?", (dni, dia_nombre_bd)).fetchone():
                deberia_trabajar_hoy = True
            else:
                sustitucion_cubre = db.execute("""
                    SELECT 1 FROM sustituciones s
                    JOIN permisos_docentes pd ON s.permiso_id = pd.id
                    JOIN horarios h ON pd.dni = h.dni
                    WHERE s.sustituto_dni = ? AND (? BETWEEN s.fecha_inicio AND s.fecha_fin)
                      AND (? BETWEEN pd.fecha_inicio AND pd.fecha_fin) AND h.dia_semana = ?
                """, (dni, dia_str, dia_str, dia_nombre_bd)).fetchone()
                if sustitucion_cubre:
                    deberia_trabajar_hoy = True

            if not deberia_trabajar_hoy:
                asistencias[dni]['dias'][dia_obj] = "—"
                continue

             
            
             
            reg = db.execute("SELECT id, estado FROM asistencias WHERE dni = ? AND DATE(fecha) = ?", (dni, dia_str)).fetchone()
            
            if reg:
                 
                estado, justif_estado = reg['estado'], None
                if estado in ("Inasistencia", "Tarde"):
                    res_justif = db.execute("SELECT estado FROM justificaciones WHERE asistencia_id = ?", (reg['id'],)).fetchone()
                    if res_justif: justif_estado = res_justif['estado']
                
                if justif_estado == "Aprobada":
                    asistencias[dni]['dias'][dia_obj] = "J✔"; asistencias[dni]['justif'] += 1
                elif justif_estado == "Pendiente":
                    asistencias[dni]['dias'][dia_obj] = "J⧗"
                elif estado == "A tiempo":
                    asistencias[dni]['dias'][dia_obj] = "✔"; asistencias[dni]['atiempo'] += 1
                elif estado == "Tarde":
                    asistencias[dni]['dias'][dia_obj] = "🕒"; asistencias[dni]['tarde'] += 1
                elif estado == "Inasistencia":
                    asistencias[dni]['dias'][dia_obj] = "✗"; asistencias[dni]['inasist'] += 1
                else:
                    asistencias[dni]['dias'][dia_obj] = "?"
            else:  
                 
                hay_registro_general_para_hoy = db.execute(
                    "SELECT 1 FROM asistencias WHERE DATE(fecha) = ? LIMIT 1", (dia_str,)
                ).fetchone()

                if hay_registro_general_para_hoy:
                     
                    asistencias[dni]['dias'][dia_obj] = "✗"
                    asistencias[dni]['inasist'] += 1
                else:
                     
                    asistencias[dni]['dias'][dia_obj] = "—"
    
    total_atiempo = sum(d['atiempo'] for d in asistencias.values())
    total_tarde = sum(d['tarde'] for d in asistencias.values())
    total_justif = sum(d['justif'] for d in asistencias.values())
    total_inasist = sum(d['inasist'] for d in asistencias.values())

    return render_template(
        'asistencias_semanal.html',
        asistencias=asistencias,
        semana=semana,
        semana_offset=offset,
        total_atiempo=total_atiempo,
        total_tarde=total_tarde,
        total_justif=total_justif,
        total_inasist=total_inasist
    )

@attendance_bp.route('/asistencias_data', methods=['POST'])
@requiere_rol(1, 2)
def asistencias_data():
    try:
        db = get_db()
        c = db.cursor()

        start = int(request.form.get('start', 0))
        length = int(request.form.get('length', 10))
        search = request.form.get('search[value]', '')
        order_col = int(request.form.get('order[0][column]', 5))  
        order_dir = request.form.get('order[0][dir]', 'desc')
        fecha = request.form.get('fecha', '')

         
         
         
        columnas = [
            'a.dni', 'nombre', 'nombre_cargo', 'nombre_grado',
            'a.fecha', 'a.hora_registro', 'a.hora_salida', 'a.estado'  
        ]

         
        base = """
            SELECT 
                a.id, a.dni,
                d.nombres || ' ' || d.apellido_paterno || ' ' || d.apellido_materno AS nombre,
                a.fecha, a.hora_registro, a.hora_salida, a.estado, -- <-- Añadida hora_salida
                COALESCE(cr.nombre_cargo, 'N/A') as nombre_cargo,
                COALESCE(g.nombre_grado, '') as nombre_grado,
                COALESCE(s.nombre_seccion, '') as nombre_seccion
            FROM asistencias a
            JOIN docentes d ON a.dni = d.dni
            LEFT JOIN cargos cr ON d.cargo_id = cr.id_cargo
            LEFT JOIN grados g ON d.grado_id = g.id_grado
            LEFT JOIN secciones s ON d.seccion_id = s.id_seccion
        """

        filtros = []
        params = []
        if fecha:
            filtros.append('DATE(a.fecha) = ?')
            params.append(fecha)
        if search:
             
            filtros.append('(d.nombres LIKE ? OR d.apellido_paterno LIKE ? OR d.apellido_materno LIKE ? OR a.dni LIKE ? OR cr.nombre_cargo LIKE ?)')
            search_param = f'%{search}%'
            params.extend([search_param] * 5)

        where = ' WHERE ' + ' AND '.join(filtros) if filtros else ''
        
         
         
         
        order_by_column = columnas[order_col] if order_col < len(columnas) else 'a.fecha'  
        
         
        mapa_orden = {
            "nombre": "d.nombres || ' ' || d.apellido_paterno || ' ' || d.apellido_materno",
            "nombre_cargo": "cr.nombre_cargo",
            "nombre_grado": "g.nombre_grado"
        }
        order_by_expression = mapa_orden.get(order_by_column, order_by_column)
        order = f' ORDER BY {order_by_expression} {order_dir.upper()}'

        limit = ' LIMIT ? OFFSET ?'
        
         
        count_query = f'SELECT COUNT(*) FROM asistencias a JOIN docentes d ON a.dni = d.dni LEFT JOIN cargos cr ON d.cargo_id = cr.id_cargo {where}'
        total_filtered = c.execute(count_query, params).fetchone()[0]
        
         
        params.extend([length, start])
        
        rows = c.execute(base + where + order + limit, params).fetchall()
        data = []

        hoy = datetime.now().date()

        for r in rows:
            res = c.execute("SELECT estado FROM justificaciones WHERE asistencia_id = ?", (r['id'],)).fetchone()
            estado_justificacion = res['estado'] if res else None

             
            if isinstance(r['fecha'], str):
                fecha_asistencia = datetime.strptime(r['fecha'].split(' ')[0], "%Y-%m-%d").date()
            else:  
                fecha_asistencia = r['fecha'].date()

            dias_diferencia = (hoy - fecha_asistencia).days
            puede_justificar = r['estado'] in ["Inasistencia", "Tarde"] and dias_diferencia <= 3 and not estado_justificacion

             
            grado_str = r['nombre_grado'].replace(" Grado", "") if r['nombre_grado'] and r['nombre_grado'] != 'N/A' else ''
            seccion_str = f'"{r["nombre_seccion"]}"' if r['nombre_seccion'] and r['nombre_seccion'] != 'N/A' else ''
            grado_seccion = f"{grado_str} {seccion_str}".strip()

             
             
            data.append([
                r['id'],
                r['dni'],
                r['nombre'],
                r['nombre_cargo'],
                grado_seccion,  
                formatear_fecha(r['fecha']),
                r['hora_registro'] or '—',
                r['hora_salida'] or '—',  
                r['estado'],
                estado_justificacion,
                puede_justificar
            ])

         
        total_sin_filtros_query = 'SELECT COUNT(*) FROM asistencias'
        if fecha:  
             total_sin_filtros_query = f"SELECT COUNT(*) FROM asistencias WHERE DATE(fecha) = '{fecha}'"
        
        total = c.execute(total_sin_filtros_query).fetchone()[0]


        return jsonify({
            'draw': int(request.form.get('draw', 1)),
            'recordsTotal': total,
            'recordsFiltered': total_filtered,
            'data': data
        })

    except Exception as e:
        import traceback
        print("❌ ERROR EN asistencias_data:", e)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/registrar_justificacion', methods=['POST'])
@requiere_rol(1, 2)
def registrar_justificacion():

    EXTENSIONES_PERMITIDAS = {'.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'}

    db = get_db()
    c = db.cursor()

    asistencia_id = request.form.get('asistencia_id')
    motivo = request.form.get('motivo')
    archivo = request.files.get('archivo_justificante')

    if not asistencia_id or not motivo:
        flash("Faltan datos obligatorios", "danger")
        return redirect(url_for('attendance.index'))

     
    c.execute("SELECT 1 FROM justificaciones WHERE asistencia_id = ?", (asistencia_id,))
    if c.fetchone():
        flash("Ya existe una justificación registrada para esta asistencia.", "warning")
        return redirect(url_for('attendance.index'))

    archivo_nombre = None

    if archivo and archivo.filename:
        extension = os.path.splitext(archivo.filename)[1].lower()

        if extension not in EXTENSIONES_PERMITIDAS:
            flash("Archivo no permitido. Solo se aceptan PDF, DOC, DOCX, JPG, PNG.", "danger")
            return redirect(url_for('attendance.index'))

         
        c.execute("""
            SELECT a.fecha, d.nombres, d.apellido_paterno
            FROM asistencias a
            JOIN docentes d ON a.dni = d.dni
            WHERE a.id = ?
        """, (asistencia_id,))
        asistencia = c.fetchone()

        if not asistencia:
            flash("Asistencia no encontrada.", "danger")
            return redirect(url_for('attendance.index'))

         
        fecha_asistencia_raw = asistencia['fecha']
        if ' ' in fecha_asistencia_raw:
            fecha_solo_dia = datetime.strptime(fecha_asistencia_raw, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        else:
            fecha_solo_dia = fecha_asistencia_raw

        fecha_str = fecha_solo_dia.replace('/', '-')
        nombre_docente = asistencia['nombres'].replace(' ', '')
        apellido = asistencia['apellido_paterno'].replace(' ', '')
        nombre_base = f"Justificacion_{nombre_docente}_{apellido}_{fecha_str}"

        archivo_nombre = secure_filename(f"{nombre_base}{extension}")
        
         
        ruta = current_app.config['JUSTIFICACIONES_PATH']
        os.makedirs(ruta, exist_ok=True)

        archivo_path = os.path.join(ruta, archivo_nombre)
        archivo.save(archivo_path)

     
    c.execute("""
        INSERT INTO justificaciones (asistencia_id, motivo, archivo_justificante)
        VALUES (?, ?, ?)
    """, (asistencia_id, motivo, archivo_nombre))
    db.commit()

    flash("Justificación registrada correctamente.", "success")
    return redirect(url_for('attendance.index'))

@attendance_bp.route('/justificaciones/<path:filename>')
@requiere_rol(1, 2)   
def descargar_justificante(filename):
     
    carpeta = current_app.config.get('JUSTIFICACIONES_PATH')
    if not carpeta:
        abort(404)
    try:
        return send_from_directory(carpeta, filename, as_attachment=False)
    except FileNotFoundError:
        abort(404)



@attendance_bp.route('/justificaciones')
def lista_justificaciones():
    db = get_db()
    c = db.cursor()

    c.execute("""
        SELECT j.id, a.fecha, a.hora_registro, a.dni, d.nombres || ' ' || d.apellido_paterno || ' ' || d.apellido_materno AS nombre,
               j.motivo, j.archivo_justificante, j.estado
        FROM justificaciones j
        JOIN asistencias a ON j.asistencia_id = a.id
        JOIN docentes d ON a.dni = d.dni
        ORDER BY a.fecha DESC
    """)
    justificaciones = c.fetchall()

    return render_template('justificaciones.html', justificaciones=justificaciones)
    

@attendance_bp.route('/abrir_justificaciones')
@requiere_rol(1, 2)
def abrir_justificaciones():
    ruta = current_app.config['JUSTIFICACIONES_PATH']
    try:
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer "{ruta}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", ruta])
        else:
            subprocess.Popen(["xdg-open", ruta])
        flash("(OK) Carpeta de justificaciones abierta correctamente.", "success")
    except Exception as e:
        flash(f"(Error) No se pudo abrir la carpeta de justificaciones: {e}", "danger")
    return redirect(request.referrer or url_for('justificaciones.index'))


@attendance_bp.route('/aprobar_justificacion', methods=['POST'])
@requiere_rol(1, 2)
def aprobar_justificacion():
    justificacion_id = request.form.get('justificacion_id')
    if not justificacion_id:
        flash("ID no válido.", "danger")
        return redirect(url_for('attendance.lista_justificaciones'))

    db = get_db()
    c = db.cursor()
    c.execute("UPDATE justificaciones SET estado = 'Aprobada' WHERE id = ?", (justificacion_id,))
    db.commit()
    flash("Justificación aprobada correctamente.", "success")
    return redirect(url_for('attendance.lista_justificaciones'))

def generar_inasistencias_faltantes(fecha_str=None):
    """
    Inserta inasistencias para docentes con horario que no registraron asistencia,
    a menos que tengan un permiso válido en esa fecha.
    """
    from datetime import datetime
    db = get_db()
    
    if not fecha_str:
        fecha_str = datetime.now().strftime('%Y-%m-%d')

    if db.execute("SELECT 1 FROM fechas_no_laborables WHERE fecha = ?", (fecha_str,)).fetchone():
        return 0

    dias_es = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles", "Thursday": "Jueves", "Friday": "Viernes"}
    fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    dia_en_bd = dias_es.get(fecha_dt.strftime('%A'), '')

     
    faltantes_query = """
        SELECT d.dni FROM docentes d JOIN horarios h ON d.dni = h.dni
        WHERE h.dia_semana = ?
          -- Que no tengan una asistencia ya registrada para ese día
          AND NOT EXISTS (
              SELECT 1 FROM asistencias a WHERE a.dni = d.dni AND DATE(a.fecha) = ?
          )
          -- Que no tengan un permiso propio válido para ese día
          AND NOT EXISTS (
              SELECT 1 FROM permisos_docentes pd WHERE pd.dni = d.dni AND (? BETWEEN pd.fecha_inicio AND pd.fecha_fin)
          )
          -- Que no estén sustituyendo a alguien con un permiso válido ese día
          AND NOT EXISTS (
              SELECT 1 FROM sustituciones s
              JOIN permisos_docentes pd_sust ON s.permiso_id = pd_sust.id
              WHERE s.sustituto_dni = d.dni 
                AND (? BETWEEN s.fecha_inicio AND s.fecha_fin)
                AND (? BETWEEN pd_sust.fecha_inicio AND pd_sust.fecha_fin)
          )
        GROUP BY d.dni
    """
    params = (dia_en_bd, fecha_str, fecha_str, fecha_str, fecha_str)
    faltantes = db.execute(faltantes_query, params).fetchall()

    for f in faltantes:
        db.execute("INSERT INTO asistencias (dni, fecha, estado) VALUES (?, ?, 'Inasistencia')", (f['dni'], fecha_str))

    db.commit()
    return len(faltantes)

@attendance_bp.route('/exportar/diario/<fecha_str>')
@requiere_rol(1, 2)
def exportar_reporte_diario(fecha_str):
    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d')

        reportes_dir = current_app.config['REPORTS_PATH']
        os.makedirs(reportes_dir, exist_ok=True)
        nombre_archivo = f"Asistencia_Diaria_{fecha_str}.pdf"
        path_pdf = os.path.join(reportes_dir, nombre_archivo)

        doc = SimpleDocTemplate(path_pdf, pagesize=landscape(A4), topMargin=20, bottomMargin=30, leftMargin=40, rightMargin=40)
        
        story = []
        styles = getSampleStyleSheet()

         
        escudo_path = os.path.join(current_app.root_path, 'static', 'escudo_pe.png')
        minedu_path = os.path.join(current_app.root_path, 'static', 'minedu.PNG')

        if not os.path.exists(escudo_path) or not os.path.exists(minedu_path):
            flash("❌ Faltan los archivos 'escudo_pe.png' o 'minedu.PNG' en la carpeta static.", "danger")
            return redirect(url_for('attendance.asistencias'))

        escudo = Image(escudo_path, width=50, height=50)
        minedu_logo = Image(minedu_path, width=120, height=35)
        
        estilo_texto_central = ParagraphStyle(name='HeaderCenter', parent=styles['Normal'], alignment=TA_CENTER, fontSize=14, leading=12)
        estilo_minedu_texto = ParagraphStyle(name='MineduText', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8)

        texto_central = Paragraph("Institución Educativa Pública N° 82008<br/><b>\"Santa Beatriz de Silva\"</b>", estilo_texto_central)
        minedu_bloque = [minedu_logo, Paragraph("MINISTERIO DE EDUCACIÓN", estilo_minedu_texto)]

        tabla_header_superior_data = [[escudo, texto_central, minedu_bloque]]
        tabla_header_superior = Table(tabla_header_superior_data, colWidths=[60, '*', 130])
        tabla_header_superior.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'), ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ]))
        story.append(tabla_header_superior)
        
         
        linea_triple = Drawing(doc.width, 3)
        linea_triple.add(Line(0, 2.5, doc.width, 2.5, strokeColor=colors.black, strokeWidth=0.5))
        linea_triple.add(Line(0, 1, doc.width, 1, strokeColor=colors.black, strokeWidth=0.5))
        linea_triple.add(Line(0, -0.5, doc.width, -0.5, strokeColor=colors.black, strokeWidth=0.5))
        story.append(linea_triple)
        story.append(Spacer(1, 8))


         
         
        logo_ie_path = os.path.join(current_app.root_path, 'static', 'logo.png')
        logo_caj_path = os.path.join(current_app.root_path, 'static', 'logo_caj.png')

        if not os.path.exists(logo_ie_path) or not os.path.exists(logo_caj_path):
             flash("❌ Faltan los archivos 'logo.png' o 'logo_caj.png' en la carpeta static.", "danger")
             return redirect(url_for('attendance.asistencias'))
        
        logo_ie = Image(logo_ie_path, width=60, height=60)
        logo_caj = Image(logo_caj_path, width=60, height=60)  

        estilo_motto = ParagraphStyle(name='Motto', parent=styles['Normal'], alignment=TA_CENTER, fontSize=14, textColor=colors.HexColor(" 
        estilo_bloque_asistencia = ParagraphStyle(name='AsistenciaTitle', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, leading=14)

        story.append(Paragraph('"Sembrando Bondad y Saber"', estilo_motto))
        story.append(Spacer(1, 8))
        
         
        texto_encabezado_ie = [
            Paragraph("<b>ASISTENCIA DEL PERSONAL DIRECTIVO, DOCENTE Y ADMINISTRATIVO</b>", estilo_bloque_asistencia),
            Paragraph('DE LA I.E.P. Nº 82008 "SANTA BEATRIZ DE SILVA" _NIVEL PRIMARIA_ CAJAMARCA', estilo_bloque_asistencia)
        ]
        
        tabla_encabezado_ie_data = [[logo_caj, texto_encabezado_ie, logo_ie]]
        tabla_encabezado_ie = Table(tabla_encabezado_ie_data, colWidths=[75, '*', 75])
        tabla_encabezado_ie.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),       
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),     
            ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),      
        ]))
        story.append(tabla_encabezado_ie)
        story.append(Spacer(1, 12))
        
         
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except locale.Error:
            locale.setlocale(locale.LC_TIME, 'es')
        
        fecha_formateada = fecha_obj.strftime('%A, %d de %B de %Y').capitalize()
        estilo_fecha = ParagraphStyle(name='Fecha', parent=styles['Normal'], alignment=TA_LEFT)
        story.append(Paragraph(f"<b>FECHA:</b> {fecha_formateada}", estilo_fecha))
        story.append(Spacer(1, 20))

         
        db = get_db()
        registros = db.execute("""
            SELECT d.nombres, d.apellido_paterno, d.apellido_materno, cr.nombre_cargo,
                   COALESCE(g.nombre_grado, '') as nombre_grado, COALESCE(s.nombre_seccion, '') as nombre_seccion,
                   a.hora_registro, a.hora_salida
            FROM asistencias a JOIN docentes d ON a.dni = d.dni
            LEFT JOIN cargos cr ON d.cargo_id = cr.id_cargo
            LEFT JOIN grados g ON d.grado_id = g.id_grado
            LEFT JOIN secciones s ON d.seccion_id = s.id_seccion
            WHERE DATE(a.fecha) = ?
            ORDER BY
                CASE WHEN cr.nombre_cargo = 'Director' THEN 0 ELSE 1 END,
                d.apellido_paterno, d.apellido_materno;
        """, (fecha_str,)).fetchall()

         
        tabla_data = [['N°', 'APELLIDOS Y NOMBRES', 'CARGO', 'GRADO Y SECCIÓN', 'H. ENTRADA', 'H. SALIDA']]
        for i, reg in enumerate(registros):
            nombre_completo = f"{reg['apellido_paterno']} {reg['apellido_materno']}, {reg['nombres']}".title()
            grado_str = reg['nombre_grado'].replace(' Grado', '') if reg['nombre_grado'] else ''
            seccion_str = f'"{reg["nombre_seccion"]}"' if reg["nombre_seccion"] else ''
            grado_seccion = f"{grado_str} {seccion_str}".strip()
            fila = [str(i + 1), nombre_completo, reg['nombre_cargo'], grado_seccion, reg['hora_registro'] or '—', reg['hora_salida'] or '—']
            tabla_data.append(fila)

        ancho_columnas = [40, 300, 130, 110, 80, 80]
        tabla_asistencia = Table(tabla_data, colWidths=ancho_columnas)
        tabla_asistencia.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ]))
        story.append(tabla_asistencia)
        
        doc.build(story)

        flash(f"✅ Reporte PDF diario guardado correctamente en la carpeta de reportes.", "success")
        return redirect(url_for('attendance.asistencias'))

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF diario: {e}")
        import traceback
        traceback.print_exc()
        flash(f"❌ Ocurrió un error inesperado al generar el PDF: {e}", "danger")
        return redirect(url_for('attendance.asistencias'))