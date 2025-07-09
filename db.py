# db.py

import sqlite3
import os
import sys
from flask import current_app, g
from werkzeug.security import generate_password_hash
from db_seed import seed_initial_data

def resource_path(relative_path):
    """ Devuelve la ruta absoluta para PyInstaller o entorno local. """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_db():
    if 'db' not in g:
        db_path_absolute = current_app.config['DATABASE']
        db_dir = os.path.dirname(db_path_absolute)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        g.db = sqlite3.connect(
            db_path_absolute,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    
    schema_file = resource_path('schema.sql') 
    
    try:
        with open(schema_file, 'r', encoding='utf8') as f:
            db.executescript(f.read())
        print(f"Schema '{schema_file}' ejecutado correctamente.")
    except FileNotFoundError:
        print(f"ERROR CRÍTICO: No se encontró el archivo 'schema.sql' en la ruta: {schema_file}", file=sys.stderr)
        return

    # --- Insertar Roles, Usuarios y Catálogos Base ---
    db.execute("INSERT OR IGNORE INTO roles (id, nombre) VALUES (?, ?)", (1, 'Administrador'))
    db.execute("INSERT OR IGNORE INTO roles (id, nombre) VALUES (?, ?)", (2, 'Director'))

    admin_pw_from_config = current_app.config['ADMIN_PASSWORD'] 
    admin_hash = generate_password_hash(admin_pw_from_config, method='pbkdf2:sha256')
    db.execute(
        "INSERT OR IGNORE INTO usuarios (username, password, rol_id) VALUES (?, ?, ?)",
        ('admin', admin_hash, 1) 
    )

    director_username = 'director'#cambiar
    director_pw_from_config = current_app.config['DIRECTOR_PASSWORD'] 
    director_pw = current_app.config.get('DIRECTOR_PASSWORD', director_pw_from_config)
    director_hash = generate_password_hash(director_pw, method='pbkdf2:sha256')
    db.execute(
        "INSERT OR IGNORE INTO usuarios (username, password, rol_id) VALUES (?, ?, ?)",
        (director_username, director_hash, 2)
    )

    db.execute("INSERT OR IGNORE INTO cargos (id_cargo, nombre_cargo) VALUES (?, ?)", (1, 'Director'))
    db.execute("INSERT OR IGNORE INTO cargos (id_cargo, nombre_cargo) VALUES (?, ?)", (2, 'Prof. De Aula'))
    db.execute("INSERT OR IGNORE INTO cargos (id_cargo, nombre_cargo) VALUES (?, ?)", (3, 'Prof. Educacion Fisica'))
    db.execute("INSERT OR IGNORE INTO cargos (id_cargo, nombre_cargo) VALUES (?, ?)", (4, 'Prof. Aula de Innovación'))
    db.execute("INSERT OR IGNORE INTO cargos (id_cargo, nombre_cargo) VALUES (?, ?)", (5, 'Prof. de Ingles'))

    db.execute("INSERT OR IGNORE INTO grados (id_grado, nombre_grado) VALUES (?, ?)", (1, '1° Grado'))
    db.execute("INSERT OR IGNORE INTO grados (id_grado, nombre_grado) VALUES (?, ?)", (2, '2° Grado'))
    db.execute("INSERT OR IGNORE INTO grados (id_grado, nombre_grado) VALUES (?, ?)", (3, '3° Grado'))
    db.execute("INSERT OR IGNORE INTO grados (id_grado, nombre_grado) VALUES (?, ?)", (4, '4° Grado'))
    db.execute("INSERT OR IGNORE INTO grados (id_grado, nombre_grado) VALUES (?, ?)", (5, '5° Grado'))
    db.execute("INSERT OR IGNORE INTO grados (id_grado, nombre_grado) VALUES (?, ?)", (6, '6° Grado'))
    db.execute("INSERT OR IGNORE INTO grados (id_grado, nombre_grado) VALUES (?, ?)", (99, 'N/A'))

    db.execute("INSERT OR IGNORE INTO secciones (id_seccion, nombre_seccion) VALUES (?, ?)", (1, 'A'))
    db.execute("INSERT OR IGNORE INTO secciones (id_seccion, nombre_seccion) VALUES (?, ?)", (2, 'B'))
    db.execute("INSERT OR IGNORE INTO secciones (id_seccion, nombre_seccion) VALUES (?, ?)", (3, 'C'))
    db.execute("INSERT OR IGNORE INTO secciones (id_seccion, nombre_seccion) VALUES (?, ?)", (99, 'N/A'))
    
    print("Datos base (roles, usuarios, catálogos) insertados/verificados.")

    # --- INICIO DE LA INTEGRACIÓN DE CARGA AUTOMÁTICA ---
    cursor = db.cursor()
    

    cursor.execute("SELECT COUNT(*) FROM docentes")


    docente_count = cursor.fetchone()[0]

    if docente_count == 0:
        seed_initial_data(db)
    else:
        print("[INFO] La base de datos ya contiene docentes. Omitiendo carga de datos iniciales.")

    db.commit()
    print("Base de datos inicializada y lista para usar.")

def init_app(app):
    app.teardown_appcontext(close_db)
    # @app.cli.command('init-db')
    # def init_db_command():
    #     """Clear existing data and create new tables."""
    #     init_db()
    #     click.echo('Initialized the database.')
    # app.cli.add_command(init_db_command)