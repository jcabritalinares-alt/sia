import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from core.models import SolicitudCiudadano
from entregas.models import BeneficioEntregado
from core.views import imprimir_comprobante_solicitud
from entregas.views import sincronizar_estado_solicitud

print("=== INICIANDO PRUEBAS DE DESVINCULACIÓN ===")

# 1. Comprobar datos de prueba existentes
sol = SolicitudCiudadano.objects.get(id=1)
print(f"[INFO] Solicitud #{sol.id} de {sol.nombre_apellido} (C.I.: {sol.cedula}) - Estado: {sol.status}")

entregas_previas = BeneficioEntregado.objects.filter(cedula=sol.cedula)
print(f"[INFO] Entregas registradas para cédula {sol.cedula}: {entregas_previas.count()}")
for e in entregas_previas:
    print(f"       -> Entrega #{e.id} ({e.descripcion_prod}) - Estado: {e.status} - Evidencias: {[x for x in [e.url_evidencia_1, e.url_evidencia_2, getattr(e, 'url_evidencia_3', None)] if x]}")

# 2. Probar renderizado de imprimir_comprobante_solicitud
rf = RequestFactory()
request = rf.get(f'/atencion-ciudadano/{sol.id}/imprimir/')
request.user = User.objects.filter(is_superuser=True).first() or User.objects.first()

response = imprimir_comprobante_solicitud(request, sol.id)
assert response.status_code == 200, f"Error en respuesta: {response.status_code}"

html = response.content.decode('utf-8')

# Validar que NO aparezca el bloque de evidencia fotográfica ni fotos de la entrega #28
assert "Evidencia Fotográfica" not in html, "ERROR: Sigue apareciendo 'Evidencia Fotográfica' en el comprobante de solicitud."
for e in entregas_previas:
    if e.url_evidencia_1:
        assert e.url_evidencia_1 not in html, f"ERROR: La foto {e.url_evidencia_1} aparece en el comprobante de solicitud."
    if e.url_evidencia_2:
        assert e.url_evidencia_2 not in html, f"ERROR: La foto {e.url_evidencia_2} aparece en el comprobante de solicitud."

# Validar que aparezcan los datos correctos de la solicitud
assert str(sol.id) in html, "ERROR: No aparece el número de solicitud"
assert sol.cedula in html, "ERROR: No aparece la cédula del solicitante"
assert sol.nombre_apellido in html, "ERROR: No aparece el nombre del solicitante"
assert sol.status in html, "ERROR: No aparece el estado de la solicitud"
print("[OK] Test 1: Comprobante de solicitud renderizado limpio, sin fotos ni datos de entregas previas.")

# 3. Probar sincronización independiente (entrega no vinculada vs vinculada)
class DummyEntrega:
    def __init__(self, id, cedula, prod, via="Directa"):
        self.id = id
        self.cedula = cedula
        self.descripcion_prod = prod
        self.via = via

# A) Entrega directa para la misma cédula (NO debe alterar la solicitud)
entrega_directa = DummyEntrega(id=999, cedula=sol.cedula, prod="Colchón")
sincronizar_estado_solicitud(entrega_directa, "Entregado", solicitud_id=None)

sol.refresh_from_db()
assert sol.status == "Recibida", f"ERROR: La solicitud cambió de estado a {sol.status} por una entrega no vinculada!"
assert not sol.observaciones_seguimiento or "entrega #999" not in sol.observaciones_seguimiento, "ERROR: Se agregaron notas de una entrega directa a la solicitud social!"
print("[OK] Test 2: Entrega directa no vinculada respetó la solicitud social sin modificarla.")

# B) Entrega explícitamente vinculada (por solicitud_id)
entrega_vinculada = DummyEntrega(id=1000, cedula=sol.cedula, prod="Ayuda médica autorizada", via="Solicitud #1")
sincronizar_estado_solicitud(entrega_vinculada, "Entregado", solicitud_id=sol.id)

sol.refresh_from_db()
assert sol.status == "Entregada", f"ERROR: La solicitud vinculada no actualizó a Entregada (actual: {sol.status})"
print("[OK] Test 3: Entrega explícitamente vinculada sincronizó correctamente el estado a 'Entregada'.")

# Restaurar estado original de Solicitud #1 para dejar la BD limpia
sol.status = "Recibida"
sol.observaciones_seguimiento = None
sol.save()
print("[OK] Estado de Solicitud #1 restaurado a 'Recibida'.")

print("=== TODAS LAS PRUEBAS PASARON EXITOSAMENTE ===")
