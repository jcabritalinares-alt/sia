from django.db import models

class SIA_producto(models.Model):
    codigo = models.CharField(max_length=100, unique=True, primary_key=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    almacen = models.CharField(max_length=100, blank=True, null=True)
    cantidad = models.IntegerField(default=0)
    timestamp = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'SIA_producto'  # <--- Esto le indica el nombre exacto que tendrá en PostgreSQL

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"
