import os
import sys
import time
import socket
import subprocess
import configparser
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config_red.ini')

def cargar_configuracion():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        modo = config.get('RED_LAN', 'modo', fallback='servidor')
        ip = config.get('RED_LAN', 'ip_servidor', fallback='127.0.0.1')
        puerto = config.get('RED_LAN', 'puerto', fallback='8000')
    else:
        modo = 'servidor'
        ip = '127.0.0.1'
        puerto = '8000'
    return modo, ip, puerto

def puerto_abierto(ip, puerto):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((ip, int(puerto)))
        s.close()
        return True
    except Exception:
        return False

def iniciar_servidor_waitress(python_bin):
    servidor_script = os.path.join(BASE_DIR, 'servidor.py')
    print("Iniciando servidor de producción Waitress en puerto 8000...")
    subprocess.Popen(
        [python_bin, servidor_script],
        cwd=BASE_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )

def main():
    modo, ip, puerto = cargar_configuracion()
    
    # Determinar el ejecutable de Python del entorno virtual
    venv_python = os.path.join(BASE_DIR, 'venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    target_ip = "127.0.0.1" if modo == "servidor" else ip
    url = f"http://{target_ip}:{puerto}/login/"

    if modo == "servidor":
        if not puerto_abierto("127.0.0.1", puerto):
            iniciar_servidor_waitress(venv_python)
            # Esperar a que el servidor levante
            for _ in range(15):
                if puerto_abierto("127.0.0.1", puerto):
                    break
                time.sleep(0.5)

    print(f"Abriendo aplicación de escritorio conectada a: {url}")
    
    # Lanzar aplicación en modo ventana nativa independiente de Windows (sin barra de navegador)
    cmd_edge = [
        "msedge",
        f"--app={url}",
        "--window-size=1366,850",
        "--name=SIA Inventario"
    ]

    try:
        subprocess.run(cmd_edge)
    except FileNotFoundError:
        # Fallback a Chrome o navegador por defecto si Edge no estuviese disponible
        cmd_chrome = [
            "chrome",
            f"--app={url}",
            "--window-size=1366,850"
        ]
        try:
            subprocess.run(cmd_chrome)
        except FileNotFoundError:
            import webbrowser
            webbrowser.open(url)

if __name__ == "__main__":
    main()
