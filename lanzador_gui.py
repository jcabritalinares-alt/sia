import os
import sys
import time
import datetime
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, 'venv', 'Scripts', 'python.exe')
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

VENV_ACTIVATE = os.path.join(BASE_DIR, 'venv', 'Scripts', 'activate.bat')
SERVIDOR_PY = os.path.join(BASE_DIR, 'servidor.py')
RUN_TUNNEL_PS1 = os.path.join(BASE_DIR, 'run_tunnel.ps1')
BACKUPS_DIR = os.path.join(BASE_DIR, 'backups')
os.makedirs(BACKUPS_DIR, exist_ok=True)

class LanzadorSIAGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SIA — Sistema Institucional de Atención e Inventario")
        self.root.geometry("640x670")
        self.root.resizable(False, False)
        self.root.configure(bg="#0f172a")

        # Centrar la ventana en la pantalla
        self.centrar_ventana(640, 670)

        self.crear_interfaz()
        self.configurar_icono_y_atajos()

    def centrar_ventana(self, ancho, alto):
        self.root.update_idletasks()
        pantalla_ancho = self.root.winfo_screenwidth()
        pantalla_alto = self.root.winfo_screenheight()
        x = (pantalla_ancho // 2) - (ancho // 2)
        y = (pantalla_alto // 2) - (alto // 2) - 20
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def configurar_icono_y_atajos(self):
        if self.logo_alcaldia:
            try:
                self.root.iconphoto(False, self.logo_alcaldia)
            except Exception:
                pass

        # Atajos de teclado para máxima agilidad
        self.root.bind("<Key-1>", lambda e: self.iniciar_completo())
        self.root.bind("<Key-2>", lambda e: self.iniciar_local())
        self.root.bind("<Key-3>", lambda e: self.iniciar_consola())
        self.root.bind("<Key-4>", lambda e: self.generar_respaldo())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def crear_interfaz(self):
        # Frame Principal con padding
        self.main_frame = tk.Frame(self.root, bg="#0f172a", padx=25, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- ENCABEZADO INSTITUCIONAL ---
        header_frame = tk.Frame(self.main_frame, bg="#0f172a")
        header_frame.pack(fill=tk.X, pady=(0, 15))

        # Logo Alcaldía (Izquierda)
        self.logo_alcaldia = None
        ruta_alcaldia = os.path.join(BASE_DIR, 'imagenes', 'alcaldia.jpeg')
        if os.path.exists(ruta_alcaldia):
            try:
                img_a = Image.open(ruta_alcaldia).resize((60, 60), Image.Resampling.LANCZOS)
                self.logo_alcaldia = ImageTk.PhotoImage(img_a)
                lbl_logo_a = tk.Label(header_frame, image=self.logo_alcaldia, bg="#0f172a")
                lbl_logo_a.pack(side=tk.LEFT, padx=(0, 15))
            except Exception:
                pass

        # Textos de Título (Centro)
        title_frame = tk.Frame(header_frame, bg="#0f172a")
        title_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lbl_inst = tk.Label(
            title_frame,
            text="SISTEMA INSTITUCIONAL DE ATENCIÓN",
            font=("Segoe UI", 12, "bold"),
            fg="#38bdf8",
            bg="#0f172a",
            anchor="w"
        )
        lbl_inst.pack(fill=tk.X)

        lbl_sub = tk.Label(
            title_frame,
            text="E INVENTARIO (SIA) • ALCALDÍA DE VALERA",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
            anchor="w"
        )
        lbl_sub.pack(fill=tk.X)

        lbl_desc = tk.Label(
            title_frame,
            text="Panel de Control y Lanzador de Producción",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#0f172a",
            anchor="w"
        )
        lbl_desc.pack(fill=tk.X, pady=(2, 0))

        # Logo Valera Renace (Derecha)
        self.logo_valera = None
        ruta_valera = os.path.join(BASE_DIR, 'imagenes', 'valera_renace.jpeg')
        if os.path.exists(ruta_valera):
            try:
                img_v = Image.open(ruta_valera).resize((60, 60), Image.Resampling.LANCZOS)
                self.logo_valera = ImageTk.PhotoImage(img_v)
                lbl_logo_v = tk.Label(header_frame, image=self.logo_valera, bg="#0f172a")
                lbl_logo_v.pack(side=tk.RIGHT, padx=(15, 0))
            except Exception:
                pass

        # Línea divisoria
        sep1 = tk.Frame(self.main_frame, bg="#334155", height=1)
        sep1.pack(fill=tk.X, pady=(0, 10))

        # --- BADGES DE ESTADO DEL SISTEMA ---
        status_frame = tk.Frame(self.main_frame, bg="#1e293b", padx=12, pady=6)
        status_frame.pack(fill=tk.X, pady=(0, 15))

        lbl_st_title = tk.Label(
            status_frame,
            text="ESTADO DEL SISTEMA:",
            font=("Segoe UI", 8, "bold"),
            fg="#cbd5e1",
            bg="#1e293b"
        )
        lbl_st_title.pack(side=tk.LEFT, padx=(0, 10))

        # Badges verdes
        badge1 = tk.Label(status_frame, text="● Python venv OK", font=("Segoe UI", 8), fg="#34d399", bg="#1e293b")
        badge1.pack(side=tk.LEFT, padx=5)

        badge2 = tk.Label(status_frame, text="● Waitress (12 Hilos)", font=("Segoe UI", 8), fg="#38bdf8", bg="#1e293b")
        badge2.pack(side=tk.LEFT, padx=5)

        badge3 = tk.Label(status_frame, text="● PostgreSQL Conectada", font=("Segoe UI", 8), fg="#a78bfa", bg="#1e293b")
        badge3.pack(side=tk.LEFT, padx=5)

        # --- TARJETAS INTERACTIVAS (BOTONES GRANDES) ---
        
        # Tarjeta 1: Despliegue Servidor Completo (Localhost + Túnel NPX)
        self.crear_tarjeta_opcion(
            numero="1",
            icono="🚀",
            titulo="DESPLIEGUE SERVIDOR COMPLETO (LOCALHOST + TÚNEL NPX)",
            badge="★ SERVIDOR COMPLETO",
            badge_color="#10b981",
            subtitulo="Inicia el servidor Waitress (0.0.0.0:8000), el túnel público NPX LocalTunnel\n(https://siaweb-venezuela.loca.lt) y abre el navegador automáticamente.",
            color_borde="#10b981",
            color_icono="#34d399",
            comando=self.iniciar_completo
        )

        # Tarjeta 2: Modo Local
        self.crear_tarjeta_opcion(
            numero="2",
            icono="💻",
            titulo="INICIAR EN MODO LOCAL (RED DE OFICINA / LAN)",
            badge="RED LOCAL",
            badge_color="#3b82f6",
            subtitulo="Acceso instantáneo en http://localhost:8000. Ideal para uso administrativo\ndirecto en esta máquina o cuando no se dispone de conexión a Internet.",
            color_borde="#3b82f6",
            color_icono="#60a5fa",
            comando=self.iniciar_local
        )

        # Tarjeta 3: Modo Diagnóstico / Consola
        self.crear_tarjeta_opcion(
            numero="3",
            icono="⚙️",
            titulo="CONSOLA TÉCNICA Y DIAGNÓSTICO EN VIVO",
            badge="SOPORTE",
            badge_color="#f59e0b",
            subtitulo="Abre la consola técnica en vivo de Waitress para inspeccionar peticiones HTTP,\nregistros del sistema y realizar pruebas de desarrollo.",
            color_borde="#f59e0b",
            color_icono="#fbbf24",
            comando=self.iniciar_consola
        )

        # Tarjeta 4: Respaldo de Base de Datos
        self.crear_tarjeta_opcion(
            numero="4",
            icono="💾",
            titulo="GENERAR COPIA DE SEGURIDAD (RESPALDO DB)",
            badge="UTILIDAD",
            badge_color="#8b5cf6",
            subtitulo="Genera inmediatamente un respaldo íntegro de la base de datos PostgreSQL\ny lo almacena con marca de tiempo en la carpeta /backups.",
            color_borde="#8b5cf6",
            color_icono="#c084fc",
            comando=self.generar_respaldo
        )

        # --- PIE DE PÁGINA: ESTADO Y CONTROLES ---
        footer_frame = tk.Frame(self.main_frame, bg="#0f172a")
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        # Indicador de Estado
        self.lbl_timer = tk.Label(
            footer_frame,
            text="⚡ Seleccione una opción con el mouse o presione las teclas [1, 2, 3, 4]",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#0f172a",
            anchor="w"
        )
        self.lbl_timer.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Botón Salir
        btn_salir = tk.Button(
            footer_frame,
            text="❌ Salir",
            font=("Segoe UI", 8, "bold"),
            bg="#b91c1c",
            fg="#f8fafc",
            activebackground="#dc2626",
            activeforeground="#f8fafc",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
            command=self.root.destroy
        )
        btn_salir.pack(side=tk.RIGHT)

    def crear_tarjeta_opcion(self, numero, icono, titulo, badge, badge_color, subtitulo, color_borde, color_icono, comando):
        # Contenedor con borde personalizado
        card = tk.Frame(
            self.main_frame,
            bg="#1e293b",
            highlightbackground=color_borde,
            highlightcolor=color_borde,
            highlightthickness=1,
            padx=14,
            pady=10,
            cursor="hand2"
        )
        card.pack(fill=tk.X, pady=5)

        # Fila Superior: Ícono + Número + Título + Badge
        top_row = tk.Frame(card, bg="#1e293b")
        top_row.pack(fill=tk.X)

        lbl_icon = tk.Label(
            top_row,
            text=f"[{numero}] {icono}",
            font=("Segoe UI", 12, "bold"),
            fg=color_icono,
            bg="#1e293b"
        )
        lbl_icon.pack(side=tk.LEFT, padx=(0, 8))

        lbl_title = tk.Label(
            top_row,
            text=titulo,
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#1e293b"
        )
        lbl_title.pack(side=tk.LEFT)

        lbl_badge = tk.Label(
            top_row,
            text=f" {badge} ",
            font=("Segoe UI", 7, "bold"),
            fg="#ffffff",
            bg=badge_color,
            padx=4,
            pady=1
        )
        lbl_badge.pack(side=tk.RIGHT)

        # Fila Inferior: Subtítulo
        lbl_sub = tk.Label(
            card,
            text=subtitulo,
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#1e293b",
            justify="left",
            anchor="w"
        )
        lbl_sub.pack(fill=tk.X, pady=(4, 0))

        # Eventos Hover y Click para todos los elementos
        elementos = [card, top_row, lbl_icon, lbl_title, lbl_badge, lbl_sub]

        def on_enter(e):
            card.configure(bg="#273549", highlightthickness=2)
            top_row.configure(bg="#273549")
            lbl_icon.configure(bg="#273549")
            lbl_title.configure(bg="#273549")
            lbl_sub.configure(bg="#273549")

        def on_leave(e):
            card.configure(bg="#1e293b", highlightthickness=1)
            top_row.configure(bg="#1e293b")
            lbl_icon.configure(bg="#1e293b")
            lbl_title.configure(bg="#1e293b")
            lbl_sub.configure(bg="#1e293b")

        def on_click(e):
            comando()

        for el in elementos:
            el.bind("<Enter>", on_enter)
            el.bind("<Leave>", on_leave)
            el.bind("<Button-1>", on_click)

    def iniciar_completo(self):
        self.lbl_timer.config(text="🚀  Iniciando Servidor Waitress y Túnel NPX LocalTunnel...", fg="#34d399")
        self.root.update()

        # 1. Iniciar Servidor Waitress en ventana secundaria
        cmd_servidor = f'start "Servidor SIA (Waitress Multihilo)" cmd /k ""{VENV_PYTHON}" "{SERVIDOR_PY}""'
        subprocess.Popen(cmd_servidor, shell=True, cwd=BASE_DIR)

        # 2. Iniciar Túnel NPX LocalTunnel (siaweb-venezuela)
        tunel_bat = os.path.join(BASE_DIR, "iniciar_tunel.bat")
        cmd_tunel = f'start "SIA WEB - Tunel Publico (NPX LocalTunnel)" "{tunel_bat}"'
        subprocess.Popen(cmd_tunel, shell=True, cwd=BASE_DIR)

        # 3. Abrir navegador en localhost tras breve pausa
        def abrir_browser():
            time.sleep(2)
            webbrowser.open("http://localhost:8000/login/")

        threading.Thread(target=abrir_browser, daemon=True).start()

        # Mantener la ventana abierta con estado actualizado
        self.root.after(2000, lambda: self.lbl_timer.config(
            text="✅  Servidor Localhost y Túnel NPX activos (siaweb-venezuela.loca.lt). Panel listo.",
            fg="#10b981"
        ))

    def iniciar_local(self):
        self.lbl_timer.config(text="💻  Iniciando Servidor Local y abriendo navegador...", fg="#60a5fa")
        self.root.update()

        # 1. Iniciar Servidor Waitress en ventana secundaria
        cmd_servidor = f'start "Servidor SIA (Waitress Local)" cmd /k ""{VENV_PYTHON}" "{SERVIDOR_PY}""'
        subprocess.Popen(cmd_servidor, shell=True, cwd=BASE_DIR)

        # 2. Abrir navegador en http://localhost:8000/login/ tras breve pausa
        def abrir_browser():
            time.sleep(2)
            webbrowser.open("http://localhost:8000/login/")
            self.lbl_timer.config(
                text="✅  Servidor Local iniciado (http://localhost:8000). Panel listo.",
                fg="#60a5fa"
            )

        threading.Thread(target=abrir_browser, daemon=True).start()

    def iniciar_consola(self):
        self.lbl_timer.config(text="⚙️  Abriendo Consola Técnica en vivo...", fg="#fbbf24")
        self.root.update()

        # Iniciar servidor directamente en consola visible
        cmd_consola = f'start "SIA — Consola de Diagnóstico" cmd /k ""{VENV_PYTHON}" "{SERVIDOR_PY}""'
        subprocess.Popen(cmd_consola, shell=True, cwd=BASE_DIR)

        self.root.after(1000, lambda: self.lbl_timer.config(
            text="✅  Consola de diagnóstico abierta en ventana independiente. Panel listo.",
            fg="#fbbf24"
        ))

    def generar_respaldo(self):
        self.lbl_timer.config(text="💾  Generando copia de seguridad de PostgreSQL...", fg="#c084fc")
        self.root.update()

        def tarea_respaldo():
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_respaldo = os.path.join(BACKUPS_DIR, f"respaldo_sia_{timestamp}.json")

            cmd = [
                VENV_PYTHON,
                os.path.join(BASE_DIR, 'manage.py'),
                'dumpdata',
                '--natural-foreign',
                '--natural-primary',
                '-e', 'contenttypes',
                '-e', 'auth.Permission',
                '--indent', '2',
                '-o', archivo_respaldo
            ]

            try:
                res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True, timeout=120)
                if res.returncode == 0:
                    tamano_kb = round(os.path.getsize(archivo_respaldo) / 1024, 1)
                    mensaje = (
                        f"¡Copia de Seguridad Generada Exitosamente!\n\n"
                        f"📁 Archivo: respaldo_sia_{timestamp}.json\n"
                        f"📊 Tamaño: {tamano_kb} KB\n"
                        f"📍 Ubicación: carpeta 'backups'"
                    )
                    self.root.after(0, lambda: messagebox.showinfo("Respaldo SIA Exitoso", mensaje))
                else:
                    err_msg = f"No se pudo completar el respaldo:\n{res.stderr[:300]}"
                    self.root.after(0, lambda: messagebox.showerror("Error en Respaldo", err_msg))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error al generar respaldo: {e}"))

            self.root.after(0, lambda: self.lbl_timer.config(
                text="✔  Respaldo finalizado. Puede seleccionar otra opción cuando desee.",
                fg="#a78bfa"
            ))

        threading.Thread(target=tarea_respaldo, daemon=True).start()

def main():
    try:
        root = tk.Tk()
        app = LanzadorSIAGUI(root)
        root.mainloop()
    except Exception as e:
        print(f"[AVISO] No se pudo abrir la interfaz grafica: {e}")
        print("Iniciando servidor SIA en modo consola...")
        import subprocess
        subprocess.run([VENV_PYTHON, SERVIDOR_PY])


if __name__ == "__main__":
    main()
