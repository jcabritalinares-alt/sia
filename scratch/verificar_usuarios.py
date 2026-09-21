import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import PerfilUsuario

for u in User.objects.all():
    perfil = getattr(u, 'perfil', None)
    rol = getattr(perfil, 'rol', 'Sin Rol') if perfil else 'Sin Perfil'
    print(f"Usuario: {u.username} | Super: {u.is_superuser} | Rol: {rol}")
    if perfil and perfil.permisos_detalle:
        ent = perfil.permisos_detalle.get('entregas', {})
        print(f"   Detalle entregas: {ent}")
        print(f"   puede_editar_entregas: {perfil.puede_editar_entregas}")
        print(f"   puede_cambiar_estatus_entregas: {perfil.puede_cambiar_estatus_entregas}")
