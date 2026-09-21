import re
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Sum, Count, Q, Max
from django.urls import reverse

from beneficiarios.models import Beneficiario
from entregas.models import BeneficioEntregado
from core.models import SolicitudCiudadano
from core.utils import consultar_cedula_sistemaspnp, obtener_url_inicio_usuario

logger = logging.getLogger(__name__)


def verificar_permiso_beneficiarios(user):
    """
    Comprueba si el usuario tiene permiso para consultar beneficiarios.
    Permitido a Superusuarios, operadores con permiso_entregas o permiso_atencion_ciudadano.
    """
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfil', None)
    if not perfil:
        return False
    return bool(perfil.permiso_entregas or perfil.permiso_atencion_ciudadano)


@login_required
def consulta_beneficiarios(request):
    """
    Vista principal de Consulta y Expediente de Beneficiarios.
    Permite buscar por cédula tanto en BD local como con fallback a sistemaspnp.com (CNE).
    Muestra:
    - Datos del ciudadano (Cédula, Nombre, Teléfono, Dirección, Centro Electoral).
    - En caso de haber recibido beneficios: tabla detallada con productos, cantidades, estado y comprobantes.
    - En caso de no registrar beneficios: mensaje informativo claro y botón rápido para asignar primer beneficio.
    - Solicitudes de atención al ciudadano asociadas (si existen).
    """
    if not verificar_permiso_beneficiarios(request.user):
        messages.error(request, "Acceso restringido: No tienes permiso para acceder al módulo de Beneficiarios.")
        return redirect(obtener_url_inicio_usuario(request.user))

    cedula_input = request.GET.get('cedula', '').strip()
    forzar_cne = request.GET.get('forzar_cne', 'false').lower() == 'true'

    ciudadano = None
    entregas = []
    solicitudes = []
    total_entregas = 0
    total_articulos = 0
    tiene_beneficios = False
    busqueda_realizada = False
    no_encontrado = False

    cedula_numerica = re.sub(r'\D', '', cedula_input)

    if cedula_numerica:
        busqueda_realizada = True

        # 1. Búsqueda local
        beneficiario = None
        if not forzar_cne:
            beneficiario = Beneficiario.objects.filter(cedula=cedula_numerica).first()

        # 2. Búsqueda en CNE si no existe local o si se fuerza
        datos_cne = None
        if not beneficiario or not beneficiario.nombre_apellido or forzar_cne:
            try:
                datos_cne = consultar_cedula_sistemaspnp(cedula_numerica)
            except Exception as e:
                logger.warning(f"Error al consultar CNE para cédula {cedula_numerica}: {e}")

        # 3. Consolidación de datos del ciudadano
        if beneficiario and beneficiario.nombre_apellido and not forzar_cne:
            ciudadano = {
                'cedula': beneficiario.cedula,
                'nombre_apellido': beneficiario.nombre_apellido,
                'telefono': beneficiario.telefono or '',
                'direccion': beneficiario.direccion or '',
                'centro_electoral': '',
                'parroquia': '',
                'municipio': '',
                'estado': '',
                'origen': 'local'
            }
        elif datos_cne and datos_cne.get('nombre_completo'):
            ciudadano = {
                'cedula': cedula_numerica,
                'nombre_apellido': datos_cne.get('nombre_completo'),
                'telefono': beneficiario.telefono if beneficiario else '',
                'direccion': beneficiario.direccion if (beneficiario and beneficiario.direccion) else datos_cne.get('direccion_sugerida', ''),
                'centro_electoral': datos_cne.get('centro_electoral', ''),
                'parroquia': datos_cne.get('parroquia', ''),
                'municipio': datos_cne.get('municipio', ''),
                'estado': datos_cne.get('estado', ''),
                'origen': 'sistemaspnp'
            }
        elif beneficiario:
            ciudadano = {
                'cedula': beneficiario.cedula,
                'nombre_apellido': beneficiario.nombre_apellido,
                'telefono': beneficiario.telefono or '',
                'direccion': beneficiario.direccion or '',
                'centro_electoral': '',
                'parroquia': '',
                'municipio': '',
                'estado': '',
                'origen': 'local'
            }
        else:
            # Comprobar si al menos tiene entregas previas con ese número de cédula
            entrega_previa = BeneficioEntregado.objects.filter(cedula=cedula_numerica).first()
            if entrega_previa and entrega_previa.nombre_beneficiario:
                ciudadano = {
                    'cedula': cedula_numerica,
                    'nombre_apellido': entrega_previa.nombre_beneficiario,
                    'telefono': '',
                    'direccion': '',
                    'centro_electoral': '',
                    'parroquia': '',
                    'municipio': '',
                    'estado': '',
                    'origen': 'entregas_historico'
                }
            else:
                no_encontrado = True

        # 4. Historial de beneficios entregados
        qs_entregas = BeneficioEntregado.objects.filter(cedula=cedula_numerica).order_by('-fecha', '-id')
        entregas = list(qs_entregas)
        total_entregas = len(entregas)
        tiene_beneficios = total_entregas > 0
        total_articulos = qs_entregas.aggregate(Sum('cantidad_dada'))['cantidad_dada__sum'] or 0

        # 5. Solicitudes sociales
        solicitudes = list(SolicitudCiudadano.objects.filter(cedula=cedula_numerica).order_by('-fecha_solicitud'))

    # Beneficiarios recientes para exploración inicial
    recientes = []
    if not busqueda_realizada:
        recientes_qs = BeneficioEntregado.objects.values(
            'cedula', 'nombre_beneficiario'
        ).annotate(
            total_recibido=Count('id'),
            ultima_fecha=Max('fecha')
        ).order_by('-ultima_fecha')[:12]
        recientes = list(recientes_qs)

    total_beneficiarios_registrados = Beneficiario.objects.count()
    total_entregas_historico = BeneficioEntregado.objects.count()

    context = {
        'cedula_input': cedula_input,
        'cedula_numerica': cedula_numerica,
        'ciudadano': ciudadano,
        'entregas': entregas,
        'solicitudes': solicitudes,
        'total_entregas': total_entregas,
        'total_articulos': total_articulos,
        'tiene_beneficios': tiene_beneficios,
        'busqueda_realizada': busqueda_realizada,
        'no_encontrado': no_encontrado,
        'forzar_cne': forzar_cne,
        'recientes': recientes,
        'total_beneficiarios_registrados': total_beneficiarios_registrados,
        'total_entregas_historico': total_entregas_historico,
    }
    return render(request, 'beneficiarios/consulta.html', context)


