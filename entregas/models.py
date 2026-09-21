from django.db import models

class BeneficioEntregado(models.Model):
    firebase_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    producto = models.ForeignKey('SIA.SIA_producto', on_delete=models.SET_NULL, null=True, blank=True, related_name='entregas')
    cantidad_dada = models.IntegerField(default=0)
    cedula = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    codigo_prod = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    descripcion_prod = models.CharField(max_length=255, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True, db_index=True)
    fecha_entrega = models.DateField(blank=True, null=True, db_index=True, verbose_name="Fecha de Entrega")
    nombre_beneficiario = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    timestamp = models.DateTimeField(blank=True, null=True)
    
    # Columnas independientes para las 3 evidencias
    url_evidencia_1 = models.URLField(max_length=500, blank=True, null=True)
    url_evidencia_2 = models.URLField(max_length=500, blank=True, null=True)
    url_evidencia_3 = models.URLField(max_length=500, blank=True, null=True)
    
    via = models.CharField(max_length=100, blank=True, null=True)
    firma_beneficiario = models.TextField(blank=True, null=True)
    huella_dactilar = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre_beneficiario} - {self.descripcion_prod} ({self.status})"

