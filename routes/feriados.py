from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils.roles import requiere_rol

feriados_bp = Blueprint('feriados', __name__, url_prefix='/feriados')

@feriados_bp.before_request
def require_login():
    if not session.get('usuario'):
        return redirect(url_for('auth.login'))

@feriados_bp.route('/')
@requiere_rol(1,2)
def lista_feriados():
    db = get_db()
    feriados = db.execute("SELECT * FROM fechas_no_laborables ORDER BY fecha DESC").fetchall()
    return render_template('feriados.html', feriados=feriados)

@feriados_bp.route('/agregar', methods=['POST'])
@requiere_rol(1,2)
def agregar_feriado():
    fecha = request.form['fecha']
    descripcion = request.form['descripcion']
    tipo = request.form['tipo']

    db = get_db()
    try:
        db.execute(
            "INSERT INTO fechas_no_laborables (fecha, descripcion, tipo) VALUES (?, ?, ?)",
            (fecha, descripcion, tipo)
        )
        db.commit()
        flash('✅ Fecha registrada con éxito.', 'success')
    except Exception as e:
        flash(f'❌ Error: {e}', 'danger')

    return redirect(url_for('feriados.lista_feriados'))

@feriados_bp.route('/eliminar/<fecha>')
@requiere_rol(1,2)
def eliminar_feriado(fecha):
    db = get_db()
    db.execute("DELETE FROM fechas_no_laborables WHERE fecha = ?", (fecha,))
    db.commit()
    flash('🗑️ Fecha eliminada.', 'warning')
    return redirect(url_for('feriados.lista_feriados'))
