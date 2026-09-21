import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from presupuesto.models import ProyectoPOA, PartidaPresupuestaria
from contabilidad.models import CuentaPUC, AsientoContable, DetalleAsientoContable
from tributos.models import Contribuyente, LicenciaActividadEconomica, LiquidacionTributaria
from bienes.models import ActivoPatrimonial
from rrhh.models import FuncionarioPublico
from compras.models import ProveedorRNC
from documentos.models import DocumentoOficial
from catastro.models import InmuebleCatastral

def seed():
    admin = User.objects.filter(is_superuser=True).first()

    # 1. Presupuesto POA
    poa, _ = ProyectoPOA.objects.get_or_create(
        codigo="POA-2026-01",
        defaults={
            'nombre': "Fortalecimiento de los Servicios Públicos e Infraestructura Municipal 2026",
            'monto_total_asignado': 5000000.00,
            'responsable': "Dirección de Planificación y Presupuesto"
        }
    )

    p1, _ = PartidaPresupuestaria.objects.get_or_create(
        codigo="4.01.01.01.00",
        proyecto=poa,
        defaults={'denominacion': "Sueldos y Salarios Personal Fijo", 'monto_inicial': 2000000.00}
    )
    p2, _ = PartidaPresupuestaria.objects.get_or_create(
        codigo="4.02.01.01.00",
        proyecto=poa,
        defaults={'denominacion': "Materiales de Oficina y Equipamiento", 'monto_inicial': 500000.00}
    )

    # 2. Contabilidad PUC
    c1, _ = CuentaPUC.objects.get_or_create(codigo="1.1.1.01.001", defaults={'nombre': "Banco del Tesoro - Cuenta Principal", 'tipo': 'Activo', 'naturaleza': 'Deudora'})
    c2, _ = CuentaPUC.objects.get_or_create(codigo="2.1.1.01.001", defaults={'nombre': "Cuentas por Pagar a Proveedores", 'tipo': 'Pasivo', 'naturaleza': 'Acreedora'})
    c3, _ = CuentaPUC.objects.get_or_create(codigo="5.1.1.01.001", defaults={'nombre': "Gastos de Personal Fijo", 'tipo': 'Gasto', 'naturaleza': 'Deudora'})

    # 3. Tributos SUMAR
    contrib, _ = Contribuyente.objects.get_or_create(
        rif_cedula="J-30495861-0",
        defaults={
            'nombre_razon_social': "Comercializadora e Inversiones Valera C.A.",
            'direccion_fiscal': "Av. Bolívar con Calle 10, Valera, Trujillo",
            'telefono': "0271-2254100",
            'email': "contacto@comercializadoravalera.com"
        }
    )
    LicenciaActividadEconomica.objects.get_or_create(
        num_licencia="LIC-2026-0089",
        defaults={'contribuyente': contrib, 'ramo_comercial': "Venta de Víveres y Alimentos", 'alicuota_porcentaje': 1.50}
    )

    # 4. Bienes Públicos SUDEBIP
    ActivoPatrimonial.objects.get_or_create(
        codigo_patrimonial="BM-2026-0001",
        defaults={
            'descripcion': "Servidor Central HP ProLiant DL380 Gen10",
            'categoria': "Mueble",
            'marca': "HP",
            'modelo': "ProLiant Gen10",
            'serial': "SN-HP-994821",
            'valor_adquisicion': 18500.00,
            'responsable_patrimonial': "Ing. Jean Cabrita - Director de Informática",
            'ubicacion_dependencia': "Centro de Datos / Dirección de Tecnología"
        }
    )

    # 5. Recursos Humanos
    FuncionarioPublico.objects.get_or_create(
        cedula="V-18492019",
        defaults={
            'nombres': "Carlos Alberto",
            'apellidos': "Mendoza Rivas",
            'cargo': "Analista Contable III",
            'departamento': "Dirección de Contabilidad y Finanzas",
            'tipo_personal': 'Fijo',
            'sueldo_base': 12000.00,
            'anos_servicio': 6,
            'nivel_academico': "Profesional",
            'fecha_ingreso': "2020-03-15"
        }
    )

    # 6. Compras RNC
    ProveedorRNC.objects.get_or_create(
        rif="J-40592817-2",
        defaults={
            'razon_social': "Distribuidora Médica e Insumos Sanitarios C.A.",
            'num_rnc': "RNC-99482-A",
            'ramo_actividad': "Suministros Médicos y Farmacéuticos",
            'telefono': "0212-9840192",
            'email': "ventas@distribuidoramedica.com",
            'direccion': "Zona Industrial Valera, Edo. Trujillo"
        }
    )

    # 7. Documentos OFIPOL
    DocumentoOficial.objects.get_or_create(
        num_radicado="OFI-2026-0001",
        defaults={
            'tipo': 'Oficio',
            'remitente': "Dirección General de Gestión Pública",
            'destinatario': "Superintendencia de Administración Tributaria (SUMAR)",
            'asunto': "Remisión de Informe Trimestral de Recaudación y Solvencias Municipales",
            'contenido': "Por medio del presente se remite el balance consolidado del primer trimestre...",
            'estatus': 'Aprobado',
            'creado_por': admin
        }
    )

    # 8. Catastro Municipal
    InmuebleCatastral.objects.get_or_create(
        codigo_catastral="05-01-02-001-0005",
        defaults={
            'propietario_nombre': "Inversiones Y Construcciones El Carmen C.A.",
            'propietario_cedula_rif': "J-29481029-4",
            'parroquia': "Juan Ignacio Montilla",
            'sector_direccion': "Calle 8 entre Avenidas 5 y 6, Parcela N° 5",
            'superficie_terreno_m2': 450.00,
            'superficie_construccion_m2': 380.00,
            'valor_catastral_bs': 350000.00,
            'uso_inmueble': 'Comercial'
        }
    )

    print("SUCCESS: Todos los 8 modulos empresariales GRP han sido poblados con datos de demostracion.")

if __name__ == '__main__':
    seed()
