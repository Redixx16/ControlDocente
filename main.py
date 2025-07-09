import threading
import webview
import traceback
import time
import logging
import sys
import os


from app import app 


if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

log_file = os.path.join(application_path, 'app_desktop.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s'
)



def start_server():
    """Inicia el servidor Flask в este hilo."""
    try:
        print("Iniciando servidor Flask en segundo plano...")
        logging.info("Iniciando servidor Flask en http://127.0.0.1:5000")
        app.run(port=5000, debug=False, use_reloader=False)
    except Exception:
        error_msg = traceback.format_exc()
        print(f"ERROR CRITICO AL INICIAR FLASK. Revisa {log_file}")
        logging.critical("Error fatal al iniciar Flask:\n%s", error_msg)


if __name__ == '__main__':
    logging.info("Iniciando aplicacion de escritorio.")
    
    flask_thread = threading.Thread(target=start_server, daemon=True, name="FlaskThread")
    flask_thread.start()

    time.sleep(2)

    if not flask_thread.is_alive():
        print("El servidor Flask no pudo iniciarse. La aplicacion se cerrara.")
        logging.critical("El hilo del servidor Flask no esta activo. Terminando.")
        time.sleep(5)
        sys.exit(1)

    try:
        print("Abriendo ventana de la aplicacion...")
        logging.info("Creando ventana de WebView.")
        
        webview.create_window(
            "Sistema de Asistencia Docente",
            "http://127.0.0.1:5000",
            width=1920, height=1040, resizable=True
        )
        webview.start(gui='edgechromium', debug=False)

    except Exception:
        error_msg = traceback.format_exc()
        print(f"ERROR CRITICO EN WEBVIEW. Revisa {log_file}")
        logging.critical("Error fatal en WebView:\n%s", error_msg)
        time.sleep(5)
        sys.exit(1)

    print("Aplicacion cerrada.")
    logging.info("Aplicacion cerrada por el usuario.")
    sys.exit(0)