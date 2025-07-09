import webbrowser
import threading
import logging
from app import app

logging.basicConfig(filename="error.log", level=logging.DEBUG)

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == "__main__":
    try:
        threading.Timer(1.0, open_browser).start()
        app.run()
    except Exception as e:
        logging.exception("Error al ejecutar la app:")
