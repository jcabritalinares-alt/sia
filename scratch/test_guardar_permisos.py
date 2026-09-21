import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from core.models import PerfilUsuario
from core.views import actualizar_permisos_usuario
from django.contrib.messages.storage.fallback import FallbackStorage

admin = User.objects.filter(is_superuser=True).first()
target_user, _ = User.objects.get_or_create(username='test_toggle_user')
target_user.is_superuser = False
target_user.save()

factory = RequestFactory()

# 1. Admin saves permissions WITH permiso_entregas_editar
post_data_on = {
    'rol': 'Operador Avanzado',
    'permiso_entregas': 'on',
    'permiso_entregas_leer': 'on',
    'permiso_entregas_crear': 'on',
    'permiso_entregas_editar': 'on',
    'permiso_entregas_cambiar_estatus': 'on',
}
req1 = factory.post(f'/usuarios/{target_user.id}/actualizar-permisos/', post_data_on)
req1.user = admin
setattr(req1, 'session', {})
setattr(req1, '_messages', FallbackStorage(req1))

resp1 = actualizar_permisos_usuario(req1, target_user.id)
assert resp1.status_code == 302

target_user.refresh_from_db()
perfil1 = target_user.perfil
assert perfil1.puede_editar_entregas == True, "Failed to enable edit permission!"
print("SUCCESS: Admin can enable 'permiso_entregas_editar' via form!")

# 2. Admin saves permissions WITHOUT permiso_entregas_editar
post_data_off = {
    'rol': 'Operador Basico',
    'permiso_entregas': 'on',
    'permiso_entregas_leer': 'on',
    'permiso_entregas_crear': 'on',
    # Notice: permiso_entregas_editar is omitted (checkbox unchecked)
    'permiso_entregas_cambiar_estatus': 'on',
}
req2 = factory.post(f'/usuarios/{target_user.id}/actualizar-permisos/', post_data_off)
req2.user = admin
setattr(req2, 'session', {})
setattr(req2, '_messages', FallbackStorage(req2))

resp2 = actualizar_permisos_usuario(req2, target_user.id)
assert resp2.status_code == 302

target_user.refresh_from_db()
perfil2 = target_user.perfil
assert perfil2.puede_editar_entregas == False, "Failed to disable edit permission!"
assert perfil2.puede_cambiar_estatus_entregas == True, "cambiar_estatus should remain enabled!"
print("SUCCESS: Admin can disable 'permiso_entregas_editar' via form while keeping other permissions!")

print("ALL PERMISSION FORM TOGGLES WORK PERFECTLY!")
