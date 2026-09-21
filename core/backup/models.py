from django.db import models
from django.contrib.auth.models import User

class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.TextField()  # Descripción de lo que hizo
    modulo = models.CharField(max_length=100, blank=True, null=True)  # Ej: 'Entregas', 'Inventario'
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip_origen = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.fecha_hora.strftime('%Y-%m-%d %H:%M')} - {self.usuario} - {self.accion}"

class AsignacionEspecial(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    nombre_receptor = models.CharField(max_length=255)
    departamento_o_cargo = models.CharField(max_length=255, blank=True, null=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

class DetalleAsignacionEspecial(models.Model):
    asignacion = models.ForeignKey(AsignacionEspecial, related_name='detalles', on_delete=models.CASCADE)
    descripcion_prod = models.CharField(max_length=255)
    cantidad = models.PositiveIntegerField()

class Producto(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=200)
    almacen = models.CharField(max_length=100, default='Principal')
    cantidad = models.IntegerField(default=0)
    
    TIPO_PRESENTACION = [
        ('unidad', 'Unidades Sueltas'),
        ('caja', 'Caja / Paquete / Bulto'),
    ]
    tipo_presentacion = models.CharField(max_length=20, choices=TIPO_PRESENTACION, default='unidad')
    unidades_por_empaque = models.IntegerField(default=1)

    class Meta:
        db_table = 'SIA_producto'

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"
