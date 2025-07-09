from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from datetime import datetime   
from db import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
     
    if session.get('usuario'):
        return redirect(url_for('attendance.index'))

    if request.method == 'POST':
        usuario = request.form['usuario'].strip()
        clave = request.form['clave'].strip()
        error = None

        if not usuario or not clave:
            error = 'Todos los campos son obligatorios'
        else:
            db = get_db()
            user = db.execute(
                "SELECT username, password, rol_id FROM usuarios WHERE username = ?", (usuario,)
            ).fetchone()

            if user is None or not check_password_hash(user['password'], clave):
                error = 'Credenciales incorrectas'

        if error:
            flash(error, 'danger')
        else:
             
            session.clear()
            
             
            session['usuario'] = user['username']
            session['rol_id'] = user['rol_id']
            
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('attendance.index'))

     
    return render_template('login.html', year=datetime.now().year)

@auth_bp.route('/logout')
def logout():
     
     
     
    session.clear()
    
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('auth.login'))