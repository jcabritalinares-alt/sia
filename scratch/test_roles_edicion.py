import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from core.models import PerfilUsuario
from entregas.models import BeneficioEntregado
from core.views import registrar_usuario, actualizar_permisos_usuario
from entregas.views import editar_beneficiario_entrega

print("--- 1. Testing Template Rendering ---")
# Ensure registrar_usuario.html renders without errors
usuarios = []
admin_user = User.objects.filter(is_superuser=True).first()
if not admin_user:
    admin_user = User.objects.create_superuser('admin_test_tmp', 'admin@test.com', 'adminpass123')

for u in User.objects.all()[:5]:
    perfil, _ = PerfilUsuario.objects.get_or_create(user=u)
    usuarios.append({
        'id': u.id,
        'username': u.username,
        'is_superuser': u.is_superuser,
        'is_staff': u.is_staff,
        'is_active': u.is_active,
        'rol': perfil.rol,
        'perfil': perfil,
        'date_joined': u.date_joined,
        'total_modulos': perfil.total_modulos_activos,
    })

factory = RequestFactory()
req = factory.get('/usuarios/')
req.user = admin_user

html_usuarios = render_to_string('registrar_usuario.html', {'usuarios': usuarios}, request=req)
assert "✏️ Permitir Editar Beneficiario" in html_usuarios, "Checkbox creation label not found in registrar_usuario.html"
assert "Editor Beneficiarios" in html_usuarios, "Editor Beneficiarios badge not found in registrar_usuario.html"
print("SUCCESS: registrar_usuario.html renders correctly with new permission fields!")

# Ensure historial.html renders without errors
entrega_sample = BeneficioEntregado.objects.first()
if entrega_sample:
    req_hist = factory.get('/historial/')
    
    # User WITHOUT edit permission
    test_user_no_edit, _ = User.objects.get_or_create(username='test_user_no_edit')
    test_user_no_edit.is_superuser = False
    test_user_no_edit.save()
    p_no, _ = PerfilUsuario.objects.get_or_create(user=test_user_no_edit)
    p_no.permisos_detalle = {
        'entregas': {'activo': True, 'leer': True, 'crear': True, 'editar': False, 'cambiar_estatus': False}
    }
    p_no.save()
    
    req_hist.user = test_user_no_edit
    context_no_edit = {
        'entregas': [{
            'id': entrega_sample.id,
            'cedula': entrega_sample.cedula,
            'nombre_beneficiario': entrega_sample.nombre_beneficiario,
            'descripcion_prod': entrega_sample.descripcion_prod,
            'cantidad_dada': entrega_sample.cantidad_dada,
            'status': entrega_sample.status,
            'fecha_legible': '01/01/2026',
        }],
        'status_actual': 'Todos'
    }
    html_no_edit = render_to_string('historial.html', context_no_edit, request=req_hist)
    assert f'modalEditarBeneficiario{entrega_sample.id}' not in html_no_edit, "User without permission saw edit modal in historial!"
    print("SUCCESS: User WITHOUT edit permission cannot see edit button in historial.html!")

    # User WITH edit permission
    test_user_edit, _ = User.objects.get_or_create(username='test_user_edit')
    test_user_edit.is_superuser = False
    test_user_edit.save()
    p_edit, _ = PerfilUsuario.objects.get_or_create(user=test_user_edit)
    p_edit.permisos_detalle = {
        'entregas': {'activo': True, 'leer': True, 'crear': True, 'editar': True, 'cambiar_estatus': True}
    }
    p_edit.save()
    
    req_hist.user = test_user_edit
    html_edit = render_to_string('historial.html', context_no_edit, request=req_hist)
    assert f'modalEditarBeneficiario{entrega_sample.id}' in html_edit, "User with permission did not see edit modal in historial!"
    print("SUCCESS: User WITH edit permission correctly sees edit button and modal in historial.html!")

print("\n--- 2. Testing View Permissions Enforcement ---")
# Attempt edit by unauthorized user
req_post = factory.post(f'/entregas/{entrega_sample.id}/editar-beneficiario/', {
    'cedula': 'V-99999999',
    'nombre_beneficiario': 'Hacker Intruso'
})
req_post.user = test_user_no_edit
from django.contrib.messages.storage.fallback import FallbackStorage
setattr(req_post, 'session', {})
setattr(req_post, '_messages', FallbackStorage(req_post))

resp_unauth = editar_beneficiario_entrega(req_post, entrega_sample.id)
assert resp_unauth.status_code == 302, "Unauthorized user should be redirected!"
entrega_sample.refresh_from_db()
assert entrega_sample.nombre_beneficiario != 'Hacker Intruso', "Unauthorized user was able to modify data!"
print("SUCCESS: View successfully blocked unauthorized edit attempt!")

# Attempt edit by authorized user
req_post_auth = factory.post(f'/entregas/{entrega_sample.id}/editar-beneficiario/', {
    'cedula': entrega_sample.cedula,
    'nombre_beneficiario': 'Beneficiario Editado Valido',
    'telefono': '04141112233',
    'direccion': 'Calle Nueva 123'
})
req_post_auth.user = test_user_edit
setattr(req_post_auth, 'session', {})
setattr(req_post_auth, '_messages', FallbackStorage(req_post_auth))

resp_auth = editar_beneficiario_entrega(req_post_auth, entrega_sample.id)
assert resp_auth.status_code == 302
entrega_sample.refresh_from_db()
assert entrega_sample.nombre_beneficiario == 'Beneficiario Editado Valido', "Authorized user edit failed!"
print("SUCCESS: View allowed authorized user to modify beneficiary information!")

print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
