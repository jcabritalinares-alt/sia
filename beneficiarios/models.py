from django.db import models

class Beneficiario(models.Model):
    cedula = models.CharField(max_length=50, unique=True, primary_key=True)
    nombre_apellido = models.CharField(max_length=150)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.nombre_apellido
