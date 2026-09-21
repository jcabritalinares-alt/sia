import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django_module = __import__('django')
django_module.setup()

from django.test import Client
from django.contrib.auth.models import User
from beneficiarios.models import Beneficiario
from entregas.models import BeneficioEntregado

print("Iniciando pruebas de verificación...")

# Crear o recuperar superusuario para pruebas
admin_user, _ = User.objects.get_or_create(username='test_admin_verif', defaults={'is_superuser': True, 'is_staff': True})

client = Client()
client.force_login(admin_user)

# 1. Probar ruta de asignar_beneficio
resp_entrega = client.get('/entregar/')
print(f"GET /entregar/ -> Status {resp_entrega.status_code}")
assert resp_entrega.status_code == 200, f"Error en /entregar/: {resp_entrega.status_code}"
assert 'limpiarCamposBeneficiario' in resp_entrega.content.decode('utf-8'), "limpiarCamposBeneficiario no encontrado en el template"
print("OK: /entregar/ contiene limpiarCamposBeneficiario")

# 2. Probar ruta de consulta_beneficiarios (página principal)
resp_beneficiarios = client.get('/beneficiarios/')
print(f"GET /beneficiarios/ -> Status {resp_beneficiarios.status_code}")
assert resp_beneficiarios.status_code == 200, f"Error en /beneficiarios/: {resp_beneficiarios.status_code}"
print("OK: /beneficiarios/ carga exitosamente")

# 3. Crear datos de prueba si no existen
benef_test, _ = Beneficiario.objects.update_or_create(
    cedula='99999999',
    defaults={
        'nombre_apellido': 'CIUDADANO DE PRUEBA VERIFICACION',
        'telefono': '04140000000',
        'direccion': 'Comunidad de Prueba Sector 1'
    }
)

# 4. Probar API de consulta con cédula que existe sin beneficios
resp_api_sin = client.get('/api/beneficiarios/consultar/?cedula=99999999')
print(f"GET /api/beneficiarios/consultar/?cedula=99999999 -> Status {resp_api_sin.status_code}")
data_sin = resp_api_sin.json()
print("Respuesta API (sin beneficios previos):", {
    'existe': data_sin.get('existe'),
    'nombre': data_sin.get('ciudadano', {}).get('nombre_apellido'),
    'tiene_beneficios': data_sin.get('tiene_beneficios'),
    'total_entregas': data_sin.get('total_entregas')
})
assert data_sin['existe'] is True
assert data_sin['tiene_beneficios'] is False
assert data_sin['total_entregas'] == 0
print("OK: API respondió correctamente para ciudadano sin beneficios (tiene_beneficios=False, datos recuperados)")

# 5. Probar consulta web con parámetro GET ?cedula=99999999
resp_get_cedula = client.get('/beneficiarios/?cedula=99999999')
assert resp_get_cedula.status_code == 200
html_content = resp_get_cedula.content.decode('utf-8')
assert 'CIUDADANO DE PRUEBA VERIFICACION' in html_content
assert 'Sin Beneficios Entregados' in html_content
print("OK: Vista /beneficiarios/?cedula=99999999 muestra los datos encontrados y card de sin beneficios asignados")

# 6. Crear un beneficio para probar caso con beneficios
entrega_test = BeneficioEntregado.objects.create(
    cedula='99999999',
    nombre_beneficiario='CIUDADANO DE PRUEBA VERIFICACION',
    descripcion_prod='BOLSA DE ALIMENTOS PRUEBA',
    cantidad_dada=2,
    status='Entregado',
    via='Directa de Prueba'
)

# Probar API ahora con beneficios
resp_api_con = client.get('/api/beneficiarios/consultar/?cedula=99999999')
data_con = resp_api_con.json()
print("Respuesta API (con beneficios):", {
    'existe': data_con.get('existe'),
    'tiene_beneficios': data_con.get('tiene_beneficios'),
    'total_entregas': data_con.get('total_entregas'),
    'primer_producto': data_con.get('entregas', [{}])[0].get('descripcion_prod')
})
assert data_con['tiene_beneficios'] is True
assert data_con['total_entregas'] >= 1
assert data_con['entregas'][0]['descripcion_prod'] == 'BOLSA DE ALIMENTOS PRUEBA'
print("OK: API detecta y devuelve los beneficios correctamente")

# Limpieza de datos de prueba
entrega_test.delete()
benef_test.delete()
admin_user.delete()

print("\nTodas las pruebas de verificación pasaron con 100% de éxito!")
