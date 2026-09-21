import os
import sys
import django
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from entregas.models import BeneficioEntregado
from SIA.models import SIA_producto
from django.test import RequestFactory
from entregas.views import cambiar_estado, generar_comprobante_pdf
from django.contrib.auth.models import User

def main():
    print("=== TEST FECHA DE ENTREGA ===")
    
    # 1. Verificar existencia de columna en el modelo
    assert hasattr(BeneficioEntregado, 'fecha_entrega'), "El modelo no tiene el campo fecha_entrega"
    print("[OK] Campo fecha_entrega existe en el modelo BeneficioEntregado.")

    # 2. Crear un producto de prueba si no existe
    prod, _ = SIA_producto.objects.get_or_create(
        codigo="TEST-FECHA-01",
        defaults={"descripcion": "Producto Test Fecha", "cantidad": 50}
    )

    # 3. Crear entrega en estado 'Pendiente'
    entrega_pend = BeneficioEntregado.objects.create(
        producto=prod,
        cantidad_dada=1,
        cedula="99999991",
        nombre_beneficiario="Ciudadano Test Pendiente",
        codigo_prod=prod.codigo,
        descripcion_prod=prod.descripcion,
        fecha=date(2026, 9, 1),
        fecha_entrega=None,
        status="Pendiente",
        via="Prueba de Sistema"
    )
    print(f"[OK] Entrega Pendiente #{entrega_pend.id} creada: fecha={entrega_pend.fecha}, fecha_entrega={entrega_pend.fecha_entrega}")
    assert entrega_pend.fecha_entrega is None

    # 4. Probar cambio de estado a 'Entregado' simulando petición POST desde equipo
    rf = RequestFactory()
    user, _ = User.objects.get_or_create(username="admin_test", defaults={"is_superuser": True})
    
    # Simular POST con fecha_entrega tomada del equipo
    req = rf.post(f"/cambiar-estado/{entrega_pend.id}/Entregado/", {"fecha_entrega": "2026-09-07"})
    req.user = user
    from django.contrib.messages.storage.fallback import FallbackStorage
    setattr(req, 'session', {})
    messages = FallbackStorage(req)
    setattr(req, '_messages', messages)

    cambiar_estado(req, entrega_pend.id, "Entregado")

    entrega_pend.refresh_from_db()
    print(f"[OK] Entrega actualizada a '{entrega_pend.status}': fecha_entrega={entrega_pend.fecha_entrega}")
    assert entrega_pend.status == "Entregado"
    assert entrega_pend.fecha_entrega == date(2026, 9, 7)

    # 5. Probar generación del comprobante PDF con fecha_entrega
    req_pdf = rf.get(f"/comprobante/{entrega_pend.id}/pdf/")
    req_pdf.user = user
    resp_pdf = generar_comprobante_pdf(req_pdf, entrega_pend.id)
    assert resp_pdf.status_code == 200
    assert resp_pdf['Content-Type'] == 'application/pdf'
    print(f"[OK] PDF generado exitosamente (Tamaño: {len(resp_pdf.content)} bytes).")

    # Limpieza
    entrega_pend.delete()
    print("=== TODOS LOS TESTS COMPLETADOS SATISFACTORIAMENTE ===")

if __name__ == "__main__":
    main()
