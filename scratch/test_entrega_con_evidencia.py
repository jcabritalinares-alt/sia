import os
import sys
import io

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from entregas.views import registrar_entrega
from entregas.models import BeneficioEntregado
from SIA.models import SIA_producto

def run_test():
    print("=== PROBANDO REGISTRO DE ENTREGA CON EVIDENCIA FOTOGRÁFICA Y BIOMETRÍA ===")
    
    # 1. Usuario admin
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.create_superuser('admin_test', 'admin@test.com', 'admin123')

    # 2. Producto
    prod = SIA_producto.objects.first()
    if not prod:
        prod = SIA_producto.objects.create(codigo="TEST-01", descripcion="Prod Test", cantidad=100)
    elif prod.cantidad < 2:
        prod.cantidad = 50
        prod.save()

    # 3. Imágenes de prueba para evidencia1, evidencia2, evidencia3
    def make_test_img(color):
        buf = io.BytesIO()
        Image.new('RGB', (100, 100), color=color).save(buf, format='JPEG')
        buf.seek(0)
        return SimpleUploadedFile(f"foto_{color}.jpg", buf.read(), content_type="image/jpeg")

    evidencia_file1 = make_test_img('green')
    evidencia_file2 = make_test_img('blue')
    evidencia_file3 = make_test_img('red')

    # 4. POST Request
    factory = RequestFactory()
    data = {
        'cedula': 'V-77665544',
        'nombre_beneficiario': 'BENEFICIARIO TEST FOTO 3 EVIDENCIAS',
        'direccion': 'Sector Centro Calle 1',
        'telefono': '04141234567',
        'codigo_prod': str(prod.id),
        'cantidad_dada': '1',
        'via': 'Atención Directa',
        'status': 'Entregado',
        'fecha': '2026-09-07',
        'firma_data': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        'huella_data': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        'evidencia1': evidencia_file1,
        'evidencia2': evidencia_file2,
        'evidencia3': evidencia_file3,
    }

    request = factory.post('/entregar/', data=data)
    request.user = user

    # Configurar session y messages
    setattr(request, 'session', {})
    setattr(request, '_messages', FallbackStorage(request))

    response = registrar_entrega(request)
    print(f"Status Code retornado: {response.status_code}")
    assert response.status_code in [200, 302], f"Error inesperado: status {response.status_code}"

    # 5. Verificar que se creó la entrega con las 3 evidencias
    entrega = BeneficioEntregado.objects.filter(cedula='V-77665544').order_by('-id').first()
    assert entrega is not None, "Error: la entrega no se guardó en la base de datos"
    print(f"Entrega guardada exitosamente con ID #{entrega.id}!")
    print(f"- URL Evidencia 1: {entrega.url_evidencia_1}")
    print(f"- URL Evidencia 2: {entrega.url_evidencia_2}")
    print(f"- URL Evidencia 3: {entrega.url_evidencia_3}")
    assert entrega.url_evidencia_1, "Error: Evidencia 1 no se guardó"
    assert entrega.url_evidencia_2, "Error: Evidencia 2 no se guardó"
    assert entrega.url_evidencia_3, "Error: Evidencia 3 no se guardó"
    print(f"- Huella Dactilar guardada: {bool(entrega.huella_dactilar)}")
    print(f"- Firma guardada: {bool(entrega.firma_beneficiario)}")

    # Limpieza
    entrega.delete()
    print("=== PRUEBA SUPERADA CON ÉXITO: 3 EVIDENCIAS GUARDADAS CORRECTAMENTE ===")

if __name__ == '__main__':
    run_test()