@login_required
def api_consultar_beneficiario_expediente(request):
    """
    Endpoint JSON para búsqueda en vivo y reactiva desde el navegador.
    Sigue exactamente la misma lógica dual (Local + CNE) que la entrega de beneficios.
    """
    if not verificar_permiso_beneficiarios(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    cedula_raw = request.GET.get('cedula', '').strip()
    cedula = re.sub(r'\D', '', cedula_raw)
    forzar_cne = request.GET.get('forzar_cne', 'false').lower() == 'true'

    if not cedula or len(cedula) < 4:
        return JsonResponse({'existe': False, 'error': 'Cédula inválida o menor a 4 dígitos'})

    # 1. Búsqueda local
    beneficiario = None
    if not forzar_cne:
        beneficiario = Beneficiario.objects.filter(cedula=cedula).first()

    datos_cne = None
    if not beneficiario or not beneficiario.nombre_apellido or forzar_cne:
        try:
            datos_cne = consultar_cedula_sistemaspnp(cedula)
        except Exception as e:
            logger.warning(f"Error CNE en api_consultar_beneficiario_expediente: {e}")

    # Determinar identidad
    ciudadano = None
    origen = 'local'

    if beneficiario and beneficiario.nombre_apellido and not forzar_cne:
        ciudadano = {
            'cedula': beneficiario.cedula,
            'nombre_apellido': beneficiario.nombre_apellido,
            'telefono': beneficiario.telefono or '',
            'direccion': beneficiario.direccion or '',
            'centro_electoral': '',
            'parroquia': '',
            'municipio': '',
            'estado': ''
        }
        origen = 'local'
    elif datos_cne and datos_cne.get('nombre_completo'):
        ciudadano = {
            'cedula': cedula,
            'nombre_apellido': datos_cne.get('nombre_completo'),
            'telefono': beneficiario.telefono if beneficiario else '',
            'direccion': beneficiario.direccion if (beneficiario and beneficiario.direccion) else datos_cne.get('direccion_sugerida', ''),
            'centro_electoral': datos_cne.get('centro_electoral', ''),
            'parroquia': datos_cne.get('parroquia', ''),
            'municipio': datos_cne.get('municipio', ''),
            'estado': datos_cne.get('estado', '')
        }
        origen = 'sistemaspnp'
    elif beneficiario:
        ciudadano = {
            'cedula': beneficiario.cedula,
            'nombre_apellido': beneficiario.nombre_apellido,
            'telefono': beneficiario.telefono or '',
            'direccion': beneficiario.direccion or '',
            'centro_electoral': '',
            'parroquia': '',
            'municipio': '',
            'estado': ''
        }
        origen = 'local'
    else:
        entrega_previa = BeneficioEntregado.objects.filter(cedula=cedula).first()
        if entrega_previa and entrega_previa.nombre_beneficiario:
            ciudadano = {
                'cedula': cedula,
                'nombre_apellido': entrega_previa.nombre_beneficiario,
                'telefono': '',
                'direccion': '',
                'centro_electoral': '',
                'parroquia': '',
                'municipio': '',
                'estado': ''
            }
            origen = 'entregas_historico'

    if not ciudadano:
        return JsonResponse({
            'existe': False,
            'cedula': cedula,
            'mensaje': 'No se encontraron datos de identidad para esta cédula.'
        })

    # Historial de beneficios
    qs_entregas = BeneficioEntregado.objects.filter(cedula=cedula).order_by('-fecha', '-id')
    entregas_list = []
    for e in qs_entregas:
        entregas_list.append({
            'id': e.id,
            'fecha_str': e.fecha.strftime('%d/%m/%Y') if e.fecha else 'N/A',
            'descripcion_prod': e.descripcion_prod or 'Beneficio Desconocido',
            'codigo_prod': e.codigo_prod or '',
            'cantidad_dada': e.cantidad_dada,
            'status': e.status or 'Entregado',
            'via': e.via or 'Directa',
            'url_evidencia_1': e.url_evidencia_1 or '',
            'url_evidencia_2': e.url_evidencia_2 or '',
            'url_evidencia_3': getattr(e, 'url_evidencia_3', '') or '',
            'tiene_firma': bool(e.firma_beneficiario),
            'url_comprobante_pdf': reverse('generar_comprobante_pdf', args=[e.id]),
            'url_comprobante_publico': reverse('ver_comprobante_entrega_publico', args=[e.id])
        })

    total_articulos = qs_entregas.aggregate(Sum('cantidad_dada'))['cantidad_dada__sum'] or 0

    # Solicitudes de atención
    qs_sol = SolicitudCiudadano.objects.filter(cedula=cedula).order_by('-fecha_solicitud')
    solicitudes_list = []
    for s in qs_sol:
        solicitudes_list.append({
            'id': s.id,
            'fecha_str': s.fecha_solicitud.strftime('%d/%m/%Y %H:%M') if s.fecha_solicitud else 'N/A',
            'tipo_solicitud': s.tipo_solicitud,
            'status': s.status,
            'prioridad': s.prioridad,
            'descripcion_solicitud': s.descripcion_solicitud
        })

    return JsonResponse({
        'existe': True,
        'origen': origen,
        'ciudadano': ciudadano,
        'tiene_beneficios': len(entregas_list) > 0,
        'total_entregas': len(entregas_list),
        'total_articulos': total_articulos,
        'entregas': entregas_list,
        'solicitudes': solicitudes_list,
        'url_asignar_beneficio': reverse('asignar_beneficio') + f"?cedula={cedula}",
        'url_ficha_360': reverse('ficha_ciudadano_360', args=[cedula])
    })


def normalizar_telefono_whatsapp(telefono_raw):
    """
    Normaliza un número de teléfono para enlaces de WhatsApp (wa.me).
    Ejemplos:
    - '04247469405' -> '584247469405'
    - '0414-1234567' -> '584141234567'
    - '4121234567' -> '584121234567'
    - '+584141234567' -> '584141234567'
    """
    if not telefono_raw:
        return '', False

    digitos = re.sub(r'\D', '', str(telefono_raw))
    if not digitos:
        return '', False

    # En Venezuela:
    if digitos.startswith('0') and len(digitos) == 11:
        return '58' + digitos[1:], True

    if digitos.startswith('4') and len(digitos) == 10:
        return '58' + digitos, True

    if digitos.startswith('58') and len(digitos) == 12:
        return digitos, True

    if len(digitos) >= 7:
        if digitos.startswith('58'):
            return digitos, True
        elif digitos.startswith('0'):
            return '58' + digitos[1:], True
        else:
            return '58' + digitos, True

    return digitos, False


@login_required
def api_obtener_beneficiarios_whatsapp(request):
    """
    Retorna la lista completa de beneficiarios registrados en la BD local con teléfono
    para el módulo de mensajería masiva de WhatsApp.
    """
    if not verificar_permiso_beneficiarios(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    beneficiarios_qs = Beneficiario.objects.exclude(telefono__isnull=True).exclude(telefono__exact='').order_by('nombre_apellido')

    lista_resultado = []
    validos_count = 0

    for b in beneficiarios_qs:
        tlf_norm, es_valido = normalizar_telefono_whatsapp(b.telefono)
        if es_valido:
            validos_count += 1

        lista_resultado.append({
            'cedula': b.cedula,
            'nombre_apellido': b.nombre_apellido,
            'telefono': b.telefono or '',
            'telefono_normalizado': tlf_norm,
            'es_valido_whatsapp': es_valido,
            'direccion': b.direccion or ''
        })

    return JsonResponse({
        'ok': True,
        'total_registrados': len(lista_resultado),
        'total_validos_whatsapp': validos_count,
        'beneficiarios': lista_resultado
    })

