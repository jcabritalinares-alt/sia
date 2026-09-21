import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.urls import get_resolver, reverse
from django.template.loader import get_template

def audit_urls_and_views():
    print("=== AUDIT 1: Testing URL Resolvers & Views ===")
    client = Client()
    admin = User.objects.filter(is_superuser=True).first()
    if admin:
        client.force_login(admin)

    urls_to_test = [
        ('/', 'Home'),
        ('/login/', 'Login'),
        ('/dashboard/', 'Dashboard'),
        ('/inventario/', 'Inventario'),
        ('/inventario/registrar/', 'Registrar Inventario'),
        ('/inventario/entradas/', 'Entradas'),
        ('/inventario/entradas/nueva/', 'Nueva Entrada'),
        ('/inventario/exportar-excel/', 'Exportar Inventario Excel'),
        ('/inventario/etiquetas/1/', 'Etiquetas Producto 1'),
        ('/inventario/ficha/1/', 'Ficha Producto 1'),
        ('/entregar/', 'Asignar Beneficio'),
        ('/historial/', 'Historial Entregas'),
        ('/historial/exportar-excel/', 'Exportar Historial Excel'),
        ('/atencion-ciudadano/', 'Lista Solicitudes'),
        ('/atencion-ciudadano/nueva/', 'Nueva Solicitud'),
        ('/atencion-ciudadano/exportar-excel/', 'Exportar Solicitudes Excel'),
        ('/atencion-ciudadano/reporte-pdf/', 'Reporte Solicitudes PDF'),
        ('/atencion-ciudadano/2/imprimir/', 'Comprobante Solicitud 2'),
        ('/atencion-ciudadano/2/constancia-pdf/', 'Constancia Solicitud PDF 2'),
        ('/estadisticas/', 'Estadísticas Avanzadas'),
        ('/estadisticas/reporte-parroquias-pdf/', 'Reporte Parroquias PDF'),
        ('/usuarios-conectados/', 'Usuarios Conectados'),
        ('/api/usuarios-conectados/', 'API Usuarios Conectados'),
        ('/api/busqueda-global/?q=a', 'API Búsqueda Global'),
        ('/api/verificar-duplicados/?cedula=12345', 'API Verificar Duplicados'),
        ('/api/estadisticas-filtradas/?rango=todos', 'API Estadísticas Filtradas'),
        ('/auditoria/', 'Lista Auditoría'),
        ('/auditoria/exportar-excel/', 'Exportar Auditoría Excel'),
        ('/admin-sistema/institucion/', 'Configurar Institución'),
        ('/admin-sistema/respaldos/', 'Gestión Respaldos'),
        ('/ciudadano/16266728/ficha/', 'Ficha 360 Ciudadano'),
        ('/grp/presupuesto/', 'Presupuesto Fiscal SIGEF'),
        ('/grp/contabilidad/', 'Contabilidad Patrimonial NICSP'),
        ('/grp/tributos/', 'Tesorería y Tributos SUMAR'),
        ('/grp/bienes/', 'Bienes Públicos SUDEBIP'),
        ('/grp/rrhh/', 'Recursos Humanos y Nómina'),
        ('/grp/compras/', 'Compras y Licitaciones SNC'),
        ('/grp/documentos/', 'Gestión Documental OFIPOL'),
        ('/grp/catastro/', 'Catastro Municipal GIS'),
    ]

    errors = []
    for path, name in urls_to_test:
        try:
            res = client.get(path, follow=True)
            if res.status_code == 500:
                errors.append(f"[FAIL 500] en {name} ({path})")
            elif res.status_code == 404:
                errors.append(f"[FAIL 404] en {name} ({path})")
            else:
                print(f"  [OK {res.status_code}] {name} ({path})")
        except Exception as e:
            errors.append(f"[FAIL EXCEPTION] en {name} ({path}): {str(e)}")

    return errors

def audit_models():
    print("\n=== AUDIT 2: Testing Models & Queries ===")
    from core.models import SolicitudCiudadano, RegistroAuditoria, PerfilUsuario
    from SIA.models import SIA_producto, EntradaInventario
    from entregas.models import BeneficioEntregado
    from beneficiarios.models import Beneficiario

    model_counts = {
        'User': User.objects.count(),
        'SolicitudCiudadano': SolicitudCiudadano.objects.count(),
        'SIA_producto': SIA_producto.objects.count(),
        'EntradaInventario': EntradaInventario.objects.count(),
        'BeneficioEntregado': BeneficioEntregado.objects.count(),
        'RegistroAuditoria': RegistroAuditoria.objects.count(),
        'PerfilUsuario': PerfilUsuario.objects.count(),
        'Beneficiario': Beneficiario.objects.count(),
    }

    for model, count in model_counts.items():
        print(f"  - {model}: {count} registros en BD")

    # Test edge case queries
    null_cedulas = SolicitudCiudadano.objects.filter(cedula__isnull=True).count()
    if null_cedulas > 0:
        print(f"  ⚠️ ALERTA: {null_cedulas} solicitudes con cédula NULL")

    return []

if __name__ == '__main__':
    errors = audit_urls_and_views()
    audit_models()

    if errors:
        print("\n=== ERRORES ENCONTRADOS ===")
        for err in errors:
            print(err)
        sys.exit(1)
    else:
        print("\nSUCCESS: El sistema no presento errores ni excepciones HTTP 500.")
