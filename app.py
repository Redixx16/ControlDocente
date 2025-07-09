import os
import sys
import platform
import subprocess
from flask import Flask, request, flash, redirect, url_for, current_app, session
from dotenv import load_dotenv

# panel de admin
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from models import db  #instancia db de models.py

# módulos
from db import init_app as init_db_app 
from routes.auth import auth_bp
from routes.teachers import teachers_bp
from routes.attendance import attendance_bp
from routes.reports import reports_bp
from routes.feriados import feriados_bp
from routes.permiso import permiso_bp
from utils.format import formatear_fecha, formatear_hora, obtener_inicial_dia
from config import Config

# variables de entorno
load_dotenv()

# --- PANEL DE ADMINISTRACIÓN  ---
# verifica si el usuario es administrador 
class AdminSeguroView(ModelView):
    def is_accessible(self):
        # El rol 1 es el administrador
        return 'rol_id' in session and session['rol_id'] == 1

    def inaccessible_callback(self, name, **kwargs):
        flash("No tienes permiso para acceder a esta área.", "danger")
        return redirect(url_for('auth.login'))

admin = Admin(name='Panel de Control', template_mode='bootstrap4', base_template='admin/base_admin.html')

def create_app():
    """
    Función para crear y configurar la aplicación Flask (Application Factory).
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- RUTAS PERSISTENTES ---
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    REPORTS_PATH_ABSOLUTE = os.path.join(application_path, 'reportes')
    JUSTIFICACIONES_PATH_ABSOLUTE = os.path.join(application_path, 'justificaciones')
    DATABASE_PATH_ABSOLUTE = os.path.join(application_path, 'database', 'db.sqlite')
    
    # --- CONFIGURACIÓN DE LA APP ---
    app.config['DATABASE'] = DATABASE_PATH_ABSOLUTE
    app.config['REPORTS_PATH'] = REPORTS_PATH_ABSOLUTE
    app.config['JUSTIFICACIONES_PATH'] = JUSTIFICACIONES_PATH_ABSOLUTE
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DATABASE_PATH_ABSOLUTE}"
    app.secret_key = app.config['SECRET_KEY']
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    
    # crear carpetas al inicio
    os.makedirs(REPORTS_PATH_ABSOLUTE, exist_ok=True)
    os.makedirs(JUSTIFICACIONES_PATH_ABSOLUTE, exist_ok=True)
    os.makedirs(os.path.dirname(DATABASE_PATH_ABSOLUTE), exist_ok=True)

    # --- INICIALIZACIÓN DE EXTENSIONES Y BASE DE DATOS ---
    db_exists = os.path.exists(DATABASE_PATH_ABSOLUTE)

    # Inicializamos las extensiones de Flask
    db.init_app(app)  # SQLAlchemy
    admin.init_app(app) # Flask-Admin
    init_db_app(app)

    with app.app_context():
        if not db_exists:
            print("LA BASE DE DATOS NO EXISTE. CREANDO TABLAS Y CARGANDO DATOS INICIALES...")

            from db import init_db
            init_db()
            print("BASE DE DATOS INICIALIZADA CORRECTAMENTE.")
        else:
            print("La base de datos ya existe. Omitiendo inicialización.")

    # --- AÑADIR VISTAS AL PANEL DE ADMIN ---
    from models import (
        Usuario, Rol, Docente, Cargo, Grado, Seccion, Horario, Asistencia, 
        Justificacion, Advertencia, FechaNoLaborable, PermisoDocente, Sustitucion
    )
    
    admin.add_view(AdminSeguroView(Usuario, db.session, category="Gestión de Usuarios", name="Usuarios", endpoint="admin_usuarios"))
    admin.add_view(AdminSeguroView(Rol, db.session, category="Gestión de Usuarios", name="Roles"))
    
    admin.add_view(AdminSeguroView(Docente, db.session, category="Personal Docente", name="Docentes"))
    admin.add_view(AdminSeguroView(Cargo, db.session, category="Personal Docente", name="Cargos"))
    admin.add_view(AdminSeguroView(Grado, db.session, category="Personal Docente", name="Grados"))
    admin.add_view(AdminSeguroView(Seccion, db.session, category="Personal Docente", name="Secciones"))

    admin.add_view(AdminSeguroView(Asistencia, db.session, category="Control de Asistencia", name="Asistencias"))
    admin.add_view(AdminSeguroView(Justificacion, db.session, category="Control de Asistencia", name="Justificaciones"))
    admin.add_view(AdminSeguroView(Advertencia, db.session, category="Control de Asistencia", name="Advertencias"))
    admin.add_view(AdminSeguroView(Horario, db.session, category="Control de Asistencia", name="Horarios"))

    admin.add_view(AdminSeguroView(PermisoDocente, db.session, category="Permisos y Faltas", name="Permisos"))
    admin.add_view(AdminSeguroView(Sustitucion, db.session, category="Permisos y Faltas", name="Sustituciones"))
    admin.add_view(AdminSeguroView(FechaNoLaborable, db.session, category="Permisos y Faltas", name="Días no Laborables"))

    with app.app_context():
        # db.create_all()
        pass

    # Registrar filtros de Jinja
    app.jinja_env.filters['formatear_fecha'] = formatear_fecha
    app.jinja_env.filters['formatear_hora'] = formatear_hora
    app.jinja_env.filters['obtener_inicial_dia'] = obtener_inicial_dia

    # --- REGISTRO DE RUTAS (BLUEPRINTS) ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(teachers_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp, url_prefix='/reportes')
    app.register_blueprint(feriados_bp)
    app.register_blueprint(permiso_bp)

    # --- RUTAS ESPECIALES ---
    @app.errorhandler(413)
    def archivo_muy_grande(e):
        flash("(Error) El archivo es demasiado grande (máx. 5MB)", "danger")
        return redirect(request.referrer or url_for('attendance.index'))

    @app.route('/abrir_reportes')
    def abrir_reportes():
        ruta = current_app.config['REPORTS_PATH']
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{ruta}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", ruta])
            else:
                subprocess.Popen(["xdg-open", ruta])
            flash("(OK) Carpeta de reportes abierta correctamente.", "success")
        except Exception as e:
            flash(f"(Error) No se pudo abrir la carpeta de reportes: {e}", "danger")

        return redirect(request.referrer or url_for('reports.reporte_mensual'))
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)