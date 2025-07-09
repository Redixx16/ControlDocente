 

import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils.roles import requiere_rol
from datetime import datetime

permiso_bp = Blueprint('permisos', __name__, url_prefix='/permisos')

@permiso_bp.before_request
def require_login():
    if not session.get('usuario'):
        return redirect(url_for('auth.login'))

@permiso_bp.route('/')
@requiere_rol(1, 2)
def lista_permisos():
    db = get_db()
    
     
     
    permisos_query = """
        SELECT p.id, p.dni, p.fecha_inicio, p.fecha_fin, p.motivo, p.observaciones,
               d.nombres || ' ' || d.apellido_paterno || ' ' || d.apellido_materno AS docente,
               CASE
                   WHEN DATE('now', 'localtime') BETWEEN p.fecha_inicio AND p.fecha_fin THEN 'Activo'
                   ELSE 'Finalizado'
               END AS estado_calculado
        FROM permisos_docentes p
        JOIN docentes d ON d.dni = p.dni
        ORDER BY p.fecha_inicio DESC
    """
    permisos = db.execute(permisos_query).fetchall()

     
    docentes_para_permiso = db.execute("""
        SELECT dni, nombres, apellido_paterno, apellido_materno
        FROM docentes WHERE tipo = 'Titular' ORDER BY apellido_paterno, apellido_materno
    """).fetchall()
    
    docentes_sustitutos = db.execute("""
        SELECT dni, nombres, apellido_paterno, apellido_materno
        FROM docentes WHERE tipo = 'Sustituto' ORDER BY apellido_paterno, apellido_materno
    """).fetchall()

     
    permisos_con_sustitutos = []
    for permiso in permisos:
        sustitutos = db.execute("""
            SELECT s.*, d.nombres || ' ' || d.apellido_paterno || ' ' || d.apellido_materno AS nombre
            FROM sustituciones s
            JOIN docentes d ON d.dni = s.sustituto_dni
            WHERE s.permiso_id = ?
        """, (permiso['id'],)).fetchall()
        
        permiso_dict = dict(permiso)
        permiso_dict['sustitutos'] = sustitutos
        permisos_con_sustitutos.append(permiso_dict)

    return render_template(
        'permisos.html',
        permisos=permisos_con_sustitutos,
        docentes_para_permiso=docentes_para_permiso,
        docentes_sustitutos=docentes_sustitutos
    )

@permiso_bp.route('/agregar', methods=['POST'])
@requiere_rol(1, 2)
def agregar_permiso():
    dni = request.form['dni']
    fecha_inicio = request.form['fecha_inicio']
    fecha_fin = request.form.get('fecha_fin')
    motivo = request.form['motivo']
    observaciones = request.form.get('observaciones')

    if not fecha_fin or fecha_fin < fecha_inicio:
        flash("❌ Fechas inválidas. La fecha de fin es obligatoria y no puede ser anterior a la de inicio.", "danger")
        return redirect(url_for('permisos.lista_permisos'))

    db = get_db()
     
    db.execute(
        "INSERT INTO permisos_docentes (dni, fecha_inicio, fecha_fin, motivo, observaciones) VALUES (?, ?, ?, ?, ?)",
        (dni, fecha_inicio, fecha_fin, motivo, observaciones)
    )
    db.commit()
    flash("✅ Permiso registrado exitosamente.", "success")
    return redirect(url_for('permisos.lista_permisos'))

 
 


@permiso_bp.route('/sustituir/<int:permiso_id>', methods=['POST'])
@requiere_rol(1, 2)
def asignar_sustituto(permiso_id):
    sustituto_dni = request.form['sustituto_dni']
    fecha_inicio_sust = request.form['fecha_inicio']
    fecha_fin_sust = request.form.get('fecha_fin')

    db = get_db()

    if not fecha_fin_sust or fecha_fin_sust < fecha_inicio_sust:
        flash("❌ Fechas de sustitución inválidas.", "danger")
        return redirect(url_for('permisos.lista_permisos'))
    
    otras_sustituciones = db.execute(
        "SELECT fecha_inicio, fecha_fin FROM sustituciones WHERE sustituto_dni = ? AND permiso_id != ?",
        (sustituto_dni, permiso_id)
    ).fetchall()

    nueva_sust_inicio = datetime.strptime(fecha_inicio_sust, '%Y-%m-%d').date()
    nueva_sust_fin = datetime.strptime(fecha_fin_sust, '%Y-%m-%d').date()

    for sust in otras_sustituciones:
        existente_inicio = datetime.strptime(sust['fecha_inicio'], '%Y-%m-%d').date()
        existente_fin = datetime.strptime(sust['fecha_fin'], '%Y-%m-%d').date()
        
        if (nueva_sust_inicio <= existente_fin) and (existente_inicio <= nueva_sust_fin):
            flash(f"❌ Conflicto. El sustituto ya está asignado del {existente_inicio.strftime('%d/%m/%y')} al {existente_fin.strftime('%d/%m/%y')}.", "danger")
            return redirect(url_for('permisos.lista_permisos'))

    db.execute(
        "INSERT INTO sustituciones (permiso_id, sustituto_dni, fecha_inicio, fecha_fin) VALUES (?, ?, ?, ?)",
        (permiso_id, sustituto_dni, fecha_inicio_sust, fecha_fin_sust)
    )
    db.commit()
    flash("✅ Sustituto asignado correctamente.", "success")
    return redirect(url_for('permisos.lista_permisos'))