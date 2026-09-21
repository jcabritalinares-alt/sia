import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_registroauditoria_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rol', models.CharField(default='Operador Entregas', max_length=50)),
                ('permiso_dashboard', models.BooleanField(default=True)),
                ('permiso_inventario', models.BooleanField(default=True)),
                ('permiso_entregas', models.BooleanField(default=True)),
                ('permiso_atencion_ciudadano', models.BooleanField(default=True)),
                ('permiso_asignaciones_especiales', models.BooleanField(default=True)),
                ('permiso_usuarios', models.BooleanField(default=False)),
                ('permiso_auditoria', models.BooleanField(default=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perfil', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Perfil y Permisos de Usuario',
                'verbose_name_plural': 'Perfiles y Permisos de Usuarios',
            },
        ),
    ]
