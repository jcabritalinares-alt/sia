from django.db import models

PARROQUIAS_VALERA = [
    ('Juan Ignacio Montilla', 'Juan Ignacio Montilla'),
    ('La Beatriz', 'La Beatriz'),
    ('Mercedes Díaz', 'Mercedes Díaz'),
    ('San Luis', 'San Luis'),
    ('Mendoza Fría', 'Mendoza Fría'),
    ('La Puerta', 'La Puerta'),
    ('Otra / Foránea', 'Otra / Foránea'),
]

class Beneficiario(models.Model):
    cedula = models.CharField(max_length=50, unique=True, primary_key=True)
    nombre_apellido = models.CharField(max_length=150)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    parroquia = models.CharField(max_length=100, choices=PARROQUIAS_VALERA, default='Juan Ignacio Montilla', blank=True, null=True, db_index=True, verbose_name="Parroquia")
    timestamp = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.nombre_apellido
