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

    @property
    def cant_pres_texto(self):
        if hasattr(self, '_cant_pres_texto') and self._cant_pres_texto is not None:
            return self._cant_pres_texto

        tipo_raw = (self.tipo_presentacion or '').strip().lower()
        desc_raw = (self.descripcion or '').strip().lower()
        empaque = self.unidades_por_empaque if (self.unidades_por_empaque and self.unidades_por_empaque > 0) else 1
        stock = self.cantidad or 0

        # Determinar denominación exacta: Bulto, Paquete, Caja, o Unidad
        if 'bulto' in tipo_raw or 'bulto' in desc_raw:
            singular = 'Bulto'
            plural = 'Bultos'
            es_empaque = True
        elif 'paquete' in tipo_raw or 'paquete' in desc_raw:
            singular = 'Paquete'
            plural = 'Paquetes'
            es_empaque = True
        elif tipo_raw in ['caja', 'cajas'] or 'caja' in tipo_raw or 'caja' in desc_raw:
            singular = 'Caja'
            plural = 'Cajas'
            es_empaque = True
        elif tipo_raw in ['unidad', 'unidades', 'suelta', ''] or empaque <= 1:
            singular = 'Unidad'
            plural = 'Unidades'
            es_empaque = False
        else:
            singular = tipo_raw.capitalize()
            plural = f"{singular}s"
            es_empaque = empaque > 1

        if es_empaque:
            if empaque > 1:
                cant = stock // empaque
                resto = stock % empaque
                nom = singular if cant == 1 else plural
                if resto == 0:
                    return f"{cant} {nom}"
                elif cant > 0:
                    return f"{cant} {nom} (+{resto} sueltas)"
                else:
                    return f"{resto} Unidades"
            else:
                nom = singular if stock == 1 else plural
                return f"{stock} {nom}"
        else:
            nom = singular if stock == 1 else plural
            return f"{stock} {nom}"

    @cant_pres_texto.setter
    def cant_pres_texto(self, value):
        self._cant_pres_texto = value

    @property
    def cant_pres_sub(self):
        if hasattr(self, '_cant_pres_sub') and self._cant_pres_sub is not None:
            return self._cant_pres_sub
        return ""

    @cant_pres_sub.setter
    def cant_pres_sub(self, value):
        self._cant_pres_sub = value

    @property
    def presentacion_con_cantidad(self):
        if hasattr(self, '_presentacion_con_cantidad') and self._presentacion_con_cantidad is not None:
            return self._presentacion_con_cantidad
        return self.cant_pres_texto

    @presentacion_con_cantidad.setter
    def presentacion_con_cantidad(self, value):
        self._presentacion_con_cantidad = value




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

