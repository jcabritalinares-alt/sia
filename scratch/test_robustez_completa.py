import os, sys, django, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from SIA.models import SIA_producto
from entregas.models import BeneficioEntregado
from beneficiarios.models import Beneficiario
from core.views import login_view
from core.utils import consultar_cedula_sistemaspnp
from entregas.views import obtener_producto_de_entrega
from django.contrib.messages.storage.fallback import FallbackStorage

print("=" * 60)
print("INICIANDO SUITE DE PRUEBAS DE ROBUSTEZ INTEGRAL")
print("=" * 60)

# ----------------------------------------------------
# 1. PRUEBA: Control de Stock e Imposibilidad de Stock Negativo
# ----------------------------------------------------
print("\n--- 1. Probando Integridad de Stock y CheckConstraint ---")
prod_test, _ = SIA_producto.objects.get_or_create(
    codigo="TEST-ROBUST-01",
    defaults={'descripcion': 'Producto de Prueba Concurrencia', 'cantidad': 5}
)
prod_test.cantidad = 5
prod_test.save()

# Probar select_for_update en transacción
with transaction.atomic():
    locked_prod = SIA_producto.objects.select_for_update().get(id=prod_test.id)
    assert locked_prod.cantidad == 5
    locked_prod.cantidad -= 2
    locked_prod.save()

prod_test.refresh_from_db()
assert prod_test.cantidad == 3, f"Esperado 3, obtenido {prod_test.cantidad}"
print("OK: Bloqueo select_for_update y deduccion atomica funcionando correctamente.")

# Probar que la base de datos rechaza stock negativo
error_lanzado = False
try:
    with transaction.atomic():
        prod_test.cantidad = -10
        prod_test.save()
except (IntegrityError, Exception) as e:
    error_lanzado = True
    print(f"OK: PostgreSQL rechazo exitosamente el stock negativo ({type(e).__name__}).")

assert error_lanzado, "ERROR: La base de datos permitio guardar stock negativo!"

# ----------------------------------------------------
# 2. PRUEBA: Clave Foranea en Entregas
# ----------------------------------------------------
print("\n--- 2. Probando Clave Foranea en BeneficioEntregado ---")
prod_test.refresh_from_db()
entrega_fk = BeneficioEntregado.objects.create(
    producto=prod_test,
    codigo_prod=prod_test.codigo,
    descripcion_prod=prod_test.descripcion,
    cantidad_dada=1,
    cedula="99887766",
    nombre_beneficiario="Beneficiario FK Test",
    status="Pendiente"
)

assert entrega_fk.producto_id == prod_test.id
resuelto = obtener_producto_de_entrega(entrega_fk, for_update=False)
assert resuelto.id == prod_test.id
print(f"OK: Entrega vinculada directamente a ForeignKey {entrega_fk.producto} y resuelta en tiempo O(1).")

# ----------------------------------------------------
# 3. PRUEBA: Proteccion de Fuerza Bruta en Login
# ----------------------------------------------------
print("\n--- 3. Probando Rate-Limiting en Login contra Fuerza Bruta ---")
factory = RequestFactory()
test_ip = "192.168.100.99"
cache.delete(f'login_attempts_{test_ip}')
cache.delete(f'login_lockout_{test_ip}')

for i in range(1, 6):
    req_fail = factory.post('/login/', {'username': 'usuario_inexistente', 'password': 'wrong_password'}, REMOTE_ADDR=test_ip)
    setattr(req_fail, 'session', {})
    setattr(req_fail, '_messages', FallbackStorage(req_fail))
    resp = login_view(req_fail)

# El sexto intento debe ser bloqueado por lockout_key
req_blocked = factory.post('/login/', {'username': 'usuario_inexistente', 'password': 'wrong_password'}, REMOTE_ADDR=test_ip)
setattr(req_blocked, 'session', {})
messages_storage = FallbackStorage(req_blocked)
setattr(req_blocked, '_messages', messages_storage)
resp_blocked = login_view(req_blocked)

msgs = [m.message for m in messages_storage]
assert any("bloqueado" in m.lower() for m in msgs), "No se mostro mensaje de bloqueo por intentos excesivos!"
print("OK: El sistema bloqueo exitosamente la IP tras 5 intentos fallidos!")
cache.delete(f'login_attempts_{test_ip}')
cache.delete(f'login_lockout_{test_ip}')

# ----------------------------------------------------
# 4. PRUEBA: Consulta CNE / PNP con Local-First y Cache
# ----------------------------------------------------
print("\n--- 4. Probando Consulta CNE / PNP Local-First y Cache ---")
ced_test = "77665544"
Beneficiario.objects.update_or_create(
    cedula=ced_test,
    defaults={'nombre_apellido': 'CIUDADANO LOCAL RAPIDO', 'direccion': 'Sector Las Acacias'}
)

t0 = time.time()
res_local = consultar_cedula_sistemaspnp(ced_test)
t_elapsed = (time.time() - t0) * 1000 # milisegundos

assert res_local is not None
assert res_local['nombre_completo'] == 'Ciudadano Local Rapido'
assert res_local.get('origen') == 'local'
print(f"OK: Consulta local resuelta en {t_elapsed:.2f} ms sin realizar ninguna peticion externa a internet!")

# ----------------------------------------------------
# Limpieza de datos de prueba
# ----------------------------------------------------
entrega_fk.delete()
prod_test.delete()
Beneficiario.objects.filter(cedula=ced_test).delete()

print("\n" + "=" * 60)
print("¡TODAS LAS PRUEBAS DE ROBUSTEZ PASARON AL 100% EXITOSAMENTE!")
print("=" * 60)
