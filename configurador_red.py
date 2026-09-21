import os
import socket
import configparser
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.request

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config_red.ini')

def obtener_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def cargar_configuracion():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        config['RED_LAN'] = {
            'modo': 'servidor',
            'ip_servidor': '127.0.0.1',
            'puerto': '8000'
        }
    return config

def guardar_configuracion(modo, ip, puerto):
    config = configparser.ConfigParser()
    config['RED_LAN'] = {
        'modo': modo,
        'ip_servidor': ip,
        'puerto': puerto
    }
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)

class ConfiguradorRedGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Configuración de Red LAN — SIA Inventario")
        self.root.geometry("520x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#0f172a")

        self.ip_local = obtener_ip_local()
        self.config = cargar_configuracion()
        
        modo_actual = self.config.get('RED_LAN', 'modo', fallback='servidor')
        ip_actual = self.config.get('RED_LAN', 'ip_servidor', fallback=self.ip_local)
        puerto_actual = self.config.get('RED_LAN', 'puerto', fallback='8000')

        # Estilo
        style = ttk.Style()
        style.theme_use('clam')

        # Encabezado
        lbl_titulo = tk.Label(
            root, 
            text="CONFIGURACIÓN DE RED Y MODO DE OPERACIÓN", 
            font=("Segoe UI", 11, "bold"), 
            bg="#0f172a", 
            fg="#3b82f6"
        )
        lbl_titulo.pack(pady=(15, 5))

        lbl_sub = tk.Label(
            root, 
            text=f"IP de este Equipo en la Red: {self.ip_local}", 
            font=("Segoe UI", 9), 
            bg="#0f172a", 
            fg="#94a3b8"
        )
        lbl_sub.pack(pady=(0, 15))

        # Marco Principal
        frame = tk.Frame(root, bg="#1e293b", bd=1, relief="solid")
        frame.pack(padx=20, pady=5, fill="both", expand=True)

        # Selección de Modo
        self.var_modo = tk.StringVar(value=modo_actual)

        rb_servidor = tk.Radiobutton(
            frame, 
            text="🖥️ Modo Servidor Principal (Este equipo almacena los datos y atiende a la red)",
            variable=self.var_modo, 
            value="servidor", 
            command=self.on_modo_change,
            bg="#1e293b", 
            fg="#f8fafc", 
            selectcolor="#0f172a",
            font=("Segoe UI", 9, "bold")
        )
        rb_servidor.pack(anchor="w", padx=15, pady=(15, 5))

        rb_cliente = tk.Radiobutton(
            frame, 
            text="💻 Modo Cliente LAN (Conectar a un Servidor Principal en la red local)",
            variable=self.var_modo, 
            value="cliente", 
            command=self.on_modo_change,
            bg="#1e293b", 
            fg="#f8fafc", 
            selectcolor="#0f172a",
            font=("Segoe UI", 9, "bold")
        )
        rb_cliente.pack(anchor="w", padx=15, pady=5)

        # Campos IP Servidor y Puerto
        frame_fields = tk.Frame(frame, bg="#1e293b")
        frame_fields.pack(padx=15, pady=15, fill="x")

        tk.Label(frame_fields, text="Dirección IP del Servidor:", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
        self.entry_ip = tk.Entry(frame_fields, font=("Segoe UI", 10), width=22)
        self.entry_ip.insert(0, ip_actual)
        self.entry_ip.grid(row=0, column=1, sticky="w", padx=10, pady=5)

        tk.Label(frame_fields, text="Puerto de Servicio:", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
        self.entry_puerto = tk.Entry(frame_fields, font=("Segoe UI", 10), width=10)
        self.entry_puerto.insert(0, puerto_actual)
        self.entry_puerto.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        # Botones inferiores
        frame_btns = tk.Frame(root, bg="#0f172a")
        frame_btns.pack(pady=15)

        btn_test = tk.Button(
            frame_btns, 
            text="🔍 Probar Conexión", 
            command=self.probar_conexion, 
            bg="#334155", 
            fg="white", 
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=5
        )
        btn_test.pack(side="left", padx=5)

        btn_guardar = tk.Button(
            frame_btns, 
            text="💾 Guardar y Aplicar", 
            command=self.guardar, 
            bg="#2563eb", 
            fg="white", 
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=15,
            pady=5
        )
        btn_guardar.pack(side="left", padx=5)

        self.on_modo_change()

    def on_modo_change(self):
        if self.var_modo.get() == "servidor":
            self.entry_ip.delete(0, tk.END)
            self.entry_ip.insert(0, "127.0.0.1")
            self.entry_ip.config(state="disabled")
        else:
            self.entry_ip.config(state="normal")
            if self.entry_ip.get() == "127.0.0.1":
                self.entry_ip.delete(0, tk.END)
                self.entry_ip.insert(0, self.ip_local)

    def probar_conexion(self):
        ip = self.entry_ip.get().strip() if self.var_modo.get() == "cliente" else "127.0.0.1"
        puerto = self.entry_puerto.get().strip()
        url = f"http://{ip}:{puerto}/login/"

        try:
            req = urllib.request.urlopen(url, timeout=3)
            if req.status == 200:
                messagebox.showinfo("Conexión Exitosa", f"✅ Conexión establecida con éxito con el servidor SIA en:\n{url}")
            else:
                messagebox.showwarning("Respuesta Inesperada", f"⚠️ El servidor respondió con código HTTP {req.status}")
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"❌ No se pudo conectar con el servidor SIA en {url}.\nVerifique que el Servidor Principal esté iniciado y que el Firewall no bloquee el puerto {puerto}.\n\nDetalle: {e}")

    def guardar(self):
        modo = self.var_modo.get()
        ip = self.entry_ip.get().strip()
        puerto = self.entry_puerto.get().strip()

        if not puerto.isdigit():
            messagebox.showerror("Error", "El puerto debe ser un valor numérico (ej: 8000).")
            return

        guardar_configuracion(modo, ip, puerto)
        messagebox.showinfo("Guardado", f" Configuración guardada exitosamente.\nModo: {modo.upper()}\nIP Servidor: {ip}:{puerto}")
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfiguradorRedGUI(root)
    root.mainloop()
