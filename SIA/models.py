from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MODELO PRINCIPAL: PRODUCTO / BIEN DE INVENTARIO
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class SIA_producto(models.Model):
    codigo = models.CharField(max_length=255, unique=True, db_index=True, verbose_name='Codigo')
    descripcion = models.TextField(verbose_name='Descripcion', default='', blank=True)
    tipo_presentacion = models.CharField(max_length=100, blank=True, null=True, verbose_name='Tipo/Presentacion')
    unidades_por_empaque = models.IntegerField(default=1, verbose_name='Unidades por Empaque')
    almacen = models.CharField(max_length=255, blank=True, null=True, db_index=True, verbose_name='Almacen')
    cantidad = models.IntegerField(default=0, verbose_name='Cantidad')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')

    class Meta:
        db_table = 'SIA_producto'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-timestamp']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=0),
                name='sia_producto_cantidad_no_negativa'
            )
        ]

    def __str__(self):
        return f'[{self.codigo}] {self.descripcion[:60]}'




# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ENTRADAS DE INVENTARIO (RecepciÃ³n de MercancÃ­a por GuÃ­as)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class EntradaInventario(models.Model):
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    nro_guia_o_acta = models.CharField(max_length=100, blank=True, null=True, verbose_name='NÂ° GuÃ­a / Acta de RecepciÃ³n')
    origen_o_proveedor = models.CharField(max_length=255, verbose_name='Proveedor / Origen')
    rif_proveedor = models.CharField(max_length=20, default='G-20000001-9', verbose_name='RIF del Proveedor')
    observaciones = models.TextField(blank=True, null=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Entrada de Inventario'
        verbose_name_plural = 'Entradas de Inventario'

    def __str__(self):
        return f'Entrada #{self.id} â€“ {self.origen_o_proveedor} ({self.fecha.strftime("%d/%m/%Y")})'


class DetalleEntradaInventario(models.Model):
    entrada = models.ForeignKey(EntradaInventario, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(SIA_producto, on_delete=models.CASCADE)
    cantidad_ingresada = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.producto.descripcion} (+{self.cantidad_ingresada})'

