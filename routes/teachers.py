import sqlite3
from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils.format import normalizar, validar_dni
from utils.roles import requiere_rol
from datetime import datetime, timedelta

teachers_bp = Blueprint('teachers', __name__, url_prefix='/docentes')


CARGO_NOMBRE_DIRECTOR = "Director" 


@teachers_bp.before_request
def require_login():
    if not session.get('usuario'):
        return redirect(url_for('auth.login'))
    
def obtener_id_cargo_director(db):
    """Función auxiliar para obtener el ID del cargo Director."""
    cursor = db.execute("SELECT id_cargo FROM cargos WHERE nombre_cargo = ?", (CARGO_NOMBRE_DIRECTOR,))
    director_cargo_row = cursor.fetchone()
    if director_cargo_row:
        return director_cargo_row['id_cargo']
     
    flash(f"Error de configuración: El cargo '{CARGO_NOMBRE_DIRECTOR}' no fue encontrado en la base de datos.", "danger")
    return None

@teachers_bp.route('/registrar', methods=['GET', 'POST'])
@requiere_rol(1, 2)  
def registrar_docente():
    db = get_db()
    current_user_rol_id = session.get('rol_id')

     
    id_cargo_director = obtener_id_cargo_director(db)
    if id_cargo_director is None and request.method == 'POST':  
        flash("Error crítico de configuración: No se pudo validar el cargo de Director.", "danger")
         
         


    if request.method == 'POST':
        dni = normalizar(request.form['dni'])
        nombres = normalizar(request.form['nombres'])
        paterno = normalizar(request.form['apellido_paterno'])
        materno = normalizar(request.form['apellido_materno'])
        tipo = normalizar(request.form.get('tipo', 'Titular'))
        cargo_id_str = request.form.get('cargo_id')
        grado_id_str = request.form.get('grado_id')
        seccion_id_str = request.form.get('seccion_id')
        
        error = None

        if not validar_dni(dni):
            error = 'El DNI debe tener exactamente 8 dígitos numéricos.'
        elif not nombres or not paterno or not materno or not tipo:
            error = 'Los campos DNI, Nombres, Apellidos y Tipo son obligatorios.'
        elif not cargo_id_str:
            error = 'Debe seleccionar un Cargo para el docente.'
        
        cargo_id = None
        if cargo_id_str:
            try:
                cargo_id = int(cargo_id_str)
            except ValueError:
                error = "El Cargo seleccionado no es válido."

        if error is None and id_cargo_director is not None:  
             
            if cargo_id == id_cargo_director:
                if current_user_rol_id == 2:  
                    error = "No tiene permisos para asignar el cargo de Director."
                else:  
                    cursor = db.execute("SELECT COUNT(*) as count FROM docentes WHERE cargo_id = ?", (id_cargo_director,))
                    conteo_directores = cursor.fetchone()['count']
                    if conteo_directores >= 1:
                        error = "Ya existe un Director asignado en el sistema."
             
            
        if error is None:
            try:
                grado_id = int(grado_id_str) if grado_id_str else None
                seccion_id = int(seccion_id_str) if seccion_id_str else None

                db.execute(
                    """INSERT INTO docentes (dni, nombres, apellido_paterno, apellido_materno, tipo, cargo_id, grado_id, seccion_id) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (dni, nombres, paterno, materno, tipo, cargo_id, grado_id, seccion_id)
                )
                db.commit()
                flash('✅ Docente registrado exitosamente', 'success')
                return redirect(url_for('teachers.lista_docentes'))
            except Exception as e:  
                error = f"Ocurrió un error al guardar: {str(e)}"  
        
        if error:
            flash(error, 'danger')
        
     
    all_cargos_raw = db.execute("SELECT id_cargo, nombre_cargo FROM cargos ORDER BY nombre_cargo").fetchall()
    cargos_para_dropdown = []
    
     
    if id_cargo_director is None:  
        id_cargo_director = obtener_id_cargo_director(db)

    director_ya_existe = False
    if id_cargo_director:
        director_existente_check = db.execute("SELECT 1 FROM docentes WHERE cargo_id = ?", (id_cargo_director,)).fetchone()
        if director_existente_check:
            director_ya_existe = True

    for cargo_db in all_cargos_raw:
        if id_cargo_director and cargo_db['id_cargo'] == id_cargo_director:
             
            if current_user_rol_id == 1:  
                if not director_ya_existe:  
                    cargos_para_dropdown.append(cargo_db)
             
        else:  
            cargos_para_dropdown.append(cargo_db)
            
    grados = db.execute("SELECT id_grado, nombre_grado FROM grados ORDER BY id_grado").fetchall()
    secciones = db.execute("SELECT id_seccion, nombre_seccion FROM secciones ORDER BY nombre_seccion").fetchall()
    docente_form_data = request.form if request.method == 'POST' and error else {}

    return render_template('registro_docente.html', 
                           cargos=cargos_para_dropdown,  
                           grados=grados, 
                           secciones=secciones,
                           docente=docente_form_data,
                           titulo="Registrar Nuevo Docente",
                           accion="registrar")

@teachers_bp.route('/lista')
@requiere_rol(1, 2)
def lista_docentes():
    db = get_db()
    docentes = db.execute("""
        SELECT d.dni, d.nombres, d.apellido_paterno, d.apellido_materno, d.tipo,
               COALESCE(c.nombre_cargo, 'N/A') as nombre_cargo,
               COALESCE(g.nombre_grado, 'N/A') as nombre_grado, -- Mostrar N/A si el ID no se encuentra o es NULL (aunque ahora son NOT NULL)
               COALESCE(s.nombre_seccion, 'N/A') as nombre_seccion
        FROM docentes d
        LEFT JOIN cargos c ON d.cargo_id = c.id_cargo
        LEFT JOIN grados g ON d.grado_id = g.id_grado
        LEFT JOIN secciones s ON d.seccion_id = s.id_seccion
        ORDER BY d.apellido_paterno, d.apellido_materno
    """).fetchall()
    
     
    cargos_list = db.execute("SELECT id_cargo, nombre_cargo FROM cargos ORDER BY nombre_cargo").fetchall()
    grados_list = db.execute("SELECT id_grado, nombre_grado FROM grados ORDER BY id_grado").fetchall()
    secciones_list = db.execute("SELECT id_seccion, nombre_seccion FROM secciones ORDER BY nombre_seccion").fetchall()

    return render_template('lista_docentes.html', 
                           docentes=docentes,
                           cargos=cargos_list,     
                           grados=grados_list,     
                           secciones=secciones_list  
                          )

@teachers_bp.route('/info/<dni>')
@requiere_rol(1, 2)
def info_docente(dni):
    db = get_db()
    docente = db.execute("""
        SELECT d.*, /* Selecciona todos los campos de docentes, incluyendo los IDs */
               COALESCE(c.nombre_cargo, 'N/A') as nombre_cargo,
               COALESCE(g.nombre_grado, 'N/A') as nombre_grado,
               COALESCE(s.nombre_seccion, 'N/A') as nombre_seccion
        FROM docentes d
        LEFT JOIN cargos c ON d.cargo_id = c.id_cargo
        LEFT JOIN grados g ON d.grado_id = g.id_grado
        LEFT JOIN secciones s ON d.seccion_id = s.id_seccion
        WHERE d.dni = ?
    """, (dni,)).fetchone()
    
    if docente:
        return jsonify(dict(docente))
    return jsonify({"error": "Docente no encontrado"}), 404

@teachers_bp.route('/editar/<dni_docente>', methods=['GET', 'POST'])
@requiere_rol(1, 2)  
def editar_docente(dni_docente):
    db = get_db()
    current_user_rol_id = session.get('rol_id')
     
     
     
     
    dni_usuario_actual_logueado = session.get('dni_del_docente_logueado_en_session')  

    id_cargo_director = obtener_id_cargo_director(db)
    
    if request.method == 'POST':
        nombres_edit = normalizar(request.form['nombres'])
        paterno_edit = normalizar(request.form['apellido_paterno'])
        materno_edit = normalizar(request.form['apellido_materno'])
        tipo_edit = normalizar(request.form.get('tipo', 'Titular'))
        cargo_id_str_edit = request.form.get('cargo_id')
        grado_id_str_edit = request.form.get('grado_id')
        seccion_id_str_edit = request.form.get('seccion_id')
        
        error = None
        if not nombres_edit or not paterno_edit or not materno_edit or not tipo_edit:
            error = 'Los campos Nombres, Apellidos y Tipo son obligatorios.'
        elif not cargo_id_str_edit:
            error = 'Debe seleccionar un Cargo para el docente.'

        cargo_id_edit = None
        if cargo_id_str_edit:
            try:
                cargo_id_edit = int(cargo_id_str_edit)
            except ValueError:
                error = "El Cargo seleccionado no es válido."

        if error is None and id_cargo_director is not None:
            docente_original_info = db.execute("SELECT cargo_id FROM docentes WHERE dni = ?", (dni_docente,)).fetchone()
            original_cargo_id = docente_original_info['cargo_id'] if docente_original_info else None

             
             
            if cargo_id_edit == id_cargo_director:
                if current_user_rol_id == 2:  
                     
                     
                    if original_cargo_id != id_cargo_director:
                        error = "No tiene permisos para asignar el cargo de Director."
                elif current_user_rol_id == 1:  
                     
                     
                    cursor = db.execute(
                        "SELECT COUNT(*) as count FROM docentes WHERE cargo_id = ? AND dni != ?", 
                        (id_cargo_director, dni_docente) 
                    )
                    conteo_otros_directores = cursor.fetchone()['count']
                    if conteo_otros_directores >= 1:
                        error = "Ya existe otro Director asignado. No puede asignar este cargo."
            
             
            elif original_cargo_id == id_cargo_director and cargo_id_edit != id_cargo_director:
                 
                if current_user_rol_id == 2:  
                      
                    if dni_docente == dni_usuario_actual_logueado:  
                        error = "No puede cambiar su propio cargo de Director. Esta acción debe ser realizada por un Administrador."
                     
                     
                     
                     
                     
                     
                     
                     
                    elif dni_docente != dni_usuario_actual_logueado :  
                         error = "Solo un Administrador puede cambiar el cargo del Director."

                 
             
            
        if error is None:
            try:
                grado_id_edit = int(grado_id_str_edit) if grado_id_str_edit else None
                seccion_id_edit = int(seccion_id_str_edit) if seccion_id_str_edit else None
                db.execute("""
                    UPDATE docentes SET 
                        nombres=?, apellido_paterno=?, apellido_materno=?, tipo=?,
                        cargo_id=?, grado_id=?, seccion_id=?
                    WHERE dni=?
                """, (
                    nombres_edit, paterno_edit, materno_edit, tipo_edit,
                    cargo_id_edit, grado_id_edit, seccion_id_edit,
                    dni_docente
                ))
                db.commit()
                flash("✅ Docente actualizado exitosamente", "success")
                return redirect(url_for('teachers.lista_docentes'))
            except Exception as e:
                error = f"Ocurrió un error al actualizar: {str(e)}"
        
        if error:
            flash(error, 'danger')
        
        docente_actual = dict(request.form) 
        docente_actual['dni'] = dni_docente 
    else:  
         
        docente_actual_raw = db.execute("SELECT * FROM docentes WHERE dni = ?", (dni_docente,)).fetchone()
        if not docente_actual_raw:
            flash("❌ Docente no encontrado.", "danger"); return redirect(url_for('teachers.lista_docentes'))
        docente_actual = dict(docente_actual_raw)

     
    all_cargos_raw = db.execute("SELECT id_cargo, nombre_cargo FROM cargos ORDER BY nombre_cargo").fetchall()
    cargos_para_dropdown = []
    if id_cargo_director is None: id_cargo_director = obtener_id_cargo_director(db)

    director_existente_info = None
    if id_cargo_director:
        director_existente_info = db.execute("SELECT dni FROM docentes WHERE cargo_id = ? AND dni != ?", 
                                           (id_cargo_director, dni_docente)).fetchone()
    docente_siendo_editado_es_director = (id_cargo_director and docente_actual.get('cargo_id') == id_cargo_director)

    for cargo_db in all_cargos_raw:
        if id_cargo_director and cargo_db['id_cargo'] == id_cargo_director:
            if current_user_rol_id == 1: 
                if docente_siendo_editado_es_director or not director_existente_info:
                    cargos_para_dropdown.append(cargo_db)
            elif current_user_rol_id == 2: 
                if docente_siendo_editado_es_director and dni_docente == dni_usuario_actual_logueado:  
                    cargos_para_dropdown.append(cargo_db)
        else: 
            cargos_para_dropdown.append(cargo_db)
            
    grados = db.execute("SELECT id_grado, nombre_grado FROM grados ORDER BY id_grado").fetchall()
    secciones = db.execute("SELECT id_seccion, nombre_seccion FROM secciones ORDER BY nombre_seccion").fetchall()

    return render_template('registro_docente.html', 
                           docente=docente_actual, 
                           cargos=cargos_para_dropdown, 
                           grados=grados, 
                           secciones=secciones,
                           titulo=f"Editar Docente",
                           accion="editar",
                           dni_actual=dni_docente)

@teachers_bp.route('/eliminar/<dni>')
@requiere_rol(1)
def eliminar_docente(dni):
    db = get_db()
    try:
        db.execute("DELETE FROM docentes WHERE dni=?", (dni,))
        db.commit()
        flash("🗑️ Docente eliminado correctamente.", "success")  
    except sqlite3.IntegrityError:
        flash("❌ No se puede eliminar el docente. Puede tener registros asociados (horarios, asistencias, etc.).", "danger")
    except Exception as e:
        flash(f"❌ Error al eliminar docente: {str(e)}", "danger")
    return redirect(url_for('teachers.lista_docentes'))

@teachers_bp.route('/asistencias/<dni>')
@requiere_rol(1, 2)
def asistencias_docente(dni):
     
     
     
    db = get_db()
    asistencias = db.execute("""
        SELECT a.fecha, a.hora_registro, a.estado,
               j.estado AS estado_justificacion
        FROM asistencias a
        LEFT JOIN justificaciones j ON j.asistencia_id = a.id
        WHERE a.dni = ?
        ORDER BY a.fecha DESC
        LIMIT 10
    """, (dni,)).fetchall()
     
    docente_info = db.execute("""
        SELECT d.nombres, d.apellido_paterno, d.apellido_materno, c.nombre_cargo
        FROM docentes d
        LEFT JOIN cargos c ON d.cargo_id = c.id_cargo
        WHERE d.dni = ?
    """, (dni,)).fetchone()

    return render_template("partials/asistencias_docente.html", 
                           asistencias=asistencias, 
                           docente_info=docente_info)


@teachers_bp.route('/horarios')
@requiere_rol(1, 2)
def ver_horarios():
    db = get_db()
    c = db.cursor()
    docentes_horarios_final = {}
    dias_semana_orden = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]

     
    all_docs_query = """
        SELECT d.dni, d.nombres || ' ' || d.apellido_paterno || ' ' || d.apellido_materno AS nombre, 
               d.tipo, COALESCE(cg.nombre_cargo, 'N/A') AS nombre_cargo
        FROM docentes d
        LEFT JOIN cargos cg ON d.cargo_id = cg.id_cargo
        ORDER BY d.apellido_paterno, d.apellido_materno
    """
    all_docs = c.execute(all_docs_query).fetchall()

    for d_doc in all_docs:
        docentes_horarios_final[d_doc['dni']] = {
            'dni': d_doc['dni'],
            'nombre': d_doc['nombre'],
            'tipo': d_doc['tipo'],
            'nombre_cargo': d_doc['nombre_cargo'],
            'horarios': {dia: None for dia in dias_semana_orden},
            'estado_permiso': None,
            'sustituyendo_a': [],
            'siendo_sustituido_por': []
        }

     
    regular_horarios = c.execute("SELECT dni, dia_semana, hora_inicio, hora_fin FROM horarios").fetchall()
    for h in regular_horarios:
        if h['dni'] in docentes_horarios_final:
            day_name_corrected = h['dia_semana'].capitalize().replace("Miércoles", "Miercoles")
            if day_name_corrected in dias_semana_orden:
                docentes_horarios_final[h['dni']]['horarios'][day_name_corrected] = {
                    'hora_inicio': h['hora_inicio'],
                    'hora_fin': h['hora_fin'],
                    'origen': 'regular'
                }

     
     
    active_permissions_query = """
        SELECT pd.id, pd.dni AS titular_dni, pd.fecha_inicio, 
               COALESCE(pd.fecha_fin, '9999-12-31') AS fecha_fin_coalesced,
               pd.fecha_fin AS fecha_fin_original,
               pd.motivo
        FROM permisos_docentes pd
    """
    active_permissions = c.execute(active_permissions_query).fetchall()
    
    today = datetime.now().date()
    
    for p in active_permissions:
        titular_dni = p['titular_dni']
        permiso_start_str = p['fecha_inicio']
        permiso_end_coalesced_str = p['fecha_fin_coalesced']
        fecha_fin_real_str = p['fecha_fin_original']

        try:
            permiso_start = datetime.strptime(permiso_start_str, '%Y-%m-%d').date()
            permiso_end_for_loop = datetime.strptime(permiso_end_coalesced_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            current_app.logger.error(f"Error de formato de fecha en permiso ID {p['id']}.")
            continue

        if titular_dni in docentes_horarios_final:
            docentes_horarios_final[titular_dni]['estado_permiso'] = {
                'motivo': p['motivo'],
                'desde': permiso_start_str,
                'hasta': fecha_fin_real_str if fecha_fin_real_str else 'Indefinido'
            }
            
            current_date_iter = permiso_start
            display_until_date = min(permiso_end_for_loop, today + timedelta(days=365))  

            while current_date_iter <= display_until_date:
                if not (fecha_fin_real_str is None or current_date_iter <= datetime.strptime(fecha_fin_real_str, '%Y-%m-%d').date()):
                    break  

                day_name_en = current_date_iter.strftime('%A')
                day_name_es_map_local = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles", "Thursday": "Jueves", "Friday": "Viernes"}
                day_name_es = day_name_es_map_local.get(day_name_en)

                if day_name_es and day_name_es in docentes_horarios_final[titular_dni]['horarios']:
                    current_horario_info = docentes_horarios_final[titular_dni]['horarios'][day_name_es]
                    if current_horario_info is None or current_horario_info.get('origen') == 'regular':
                        docentes_horarios_final[titular_dni]['horarios'][day_name_es] = {
                            'hora_inicio': 'Permiso', 
                            'hora_fin': '',      
                            'origen': 'permiso',
                            'motivo_permiso': p['motivo'],
                            'fecha_afectada': current_date_iter.strftime('%Y-%m-%d')
                        }
                current_date_iter += timedelta(days=1)

     
    active_substitutions_query = """
        SELECT s.sustituto_dni, pd.dni AS titular_dni,
               s.fecha_inicio AS sub_start, COALESCE(s.fecha_fin, '9999-12-31') AS sub_end_coalesced, s.fecha_fin AS sub_end_original,
               pd.fecha_inicio AS titular_perm_start, COALESCE(pd.fecha_fin, '9999-12-31') AS titular_perm_end_coalesced, pd.fecha_fin AS titular_perm_end_original,
               d_titular.nombres || ' ' || d_titular.apellido_paterno AS titular_nombre_corto,
               d_sustituto.nombres || ' ' || d_sustituto.apellido_paterno AS sustituto_nombre_corto
        FROM sustituciones s
        JOIN permisos_docentes pd ON s.permiso_id = pd.id
        JOIN docentes d_titular ON pd.dni = d_titular.dni
        JOIN docentes d_sustituto ON s.sustituto_dni = d_sustituto.dni
    """
    active_substitutions = c.execute(active_substitutions_query).fetchall()
    
    dias_en_es_map_local = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles", "Thursday": "Jueves", "Friday": "Viernes"}

    for sub in active_substitutions:
        sustituto_dni = sub['sustituto_dni']
        titular_dni_sub = sub['titular_dni']
        
        try:
            sub_start_date = datetime.strptime(sub['sub_start'], '%Y-%m-%d').date()
            sub_end_date_for_loop = datetime.strptime(sub['sub_end_coalesced'], '%Y-%m-%d').date()
            sub_end_date_real_str = sub['sub_end_original']
            titular_perm_start_date = datetime.strptime(sub['titular_perm_start'], '%Y-%m-%d').date()
            titular_perm_end_real_str = sub['titular_perm_end_original']
        except (ValueError, TypeError):
            current_app.logger.error(f"Error de formato de fecha en sustitución para titular {titular_dni_sub}")
            continue

        if sustituto_dni not in docentes_horarios_final or titular_dni_sub not in docentes_horarios_final:
            continue

        titular_info_str = f"{sub['titular_nombre_corto']} (Permiso: {titular_perm_start_date.strftime('%d/%m')} - {datetime.strptime(titular_perm_end_real_str, '%Y-%m-%d').strftime('%d/%m') if titular_perm_end_real_str else 'Indef.'})"
        sustituto_info_str = f"{sub['sustituto_nombre_corto']}"

        if {'nombre': titular_info_str, 'dni': titular_dni_sub} not in docentes_horarios_final[sustituto_dni]['sustituyendo_a']:
             docentes_horarios_final[sustituto_dni]['sustituyendo_a'].append({'nombre': titular_info_str, 'dni': titular_dni_sub})
        if {'nombre': sustituto_info_str, 'dni': sustituto_dni} not in docentes_horarios_final[titular_dni_sub]['siendo_sustituido_por']:
             docentes_horarios_final[titular_dni_sub]['siendo_sustituido_por'].append({'nombre': sustituto_info_str, 'dni': sustituto_dni})

        titular_regular_horarios_dict = {
            h_reg['dia_semana'].capitalize().replace("Miércoles", "Miercoles"): {
                'hora_inicio': h_reg['hora_inicio'], 'hora_fin': h_reg['hora_fin']
            } for h_reg in c.execute("SELECT dia_semana, hora_inicio, hora_fin FROM horarios WHERE dni = ?", (titular_dni_sub,)).fetchall()
        }
        
        current_day_iter_sub = sub_start_date
        display_until_date_sub = min(sub_end_date_for_loop, today + timedelta(days=365))

        while current_day_iter_sub <= display_until_date_sub:
            is_within_titular_permit = (current_day_iter_sub >= titular_perm_start_date and 
                                       (titular_perm_end_real_str is None or current_day_iter_sub <= datetime.strptime(titular_perm_end_real_str, '%Y-%m-%d').date()))
            is_within_substitution_period = (sub_end_date_real_str is None or current_day_iter_sub <= datetime.strptime(sub_end_date_real_str, '%Y-%m-%d').date())

            if not (is_within_titular_permit and is_within_substitution_period):
                current_day_iter_sub += timedelta(days=1)
                continue

            day_name_en_sub = current_day_iter_sub.strftime('%A')
            day_name_es_sub = dias_en_es_map_local.get(day_name_en_sub)

            if day_name_es_sub and day_name_es_sub in titular_regular_horarios_dict:
                docentes_horarios_final[sustituto_dni]['horarios'][day_name_es_sub] = {
                    'hora_inicio': titular_regular_horarios_dict[day_name_es_sub]['hora_inicio'],
                    'hora_fin': titular_regular_horarios_dict[day_name_es_sub]['hora_fin'],
                    'origen': f"Sust. a {sub['titular_nombre_corto']}",
                    'fecha_aplicada': current_day_iter_sub.strftime('%Y-%m-%d') 
                }
                if docentes_horarios_final[titular_dni_sub]['horarios'].get(day_name_es_sub, {}).get('origen') != 'permiso':
                     docentes_horarios_final[titular_dni_sub]['horarios'][day_name_es_sub] = {
                        'hora_inicio': 'Cubierto por', 
                        'hora_fin': sub['sustituto_nombre_corto'],      
                        'origen': 'siendo_sustituido',
                        'fecha_afectada': current_day_iter_sub.strftime('%Y-%m-%d')
                    }
            current_day_iter_sub += timedelta(days=1)

    return render_template('horario_lista.html', docentes=docentes_horarios_final.values(), dias=dias_semana_orden)


@teachers_bp.route('/horario/<dni>', methods=['GET', 'POST'])
@requiere_rol(1,2)
def gestionar_horario(dni):
    db = get_db()
    
    if request.method == 'POST':
         
        dias = request.form.getlist('dias')
        inicio = request.form.get('hora_inicio')
        fin = request.form.get('hora_fin')

        if dias and inicio and fin:
            try:
                 
                db.execute("DELETE FROM horarios WHERE dni = ?", (dni,))
                
                 
                for dia_raw in dias:
                    dia_normalizado = dia_raw.capitalize().replace("Miércoles", "Miercoles")
                    if dia_normalizado in ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]:
                        db.execute(
                            "INSERT INTO horarios (dni, dia_semana, hora_inicio, hora_fin) VALUES (?, ?, ?, ?)",
                            (dni, dia_normalizado, inicio, fin)
                        )
                db.commit()
                flash("✅ Horario asignado/actualizado correctamente.", "success")
            except sqlite3.Error as e:
                db.rollback()
                flash(f"❌ Error al guardar el horario: {e}", "danger")
        else:
            flash("❌ Faltan datos. Verifica los campos.", "danger")
        
        return redirect(url_for('teachers.gestionar_horario', dni=dni))

     
    docente = db.execute("SELECT dni, nombres, apellido_paterno, apellido_materno FROM docentes WHERE dni = ?", (dni,)).fetchone()
    if not docente:
        flash("❌ Docente no encontrado.", "danger")
        return redirect(url_for('teachers.lista_docentes'))

    horarios_del_docente = db.execute("SELECT id, dia_semana, hora_inicio, hora_fin FROM horarios WHERE dni = ? ORDER BY id", (dni,)).fetchall()
    
     
    horarios_por_dia = {dia: None for dia in ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]}
    for h_actual in horarios_del_docente:
        dia_key = h_actual['dia_semana'].capitalize().replace("Miércoles", "Miercoles")
        if dia_key in horarios_por_dia:
             horarios_por_dia[dia_key] = h_actual

     
     
    return render_template('horario_docente.html', 
                           docente=docente, 
                           horarios=horarios_del_docente,  
                           horarios_por_dia=horarios_por_dia)



@teachers_bp.route('/horario/eliminar/<int:horario_id>/<dni>')
@requiere_rol(1)
def eliminar_horario(horario_id, dni):
 
    db = get_db()
    db.execute("DELETE FROM horarios WHERE id = ?", (horario_id,))
    db.commit()
    flash("🗑️ Horario eliminado.", "warning")  
    return redirect(url_for('teachers.gestionar_horario', dni=dni))