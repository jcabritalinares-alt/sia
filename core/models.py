from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from SIA.models import SIA_producto

class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.TextField()  # Descripción de lo que hizo
    modulo = models.CharField(max_length=100, blank=True, null=True, db_index=True)  # Ej: 'Entregas', 'Inventario'
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-timestamp']  # <--- Corregido a timestamp

    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.usuario} - {self.accion}"  # <--- Corregido a timestamp

class AsignacionEspecial(models.Model):
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    nombre_receptor = models.CharField(max_length=255)
    departamento_o_cargo = models.CharField(max_length=255, blank=True, null=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

class DetalleAsignacionEspecial(models.Model):
    asignacion = models.ForeignKey(AsignacionEspecial, related_name='detalles', on_delete=models.CASCADE)
    descripcion_prod = models.CharField(max_length=255)
    cantidad = models.PositiveIntegerField()

class SolicitudCiudadano(models.Model):
    TIPO_CHOICES = [
        ('Ayuda Médica', 'Ayuda Médica'),
        ('Enseres / Ayuda Social', 'Enseres / Ayuda Social'),
        ('Donación de Medicamentos', 'Donación de Medicamentos'),
        ('Soporte Técnico / Tránsito', 'Soporte Técnico / Tránsito'),
        ('Asesoría Jurídica', 'Asesoría Jurídica'),
        ('Otro', 'Otro'),
    ]

    PRIORIDAD_CHOICES = [
        ('Alta', 'Alta'),
        ('Media', 'Media'),
        ('Baja', 'Baja'),
    ]

    STATUS_CHOICES = [
        ('Recibida', 'Recibida'),
        ('En Proceso', 'En Proceso'),
        ('Aprobada', 'Aprobada'),
        ('Entregada', 'Entregada'),
        ('Rechazada', 'Rechazada'),
    ]

    cedula = models.CharField(max_length=20, db_index=True)
    nombre_apellido = models.CharField(max_length=255)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    tipo_solicitud = models.CharField(max_length=100, choices=TIPO_CHOICES, default='Enseres / Ayuda Social', db_index=True)
    descripcion_solicitud = models.TextField()
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default='Media', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Recibida', db_index=True)
    fecha_solicitud = models.DateTimeField(auto_now_add=True, db_index=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    observaciones_seguimiento = models.TextField(blank=True, null=True)
    entrega = models.ForeignKey('entregas.BeneficioEntregado', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_asociadas', verbose_name="Beneficio Entregado Asociado")
    fecha_entrega = models.DateField(null=True, blank=True, verbose_name="Fecha de Entrega")
    url_evidencia_1 = models.URLField(max_length=500, blank=True, null=True, verbose_name="Evidencia 1")
    url_evidencia_2 = models.URLField(max_length=500, blank=True, null=True, verbose_name="Evidencia 2")
    url_evidencia_3 = models.URLField(max_length=500, blank=True, null=True, verbose_name="Evidencia 3")

    class Meta:
        verbose_name = 'Solicitud de Atención al Ciudadano'
        verbose_name_plural = 'Solicitudes de Atención al Ciudadano'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"Solicitud #{self.id} - {self.nombre_apellido} ({self.tipo_solicitud})"

    @property
    def foto_1(self):
        if self.url_evidencia_1:
            return self.url_evidencia_1
        if self.entrega_id and self.entrega:
            return getattr(self.entrega, 'url_evidencia_1', None)
        return None

    @property
    def foto_2(self):
        if self.url_evidencia_2:
            return self.url_evidencia_2
        if self.entrega_id and self.entrega:
            return getattr(self.entrega, 'url_evidencia_2', None)
        return None

    @property
    def foto_3(self):
        if self.url_evidencia_3:
            return self.url_evidencia_3
        if self.entrega_id and self.entrega:
            return getattr(self.entrega, 'url_evidencia_3', None)
        return None

    @property
    def tiene_fotos(self):
        return bool(self.foto_1 or self.foto_2 or self.foto_3)

class PerfilUsuario(models.Model):
    MODULOS_SISTEMA = [
        ('dashboard', 'Dashboard e Indicadores'),
        ('estadisticas', 'Estadísticas e Inteligencia Social'),
        ('inventario', 'Inventario y Almacén'),
        ('entradas', 'Recepción de Entradas'),
        ('atencion_ciudadano', 'Atención al Ciudadano'),
        ('entregas', 'Entregas de Beneficios'),
        ('asignaciones_especiales', 'Asignaciones Especiales'),
        ('usuarios', 'Gestión de Usuarios y Permisos'),
        ('auditoria', 'Auditoría del Sistema'),
        ('respaldos', 'Respaldos de Base de Datos'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol = models.CharField(max_length=100, default='Personalizado')
    
    # Permisos Granulares por Módulo (columnas booleanas en BD)
    permiso_dashboard = models.BooleanField(default=True)
    permiso_inventario = models.BooleanField(default=True)
    permiso_entregas = models.BooleanField(default=True)
    permiso_atencion_ciudadano = models.BooleanField(default=True)
    permiso_asignaciones_especiales = models.BooleanField(default=True)
    permiso_usuarios = models.BooleanField(default=False)
    permiso_auditoria = models.BooleanField(default=False)

    # Detalle Granular de Acciones (Leer, Crear, Editar, Eliminar, Imprimir por Módulo)
    permisos_detalle = models.JSONField(default=dict, blank=True, null=True)

    class Meta:
        verbose_name = 'Perfil y Permisos de Usuario'
        verbose_name_plural = 'Perfiles y Permisos de Usuarios'

    def __str__(self):
        return f"Perfil de {self.user.username} ({self.rol})"

    def tiene_permiso(self, modulo, accion='leer'):
        """
        Determina de forma manual si el usuario puede acceder a un módulo y acción.
        El superusuario de Django tiene acceso maestro incondicional.
        Para los demás usuarios, se respeta estrictamente la configuración manual.
        """
        if self.user.is_superuser:
            return True
        if self.permisos_detalle and isinstance(self.permisos_detalle, dict) and modulo in self.permisos_detalle:
            mod_info = self.permisos_detalle.get(modulo, {})
            if isinstance(mod_info, bool):
                return mod_info
            if not mod_info.get('activo', False):
                return False
            if accion == 'leer':
                return mod_info.get('leer', True)
            return bool(mod_info.get(accion, False))
        columnas_db = (
            'dashboard', 'inventario', 'entregas', 'atencion_ciudadano',
            'asignaciones_especiales', 'usuarios', 'auditoria'
        )
        if modulo in columnas_db:
            if accion == 'leer':
                return getattr(self, f"permiso_{modulo}", False)
            return False
        return False

    def puede_imprimir(self, modulo):
        if self.user.is_superuser:
            return True
        if not self.permisos_detalle or not isinstance(self.permisos_detalle, dict):
            return True
        mod_info = self.permisos_detalle.get(modulo, {})
        if isinstance(mod_info, bool):
            return mod_info
        if not mod_info.get('activo', False):
            return False
        return mod_info.get('imprimir', True)

    @property
    def permiso_estadisticas(self):
        return self.tiene_permiso('estadisticas', 'leer')

    @property
    def permiso_entradas(self):
        return self.tiene_permiso('entradas', 'leer')

    @property
    def permiso_respaldos(self):
        return self.tiene_permiso('respaldos', 'leer')

    @property
    def total_modulos_activos(self):
        if self.user.is_superuser:
            return 10
        modulos = [
            'dashboard', 'estadisticas', 'inventario', 'entradas',
            'atencion_ciudadano', 'entregas', 'asignaciones_especiales',
            'usuarios', 'auditoria', 'respaldos'
        ]
        return sum(1 for m in modulos if self.tiene_permiso(m, 'leer'))

    @property
    def lista_modulos_activos(self):
        modulos = [
            ('dashboard', 'Dash', '📊'),
            ('estadisticas', 'Est', '📈'),
            ('inventario', 'Inv', '📦'),
            ('entradas', 'Rec', '🚚'),
            ('atencion_ciudadano', 'Aten', '🏛️'),
            ('entregas', 'Ent', '🎁'),
            ('asignaciones_especiales', 'Asig', '🏢'),
            ('usuarios', 'Usr', '👥'),
            ('auditoria', 'Aud', '🛡️'),
            ('respaldos', 'Resp', '💾'),
        ]
        if self.user.is_superuser:
            return [(cod, nom, ico, True) for cod, nom, ico in modulos]
        return [(cod, nom, ico, self.tiene_permiso(cod, 'leer')) for cod, nom, ico in modulos]

    @property
    def puede_imprimir_entregas(self):
        return self.puede_imprimir('entregas')

    @property
    def puede_editar_entregas(self):
        return self.tiene_permiso('entregas', 'editar')

    @property
    def puede_cambiar_estatus_entregas(self):
        if self.user.is_superuser:
            return True
        if self.permisos_detalle and isinstance(self.permisos_detalle, dict):
            ent_info = self.permisos_detalle.get('entregas', {})
            if isinstance(ent_info, dict):
                if 'cambiar_estatus' in ent_info:
                    return bool(ent_info.get('cambiar_estatus', False))
                return bool(ent_info.get('crear', False) or ent_info.get('editar', False))
        return self.tiene_permiso('entregas', 'crear')

    @property
    def puede_imprimir_atencion(self):
        return self.puede_imprimir('atencion_ciudadano')

    @property
    def puede_imprimir_asignaciones(self):
        return self.puede_imprimir('asignaciones_especiales')

    @property
    def puede_imprimir_estadisticas(self):
        return self.puede_imprimir('estadisticas')

    @property
    def puede_imprimir_inventario(self):
        return self.puede_imprimir('inventario')

    @property
    def puede_imprimir_auditoria(self):
        return self.puede_imprimir('auditoria')

    @property
    def puede_imprimir_respaldos(self):
        return self.puede_imprimir('respaldos')

class ConfiguracionInstitucion(models.Model):
    nombre_institucion = models.CharField(max_length=255, default="ALCALDÍA SOCIAL / DIRECCIÓN DE ATENCIÓN CIUDADANA")
    subtitulo_institucion = models.CharField(max_length=255, default="SIA Web - Sistema Institucional de Atención e Inventario")
    rif = models.CharField(max_length=50, default="G-20000000-0")
    direccion = models.TextField(default="Av. Principal, Edificio Sede Municipal, Valera, Edo. Trujillo")
    telefono = models.CharField(max_length=100, default="0271-2310000 / 0414-0000000")
    email = models.EmailField(default="contacto@alcaldia.gob.ve")
    logo_principal = models.ImageField(upload_to='logos/', null=True, blank=True)
    logo_secundario = models.ImageField(upload_to='logos/', null=True, blank=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Institución'
        verbose_name_plural = 'Configuraciones de Institución'

    def __str__(self):
        return f"{self.nombre_institucion} (RIF: {self.rif})"

    @classmethod
    def get_solo(cls):
        config, _ = cls.objects.get_or_create(id=1)
        return config
