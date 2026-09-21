import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
import base64
from io import BytesIO
from PIL import Image, ImageDraw

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from entregas.models import BeneficioEntregado
from SIA.models import SIA_producto
from django.test import RequestFactory
from django.contrib.auth.models import User
from entregas.views import generar_comprobante_pdf, ver_comprobante_entrega_publico

def generar_muestra_huella_base64():
    img = Image.new('RGB', (180, 240), color='white')
    draw = ImageDraw.Draw(img)
    # Draw oval and simulated fingerprint ridges
    draw.ellipse([20, 20, 160, 210], outline=(30, 58, 138), width=3)
    for r in range(30, 80, 6):
        draw.ellipse([90 - r, 110 - int(r*1.2), 90 + r, 110 + int(r*1.2)], outline=(30, 58, 138), width=2)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    b64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_str}"

def test_flujo_biometria():
    print("=== INICIANDO PRUEBAS DE BIOMETRÍA DACTILAR (OPCIÓN A) ===")
    
    # 1. Crear producto de prueba si es necesario
    producto = SIA_producto.objects.first()
    if not producto:
        producto = SIA_producto.objects.create(
            codigo="TEST-BIO-001",
            descripcion="Articulo de Prueba Biometrica",
            cantidad=50,
            almacen="Principal"
        )
    print(f"1. Producto de prueba listo: {producto.descripcion}")

    # 2. Generar huella sintética
    huella_b64 = generar_muestra_huella_base64()
    firma_b64 = generar_muestra_huella_base64()
    print("2. Huella dactilar sintética Base64 generada con éxito.")

    # 3. Guardar entrega con huella dactilar
    entrega = BeneficioEntregado.objects.create(
        producto=producto,
        cedula="V-99887766",
        nombre_beneficiario="CIUDADANO PRUEBA BIOMETRÍA",
        codigo_prod=producto.codigo,
        descripcion_prod=producto.descripcion,
        cantidad_dada=1,
        via="Jornada Móvil Biometría",
        status="Entregado",
        firma_beneficiario=firma_b64,
        huella_dactilar=huella_b64
    )
    print(f"3. Entrega #{entrega.id} guardada en PostgreSQL con huella_dactilar={bool(entrega.huella_dactilar)}.")

    # 4. Verificar recuperación de BD
    entrega_db = BeneficioEntregado.objects.get(id=entrega.id)
    assert entrega_db.huella_dactilar is not None, "Error: huella_dactilar no persistió en PostgreSQL"
    assert "data:image/png;base64," in entrega_db.huella_dactilar, "Error: formato de huella_dactilar inválido"
    print("4. Persistencia en PostgreSQL verificada al 100%.")

    # 5. Probar generación de Comprobante Oficial PDF
    factory = RequestFactory()
    request_pdf = factory.get(f"/comprobante/{entrega.id}/pdf/")
    response_pdf = generar_comprobante_pdf(request_pdf, entrega.id)
    assert response_pdf.status_code == 200, f"Error al generar PDF: status {response_pdf.status_code}"
    assert response_pdf['Content-Type'] == 'application/pdf', "Error: tipo de contenido no es application/pdf"
    assert len(response_pdf.content) > 1000, "Error: PDF generado parece estar vacío"
    print(f"5. Generación de Comprobante Oficial PDF exitosa ({len(response_pdf.content)} bytes generados con xhtml2pdf).")

    # 6. Probar vista pública del Comprobante Digital
    request_pub = factory.get(f"/comprobante/entrega/{entrega.id}/")
    response_pub = ver_comprobante_entrega_publico(request_pub, entrega.id)
    assert response_pub.status_code == 200, f"Error al ver comprobante público: status {response_pub.status_code}"
    contenido_html = response_pub.content.decode('utf-8')
    assert "Huella Dactilar" in contenido_html, "Error: texto Huella Dactilar no encontrado en HTML público"
    assert "Pulgar / Biometría" in contenido_html, "Error: subtítulo Pulgar / Biometría no encontrado en HTML público"
    print("6. Vista pública de comprobante digital validada con sello dactiloscópico.")

    # 7. Limpieza
    entrega.delete()
    print("7. Registro de prueba eliminado satisfactoriamente.")
    print("=== TODAS LAS PRUEBAS DE BIOMETRÍA PASARON EXITOSAMENTE ===")

if __name__ == '__main__':
    test_flujo_biometria()
