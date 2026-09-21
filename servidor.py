import sys
from waitress import serve
from core.wsgi import application

print("=" * 65)
print("  SISTEMA INSTITUCIONAL DE ATENCIÓN E INVENTARIO (SIA)")
print("  Servidor de Producción Multihilo Activo (Waitress WSGI)")
print("  - Concurrencia: 12 hilos de procesamiento simultáneo")
print("  - Dirección Local:  http://localhost:8000")
print("  - Dirección de Red: http://0.0.0.0:8000")
print("  - Soporte Estáticos: WhiteNoise con Compresión GZIP activa")
print("=" * 65)
sys.stdout.flush()

try:
    serve(
        application,
        host='0.0.0.0',
        port=8000,
        threads=12,
        connection_limit=200,
        channel_timeout=60
    )
except OSError as e:
    if "10048" in str(e) or "already in use" in str(e).lower() or "address" in str(e).lower():
        print("\n[AVISO] El puerto 8000 ya se encuentra ocupado por otra instancia activa del servidor SIA.")
        print("El sistema ya está funcionando y listo en http://localhost:8000")
        sys.stdout.flush()
    else:
        raise

