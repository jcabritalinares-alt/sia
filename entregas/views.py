import os
import ssl
import base64
import tempfile
import re
import logging
from datetime import date, datetime
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.db.models import Sum, Q
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from django.core.exceptions import ValidationError
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import cloudinary
import cloudinary.uploader
from xhtml2pdf import pisa

# Bypass SSL certificate verification for Cloudinary image fetching in xhtml2pdf on Windows
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

from SIA.models import SIA_producto

logger = logging.getLogger(__name__)
from beneficiarios.models import Beneficiario
from entregas.models import BeneficioEntregado
from core.models import AsignacionEspecial, DetalleAsignacionEspecial, RegistroAuditoria, SolicitudCiudadano
from core.utils import obtener_url_inicio_usuario, generar_hash_firma_digital, consultar_cedula_sistemaspnp

import time
import uuid
import email.utils
import urllib.request
import cloudinary.utils
from django.conf import settings

cloudinary.config( 
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME', ''), 
    api_key = os.getenv('CLOUDINARY_API_KEY', ''), 
    api_secret = os.getenv('CLOUDINARY_API_SECRET', '') 
)

_CLOUDINARY_TIME_OFFSET = None
_LAST_OFFSET_CHECK = 0

def obtener_offset_tiempo_servidor():
    """Calcula la diferencia de segundos entre el reloj local y el tiempo real del servidor (UTC)."""
    global _CLOUDINARY_TIME_OFFSET, _LAST_OFFSET_CHECK
    ahora = time.time()
    if _CLOUDINARY_TIME_OFFSET is not None and (ahora - _LAST_OFFSET_CHECK) < 1800:
        return _CLOUDINARY_TIME_OFFSET
    try:
        req = urllib.request.Request('https://www.google.com', headers={'User-Agent': 'Mozilla/5.0'}, method='HEAD')
        with urllib.request.urlopen(req, timeout=3) as resp:
            date_hdr = resp.headers.get('Date')
            if date_hdr:
                server_dt = email.utils.parsedate_to_datetime(date_hdr)
                _CLOUDINARY_TIME_OFFSET = int(server_dt.timestamp() - ahora)
                _LAST_OFFSET_CHECK = ahora
                return _CLOUDINARY_TIME_OFFSET
    except Exception:
        pass
    return _CLOUDINARY_TIME_OFFSET or 0

def _synced_cloudinary_now():
    offset = obtener_offset_tiempo_servidor()
    return int(time.time() + offset)

if hasattr(cloudinary.utils, 'now'):
    cloudinary.utils.now = _synced_cloudinary_now

def subir_archivo_evidencia_seguro(archivo_file, request=None):
    """
    Sube una imagen de evidencia a Cloudinary con corrección automática de desfase de reloj.
    Si Cloudinary no está disponible o falla por cualquier motivo, almacena el archivo localmente
    en MEDIA_ROOT/evidencias/ sin interrumpir el registro de entrega ni arrojar error 500.
    """
    if not archivo_file:
        return None

    # Intento 1: Cloudinary con timestamp sincronizado
    try:
        resp = cloudinary.uploader.upload(archivo_file)
        sec_url = resp.get('secure_url')
        if sec_url:
            return sec_url
    except Exception as err:
        logger.warning(f"Aviso: Subida a Cloudinary no completada ({err}). Aplicando almacenamiento local seguro.")

    # Intento 2: Almacenamiento local de contingencia en media/evidencias/
    try:
        archivo_file.seek(0)
        ext = os.path.splitext(archivo_file.name)[-1].lower() or '.jpg'
        nombre_unico = f"evidencia_{uuid.uuid4().hex[:12]}{ext}"
        carpeta_evidencias = os.path.join(settings.MEDIA_ROOT, 'evidencias')
        os.makedirs(carpeta_evidencias, exist_ok=True)
        ruta_destino = os.path.join(carpeta_evidencias, nombre_unico)
        with open(ruta_destino, 'wb+') as destino:
            for chunk in archivo_file.chunks():
                destino.write(chunk)

        url_relativa = f"/media/evidencias/{nombre_unico}"
        if request:
            return request.build_absolute_uri(url_relativa)
        return url_relativa
    except Exception as local_err:
        logger.error(f"Error en almacenamiento local de evidencia: {local_err}")
        return None

def parse_date_safe(val):
    """Convierte de forma segura una cadena en objeto date de Python sin lanzar excepciones."""
    if not val or not str(val).strip():
        return None
    val_str = str(val).strip()
    try:
        return datetime.strptime(val_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        try:
            return datetime.strptime(val_str, '%d/%m/%Y').date()
        except (ValueError, TypeError):
            return None

def sincronizar_estado_solicitud(entrega, nuevo_status, solicitud_id=None):
    """
    Sincroniza el estado de la SolicitudCiudadano ÚNICAMENTE cuando una entrega
    está explícitamente vinculada a dicha solicitud (por ID explícito o 'Solicitud #ID' en vía).
    Jamás busca por cédula de forma genérica para evitar alterar solicitudes sociales independientes.
    """
    if not entrega:
        return

    solicitud = None
    if solicitud_id and str(solicitud_id).isdigit():
        solicitud = SolicitudCiudadano.objects.filter(id=int(solicitud_id)).first()

    if not solicitud and entrega.via and 'Solicitud #' in entrega.via:
        match = re.search(r'Solicitud #(\d+)', entrega.via)
        if match:
            solicitud = SolicitudCiudadano.objects.filter(id=int(match.group(1))).first()

    if solicitud:
        if nuevo_status == 'Entregado':
            solicitud.status = 'Entregada'
        elif nuevo_status == 'Pendiente':
            solicitud.status = 'En Proceso'

        nota = f"Actualización automática por entrega #{entrega.id} '{entrega.descripcion_prod}' estado '{nuevo_status}'."
        if solicitud.observaciones_seguimiento:
            if nota not in solicitud.observaciones_seguimiento:
                solicitud.observaciones_seguimiento += f"\n- {nota}"
        else:
            solicitud.observaciones_seguimiento = nota
        solicitud.save()

def obtener_producto_de_entrega(entrega, for_update=False):
    """
    Resuelve de forma robusta e inteligente el producto en SIA_producto sin bloquear toda la tabla:
    0. Clave foránea directa si ya está vinculada.
    1. Por código de producto exacto (codigo_prod).
    2. Por ID primario si codigo_prod es un entero numérico.
    3. Por coincidencia de descripción (exacta o icontains).
    4. Por palabras clave del nombre.
    """
    if not entrega:
        return None

    prod_id = getattr(entrega, 'producto_id', None)

    if not prod_id and entrega.codigo_prod and str(entrega.codigo_prod).isdigit():
        prod_id = SIA_producto.objects.filter(id=int(entrega.codigo_prod)).values_list('id', flat=True).first()

    if not prod_id and entrega.codigo_prod:
        prod_id = SIA_producto.objects.filter(codigo=entrega.codigo_prod).values_list('id', flat=True).first()

    if not prod_id and entrega.descripcion_prod and entrega.descripcion_prod.strip():
        desc = entrega.descripcion_prod.strip()
        prod_id = SIA_producto.objects.filter(descripcion__iexact=desc).values_list('id', flat=True).first()
        if not prod_id:
            prod_id = SIA_producto.objects.filter(descripcion__icontains=desc).values_list('id', flat=True).first()
        if not prod_id:
            palabras = [w for w in desc.split() if len(w) >= 3]
            for w in palabras:
                prod_id = SIA_producto.objects.filter(descripcion__icontains=w).values_list('id', flat=True).first()
                if prod_id:
                    break

    if prod_id:
        qs = SIA_producto.objects.filter(id=prod_id)
        return qs.select_for_update().first() if for_update else qs.first()

    return None

@login_required
def dashboard(request):
    entregas = BeneficioEntregado.objects.all()
    pendientes = entregas.filter(status='Pendiente').count()
    entregados_qs = entregas.filter(status='Entregado')
    entregados = entregados_qs.count()
     
    total_articulos = entregados_qs.aggregate(total=Sum('cantidad_dada'))['total'] or 0
    recientes = BeneficioEntregado.objects.all().order_by('-id')[:5]
     
    lista_recientes = [{
        'nombre_beneficiario': r.nombre_beneficiario,
        'descripcion_prod': r.descripcion_prod,
        'fecha': r.fecha
    } for r in recientes]
     
    resumen_productos = entregas.values('descripcion_prod').annotate(total_cant=Sum('cantidad_dada')).order_by('-total_cant')
    nombres_productos = [item['descripcion_prod'] or 'Desconocido' for item in resumen_productos]
    cantidades_productos = [int(item['total_cant'] or 0) for item in resumen_productos]

    from SIA.views import obtener_datos_estadisticas_entregas
    import json
    stats_entregas_init = obtener_datos_estadisticas_entregas(filtro='7d', status_filtro='Entregado')

    context = {
        'pendientes': pendientes, 
        'entregados': entregados, 
        'total_articulos': total_articulos,
        'recientes': lista_recientes,
        'nombres_productos': nombres_productos, 
        'cantidades_productos': cantidades_productos,
        'stats_entregas_init_json': json.dumps(stats_entregas_init),
    }
    return render(request, 'dashboard.html', context)

@login_required
def registrar_entrega(request):
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and not perfil.permiso_entregas:
            messages.error(request, "Acceso restringido: No tienes permiso para acceder al módulo de Entregas.")
            return redirect(obtener_url_inicio_usuario(request.user))
    if request.method == 'POST':
        cedula = request.POST.get('cedula', '').strip()
        nombre_beneficiario = request.POST.get('nombre_beneficiario', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        codigo_prod = request.POST.get('codigo_prod', '').strip()
        firma_data = request.POST.get('firma_data', '')
        huella_data = request.POST.get('huella_data', '').strip()
        via = request.POST.get('via', '').strip()
        status = request.POST.get('status', '').strip()
        fecha_input = request.POST.get('fecha', '').strip()
        solicitud_id_input = request.POST.get('solicitud_id', '').strip()

        # 0. Validación de Campos Obligatorios
        if not cedula or not nombre_beneficiario or not direccion or not telefono or not codigo_prod or not via or not fecha_input:
            messages.error(request, "Todos los campos del formulario marcados con (*) son obligatorios. Únicamente la firma digital y las fotos de evidencia son opcionales.")
            return redirect('asignar_beneficio')

        # 1. Validación de Duplicidad y Control de Autorización Administradora
        es_admin = request.user.is_superuser
        entrega_previa_cedula = BeneficioEntregado.objects.filter(cedula=cedula).exists()
        
        conflicto_telefono = None
        if telefono:
            conflicto_telefono = Beneficiario.objects.filter(
                telefono=telefono,
                cedula__in=BeneficioEntregado.objects.values('cedula')
            ).exclude(cedula=cedula).first()

        if entrega_previa_cedula or conflicto_telefono:
            if not es_admin:
                if entrega_previa_cedula:
                    msg = f"Acceso restringido: El beneficiario con Cédula {cedula} ya posee un beneficio asignado previamente. Para registrar un nuevo beneficio a este ciudadano se requiere la autorización de un usuario Administrador."
                else:
                    msg = f"Acceso restringido: El número de teléfono {telefono} pertenece a {conflicto_telefono.nombre_apellido} (C.I. {conflicto_telefono.cedula}), quien ya recibió un beneficio. Se requiere la autorización de un Administrador."
                messages.error(request, msg)
                return redirect('asignar_beneficio')

        try:
            cantidad_dada = int(request.POST.get('cantidad_dada', 0))
        except (ValueError, TypeError):
            cantidad_dada = 0

        fecha_a_guardar = parse_date_safe(fecha_input) or date.today()

        # Subida de evidencias a Cloudinary / almacenamiento local FUERA de la transacción de base de datos
        # Esto previene bloqueos de concurrencia e idle-in-transaction mientras se transmiten fotos por la red.
        url_evidencia_1_str = None
        url_evidencia_2_str = None
        url_evidencia_3_str = None
  
        if request.FILES.get('evidencia1'):
            url_evidencia_1_str = subir_archivo_evidencia_seguro(request.FILES['evidencia1'], request)
  
        # En estado 'Entregado' se permite cargar hasta las 3 evidencias.
        # En estado 'Pendiente' únicamente se procesa y permite 1 evidencia de respaldo.
        if status == "Entregado":
            if request.FILES.get('evidencia2'):
                url_evidencia_2_str = subir_archivo_evidencia_seguro(request.FILES['evidencia2'], request)

            if request.FILES.get('evidencia3'):
                url_evidencia_3_str = subir_archivo_evidencia_seguro(request.FILES['evidencia3'], request)

        # Transacción de base de datos atómica y ultrarrápida (< 5ms)
        with transaction.atomic():
            # Búsqueda unívoca e inequívoca del producto con bloqueo pesimista SOLAMENTE de esa fila
            producto = None
            if codigo_prod:
                if codigo_prod.isdigit():
                    producto = SIA_producto.objects.select_for_update().filter(id=int(codigo_prod)).first()
                if not producto:
                    producto = SIA_producto.objects.select_for_update().filter(codigo=codigo_prod).first()
            
            if not producto:
                messages.error(request, "El producto seleccionado no existe en el inventario.")
                return redirect('asignar_beneficio')
      
            stock_actual = producto.cantidad
            descripcion_prod = producto.descripcion
      
            if status == "Entregado":
                if stock_actual < cantidad_dada:
                    messages.error(request, f"Stock insuficiente para '{descripcion_prod}'. Stock disponible actual: {stock_actual} u.")
                    return redirect('asignar_beneficio')
                producto.cantidad = stock_actual - cantidad_dada
                producto.save(update_fields=['cantidad'])

            Beneficiario.objects.update_or_create(
                cedula=cedula,
                defaults={
                    'nombre_apellido': nombre_beneficiario,
                    'direccion': direccion,
                    'telefono': telefono
                }
            )

            fecha_entrega = None
            if status == "Entregado":
                fecha_entrega_input = request.POST.get('fecha_entrega', '').strip()
                fecha_entrega = parse_date_safe(fecha_entrega_input) or date.today()

            entrega = BeneficioEntregado.objects.create(
                producto=producto,
                cedula=cedula,
                nombre_beneficiario=nombre_beneficiario,
                codigo_prod=producto.codigo,
                descripcion_prod=descripcion_prod,
                cantidad_dada=cantidad_dada,
                via=via,
                fecha=fecha_a_guardar,
                fecha_entrega=fecha_entrega,
                status=status,
                url_evidencia_1=url_evidencia_1_str,
                url_evidencia_2=url_evidencia_2_str if status == "Entregado" else None,
                url_evidencia_3=url_evidencia_3_str if status == "Entregado" else None,
                firma_beneficiario=firma_data if firma_data.strip() else None,
                huella_dactilar=huella_data if huella_data else None
            )

            # Sincronización automática de estado con el Módulo de Atención al Ciudadano
            sincronizar_estado_solicitud(entrega, status, solicitud_id_input)

            RegistroAuditoria.objects.create(
                usuario=request.user,
                accion=f"Registro de entrega #{entrega.id} '{descripcion_prod}' ({cantidad_dada} u.) a {nombre_beneficiario} (C.I.: {cedula}) estado '{status}'.",
                modulo="Entregas",
                timestamp=timezone.now()
            )
        
        messages.success(request, "Registro de entrega guardado correctamente.")
        return redirect('asignar_beneficio')
    else:
        lista_inventario = list(SIA_producto.objects.values('id', 'codigo', 'descripcion', 'almacen', 'cantidad'))
        
        solicitud_id = request.GET.get('solicitud_id', '').strip()
        tipo_solicitud = request.GET.get('tipo_solicitud', '').strip()
        cedula_param = request.GET.get('cedula', '').strip()

        return render(request, 'asignar_beneficio.html', {
            'inventario': lista_inventario, 
            'hoy': date.today().strftime("%Y-%m-%d"),
            'solicitud_id': solicitud_id,
            'tipo_solicitud': tipo_solicitud,
            'cedula_param': cedula_param
        })

@login_required
def verificar_beneficio(request):
    cedula = request.GET.get('cedula', '').strip()
    telefono = request.GET.get('telefono', '').strip()
    es_admin = request.user.is_superuser

    # 1. Cédula ya posee un beneficio
    if cedula and BeneficioEntregado.objects.filter(cedula=cedula).exists():
        if not es_admin:
            return JsonResponse({
                'bloqueado': True,
                'ya_tiene_beneficio': True,
                'es_admin': False,
                'mensaje': f'🛑 ACCESO RESTRINGIDO: La Cédula {cedula} ya posee entregas registradas previamente. Para asignarle un nuevo beneficio se requiere la autorización de un usuario Administrador.'
            })
        else:
            return JsonResponse({
                'bloqueado': False,
                'ya_tiene_beneficio': True,
                'es_admin': True,
                'mensaje': f'👑 AUTORIZACIÓN DE ADMINISTRADOR ACTIVA: La Cédula {cedula} registra entregas previas. Como Administrador del sistema, estás facultado para autorizar un beneficio adicional.'
            })

    # 2. Teléfono pertenece a otra persona con beneficio
    if telefono:
        conflicto = Beneficiario.objects.filter(
            telefono=telefono, 
            cedula__in=BeneficioEntregado.objects.values('cedula')
        ).exclude(cedula=cedula).first()
        
        if conflicto:
            if not es_admin:
                return JsonResponse({
                    'bloqueado': True,
                    'ya_tiene_beneficio': True,
                    'es_admin': False,
                    'mensaje': f'🛑 ACCESO RESTRINGIDO: El teléfono {telefono} pertenece a {conflicto.nombre_apellido} (C.I. {conflicto.cedula}), quien ya recibió un beneficio. Se requiere autorización de un Administrador.'
                })
            else:
                return JsonResponse({
                    'bloqueado': False,
                    'ya_tiene_beneficio': True,
                    'es_admin': True,
                    'mensaje': f'👑 AUTORIZACIÓN DE ADMINISTRADOR ACTIVA: El teléfono {telefono} pertenece a {conflicto.nombre_apellido} (C.I. {conflicto.cedula}), quien registra entregas anteriores. Como Administrador, autorizas esta entrega.'
                })

    return JsonResponse({'bloqueado': False, 'ya_tiene_beneficio': False, 'es_admin': es_admin})

@login_required
def confirmar_entrega(request, entrega_id):
    if request.method == 'POST' and request.FILES.get('evidencia'):
        try:
            url_foto = subir_archivo_evidencia_seguro(request.FILES['evidencia'], request)
             
            with transaction.atomic():
                entrega = BeneficioEntregado.objects.select_for_update().get(id=entrega_id)
                 
                if entrega.status == 'Pendiente':
                    producto = obtener_producto_de_entrega(entrega, for_update=True)
                    
                    if producto:
                        if producto.cantidad < entrega.cantidad_dada:
                            messages.error(request, f"Stock insuficiente para confirmar entrega. Disponible: {producto.cantidad}")
                            return redirect('historial')
                        producto.cantidad -= entrega.cantidad_dada
                        producto.save(update_fields=['cantidad'])
                        if not entrega.producto_id:
                            entrega.producto = producto
                 
                if not entrega.url_evidencia_1:
                    entrega.url_evidencia_1 = url_foto
                elif not entrega.url_evidencia_2:
                    entrega.url_evidencia_2 = url_foto
                else:
                    entrega.url_evidencia_3 = url_foto
      
                entrega.status = "Entregado"
                fecha_entrega_input = request.POST.get('fecha_entrega', '').strip()
                fecha_equipo = parse_date_safe(fecha_entrega_input) or date.today()
                if not getattr(entrega, 'fecha_entrega', None):
                    entrega.fecha_entrega = fecha_equipo
                entrega.save()

                # Sincronización automática de estado con el Módulo de Atención al Ciudadano
                sincronizar_estado_solicitud(entrega, "Entregado")

                RegistroAuditoria.objects.create(
                    usuario=request.user,
                    accion=f"Confirmación de entrega #{entrega.id} para {entrega.nombre_beneficiario} con carga de evidencia fotográfica.",
                    modulo="Entregas",
                    timestamp=timezone.now()
                )
            
            messages.success(request, "Evidencia agregada correctamente.")
        except Exception as e:
            messages.error(request, f"Error al subir evidencia: {str(e)}")
    else:
        messages.error(request, "No se seleccionó ninguna imagen.")
    return redirect('historial')

@login_required
def historial_entregas(request):
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and not perfil.permiso_entregas:
            messages.error(request, "Acceso restringido: No tienes permiso para acceder al Historial de Entregas.")
            return redirect(obtener_url_inicio_usuario(request.user))
    status_filtro = request.GET.get('status', 'Todos').strip()
    fecha_inicio_raw = request.GET.get('fecha_inicio', '').strip()
    fecha_fin_raw = request.GET.get('fecha_fin', '').strip()
    
    entregas = BeneficioEntregado.objects.all().order_by('-id')

    if status_filtro and status_filtro != 'Todos':
        entregas = entregas.filter(status=status_filtro)
        
    fecha_inicio_val = parse_date_safe(fecha_inicio_raw)
    if fecha_inicio_val:
        try:
            entregas = entregas.filter(fecha__gte=fecha_inicio_val)
        except Exception as e:
            logger.warning(f"Error al filtrar entregas por fecha_inicio: {e}")

    fecha_fin_val = parse_date_safe(fecha_fin_raw)
    if fecha_fin_val:
        try:
            entregas = entregas.filter(fecha__lte=fecha_fin_val)
        except Exception as e:
            logger.warning(f"Error al filtrar entregas por fecha_fin: {e}")
  
    lista_entregas = []
    for e in entregas:
        fecha_legible = 'N/A'
        if e.fecha:
            try:
                fecha_legible = e.fecha.strftime('%d/%m/%Y')
            except AttributeError:
                fecha_legible = str(e.fecha)

        fecha_entrega_legible = ''
        if getattr(e, 'fecha_entrega', None):
            try:
                fecha_entrega_legible = e.fecha_entrega.strftime('%d/%m/%Y')
            except AttributeError:
                fecha_entrega_legible = str(e.fecha_entrega)
        elif e.status == 'Entregado' and e.fecha:
            try:
                fecha_entrega_legible = e.fecha.strftime('%d/%m/%Y')
            except AttributeError:
                fecha_entrega_legible = str(e.fecha)

        urls = []
        if e.url_evidencia_1:
            urls.append(e.url_evidencia_1)
        if e.url_evidencia_2:
            urls.append(e.url_evidencia_2)
        if getattr(e, 'url_evidencia_3', None):
            urls.append(e.url_evidencia_3)

        data = {
            'id': e.id,
            'cedula': e.cedula,
            'nombre_beneficiario': e.nombre_beneficiario,
            'descripcion_prod': e.descripcion_prod,
            'cantidad_dada': e.cantidad_dada,
            'via': e.via or 'Atención Directa',
            'status': e.status,
            'url_evidencia_1': e.url_evidencia_1,
            'url_evidencia_2': e.url_evidencia_2,
            'url_evidencia_3': getattr(e, 'url_evidencia_3', None),
            'urls_evidencia': urls,
            'fecha_legible': fecha_legible,
            'fecha_entrega': getattr(e, 'fecha_entrega', None),
            'fecha_entrega_legible': fecha_entrega_legible,
            'tiene_firma': bool(e.firma_beneficiario),
            'firma_beneficiario': e.firma_beneficiario or '',
            'huella_dactilar': getattr(e, 'huella_dactilar', None) or '',
            'firma_hash': generar_hash_firma_digital(e)
        }
        lista_entregas.append(data)
  
    per_page_raw = request.GET.get('per_page', '50').strip()
    try:
        per_page = int(per_page_raw)
        if per_page not in [15, 30, 50, 100]:
            per_page = 50
    except ValueError:
        per_page = 50

    page_number = request.GET.get('page', 1)
    paginator = Paginator(lista_entregas, per_page)
    page_obj = paginator.get_page(page_number)

    # Enriquecer los items de la página con teléfono y dirección desde Beneficiario
    cedulas_pagina = [item['cedula'] for item in page_obj.object_list if item.get('cedula')]
    bens_map = {b.cedula: b for b in Beneficiario.objects.filter(cedula__in=cedulas_pagina)}
    for item in page_obj.object_list:
        ben = bens_map.get(item.get('cedula'))
        item['telefono'] = (ben.telefono or '') if ben else ''
        item['direccion'] = (ben.direccion or '') if ben else ''

    return render(request, 'historial.html', {
        'entregas': page_obj.object_list, 
        'page_obj': page_obj,
        'status_actual': status_filtro,
        'fecha_inicio': fecha_inicio_raw,
        'fecha_fin': fecha_fin_raw,
        'per_page': per_page
    })

@login_required
def exportar_historial_excel(request):
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and not perfil.permiso_entregas:
            messages.error(request, "Acceso restringido: No tienes permiso para exportar el Historial de Entregas.")
            return redirect(obtener_url_inicio_usuario(request.user))

    fecha_inicio_raw = request.GET.get('fecha_inicio', '').strip()
    fecha_fin_raw = request.GET.get('fecha_fin', '').strip()
    status_filtro = request.GET.get('status', 'Todos').strip()

    entregas = BeneficioEntregado.objects.all().order_by('-id')

    if status_filtro and status_filtro != 'Todos':
        entregas = entregas.filter(status=status_filtro)
        
    fecha_inicio_val = parse_date_safe(fecha_inicio_raw)
    if fecha_inicio_val:
        try:
            entregas = entregas.filter(fecha__gte=fecha_inicio_val)
        except Exception as e:
            logger.warning(f"Error al filtrar entregas en Excel por fecha_inicio: {e}")

    fecha_fin_val = parse_date_safe(fecha_fin_raw)
    if fecha_fin_val:
        try:
            entregas = entregas.filter(fecha__lte=fecha_fin_val)
        except Exception as e:
            logger.warning(f"Error al filtrar entregas en Excel por fecha_fin: {e}")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Historial Entregas"

    ws.merge_cells('A1:F1')
    ws['A1'] = "SIA WEB - HISTORIAL GENERAL DE ENTREGAS"
    ws['A1'].font = Font(name='Calibri', size=14, bold=True, color="FFFFFF")
    ws['A1'].fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    headers = ["Fecha Registro", "Fecha Entrega", "Cédula", "Beneficiario", "Producto", "Cantidad", "Estado", "Observaciones / Vía"]
    ws.append(headers)
    ws.row_dimensions[2].height = 24

    header_fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")
    header_font = Font(name='Calibri', size=11, bold=True, color="FFFFFF")

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, e in enumerate(entregas, start=3):
        fecha_reg_str = e.fecha.strftime('%d/%m/%Y') if e.fecha else 'N/A'
        fecha_ent_str = e.fecha_entrega.strftime('%d/%m/%Y') if getattr(e, 'fecha_entrega', None) else (fecha_reg_str if e.status == 'Entregado' else 'Pendiente')
        via_str = e.via or 'Atención Directa'
        ws.append([fecha_reg_str, fecha_ent_str, e.cedula, e.nombre_beneficiario, e.descripcion_prod, e.cantidad_dada, e.status, via_str])
        ws.cell(row=row_idx, column=1).alignment = Alignment(horizontal="center")
        ws.cell(row=row_idx, column=2).alignment = Alignment(horizontal="center")
        ws.cell(row=row_idx, column=3).alignment = Alignment(horizontal="center")
        ws.cell(row=row_idx, column=6).alignment = Alignment(horizontal="center")
        ws.cell(row=row_idx, column=7).alignment = Alignment(horizontal="center")

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Reporte_Historial_Entregas.xlsx"'
    wb.save(response)
    return response

from core.views import obtener_url_publica_comprobante

def ver_comprobante_entrega_publico(request, entrega_id):
    entrega = get_object_or_404(BeneficioEntregado, id=entrega_id)
    
    evidencias = []
    if entrega.url_evidencia_1 and entrega.url_evidencia_1 not in evidencias:
        evidencias.append(entrega.url_evidencia_1)
    if entrega.url_evidencia_2 and entrega.url_evidencia_2 not in evidencias:
        evidencias.append(entrega.url_evidencia_2)
    if getattr(entrega, 'url_evidencia_3', None) and entrega.url_evidencia_3 not in evidencias:
        evidencias.append(entrega.url_evidencia_3)
        
    if entrega.cedula:
        otras = BeneficioEntregado.objects.filter(cedula=entrega.cedula).order_by('-id')
        for e in otras:
            if e.url_evidencia_1 and e.url_evidencia_1 not in evidencias:
                evidencias.append(e.url_evidencia_1)
            if e.url_evidencia_2 and e.url_evidencia_2 not in evidencias:
                evidencias.append(e.url_evidencia_2)
            if getattr(e, 'url_evidencia_3', None) and e.url_evidencia_3 not in evidencias:
                evidencias.append(e.url_evidencia_3)

    url_base = obtener_url_publica_comprobante(request, custom_path=f"/comprobante/entrega/{entrega.id}/")
    firma_hash = generar_hash_firma_digital(entrega)

    return render(request, 'entregas/comprobante_publico.html', {
        'entrega': entrega,
        'evidencias': evidencias,
        'qr_comprobante_url': url_base,
        'firma_hash': firma_hash
    })

def generar_comprobante_pdf(request, entrega_id):
    entrega = get_object_or_404(BeneficioEntregado, id=entrega_id)
    firma_local_path = None
    huella_local_path = None

    if entrega.firma_beneficiario and 'base64,' in entrega.firma_beneficiario:
        try:
            format_str, imgstr = entrega.firma_beneficiario.split(';base64,')
            ext = format_str.split('/')[-1] if '/' in format_str else 'png'
            data_bytes = base64.b64decode(imgstr)
            if len(data_bytes) > 200:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}')
                temp_file.write(data_bytes)
                temp_file.close()
                firma_local_path = temp_file.name
        except Exception:
            firma_local_path = None

    if getattr(entrega, 'huella_dactilar', None) and 'base64,' in entrega.huella_dactilar:
        try:
            format_str, imgstr = entrega.huella_dactilar.split(';base64,')
            ext = format_str.split('/')[-1] if '/' in format_str else 'png'
            data_bytes = base64.b64decode(imgstr)
            if len(data_bytes) > 200:
                temp_file_h = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}')
                temp_file_h.write(data_bytes)
                temp_file_h.close()
                huella_local_path = temp_file_h.name
        except Exception:
            huella_local_path = None

    qr_comprobante_url = obtener_url_publica_comprobante(request, custom_path=f"/comprobante/entrega/{entrega.id}/")
    firma_hash = generar_hash_firma_digital(entrega)

    context = {
        'entrega': entrega,
        'firma_local_path': firma_local_path,
        'huella_local_path': huella_local_path,
        'qr_comprobante_url': qr_comprobante_url,
        'firma_hash': firma_hash
    }

    html = render_to_string('reportes/comprobante_pdf.html', context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Comprobante_{entrega.id}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)

    if firma_local_path and os.path.exists(firma_local_path):
        try:
            os.remove(firma_local_path)
        except OSError:
            pass

    if huella_local_path and os.path.exists(huella_local_path):
        try:
            os.remove(huella_local_path)
        except OSError:
            pass

    if pisa_status.err:
        return HttpResponse('Error al generar PDF del comprobante', status=500)
        
    return response

@login_required
def generar_reporte_mensual_pdf(request):
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and not perfil.permiso_entregas:
            messages.error(request, "Acceso restringido: No tienes permiso para generar el reporte mensual de entregas.")
            return redirect(obtener_url_inicio_usuario(request.user))
    hoy = date.today()
    try:
        mes = int(request.GET.get('mes', hoy.month))
    except ValueError:
        mes = hoy.month
        
    try:
        anio = int(request.GET.get('anio', hoy.year))
    except ValueError:
        anio = hoy.year

    nombres_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_nombre = nombres_meses[mes - 1]

    entregas_mes = BeneficioEntregado.objects.filter(
        fecha__month=mes,
        fecha__year=anio
    ).order_by('-fecha')

    total_entregas = entregas_mes.count()
    total_articulos = entregas_mes.aggregate(total=Sum('cantidad_dada'))['total'] or 0
    total_beneficiarios = entregas_mes.values('cedula').distinct().count()

    resumen_productos = list(entregas_mes.values('descripcion_prod').annotate(total_cant=Sum('cantidad_dada')).order_by('-total_cant'))

    context = {
        'mes_nombre': mes_nombre,
        'anio': anio,
        'total_entregas': total_entregas,
        'total_articulos': total_articulos,
        'total_beneficiarios': total_beneficiarios,
        'resumen_productos': resumen_productos,
        'entregas_mes': entregas_mes[:60]
    }

    html = render_to_string('reportes/reporte_mensual_pdf.html', context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Reporte_Ejecutivo_{mes_nombre}_{anio}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF del reporte ejecutivo', status=500)
        
    return response

@login_required
def api_buscar_beneficiario_autocomplete(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'resultados': []})
    
    beneficiarios = Beneficiario.objects.filter(
        Q(cedula__icontains=q) | Q(nombre_apellido__icontains=q)
    )[:10]

    resultados = [{
        'cedula': b.cedula,
        'nombre_apellido': b.nombre_apellido,
        'direccion': b.direccion,
        'telefono': b.telefono
    } for b in beneficiarios]

    return JsonResponse({'resultados': resultados})

@login_required
@transaction.atomic
def eliminar_entrega(request, entrega_id):
    entrega = get_object_or_404(BeneficioEntregado, id=entrega_id)
  
    if request.method == 'POST':
        reponer_stock = 'reponer_stock' in request.POST or request.POST.get('reponer_stock') == 'on'
        
        producto = obtener_producto_de_entrega(entrega, for_update=True)
  
        if reponer_stock:
            if producto:
                producto.cantidad += entrega.cantidad_dada
                producto.save()
                messages.success(request, f"Registro eliminado y stock repuesto: +{entrega.cantidad_dada} u. sumadas a '{producto.descripcion}'. Stock total: {producto.cantidad} u.")
            else:
                messages.warning(request, f"Registro eliminado, pero no se encontró el producto '{entrega.descripcion_prod}' en el inventario para reponer.")
        else:
            messages.success(request, "Registro eliminado exitosamente sin modificar el inventario.")
  
        RegistroAuditoria.objects.create(
            usuario=request.user,
            accion=f"Eliminación de entrega #{entrega.id} correspondiente a {entrega.nombre_beneficiario} ({'con reposición de stock' if reponer_stock else 'sin modificar inventario'}).",
            modulo="Entregas",
            timestamp=timezone.now()
        )

        entrega.delete()
  
    return redirect('historial')

@login_required
@transaction.atomic
def editar_beneficiario_entrega(request, entrega_id):
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if not perfil or not perfil.tiene_permiso('entregas', 'editar'):
            messages.error(request, "Acceso restringido: No tienes permiso para editar entregas.")
            return redirect(obtener_url_inicio_usuario(request.user))

    entrega = get_object_or_404(BeneficioEntregado, id=entrega_id)

    if request.method == 'POST':
        referer = request.META.get('HTTP_REFERER')
        url_retorno = referer if (referer and ('historial' in referer or 'entrega' in referer)) else 'historial'

        cedula_raw = request.POST.get('cedula', '').strip()
        nombre = request.POST.get('nombre_beneficiario', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()

        # Limpieza básica de cédula
        cedula = re.sub(r'[^0-9A-Za-z-]', '', cedula_raw)

        if not cedula or not nombre:
            messages.error(request, "La cédula y el nombre completo del beneficiario son obligatorios.")
            return redirect(url_retorno)

        try:
            cedula_ant = entrega.cedula or ''
            nombre_ant = entrega.nombre_beneficiario or ''

            # 1. Modificar ÚNICAMENTE datos de identidad del beneficiario en la entrega
            entrega.cedula = cedula
            entrega.nombre_beneficiario = nombre
            entrega.save()

            # 2. Actualizar o sincronizar el registro en la tabla Beneficiario
            Beneficiario.objects.update_or_create(
                cedula=cedula,
                defaults={
                    'nombre_apellido': nombre,
                    'telefono': telefono,
                    'direccion': direccion,
                    'timestamp': timezone.now()
                }
            )

            # 3. Sincronizar solicitudes ciudadanas vinculadas si existen
            solicitudes = SolicitudCiudadano.objects.filter(cedula__in=[cedula_ant, cedula])
            for sol in solicitudes:
                sol.cedula = cedula
                sol.nombre_apellido = nombre
                if telefono:
                    sol.telefono = telefono
                if direccion:
                    sol.direccion = direccion
                sol.save()

            # 4. Registrar evento en Auditoría detallando exactamente los campos modificados
            cambios = []
            if cedula_ant != cedula:
                cambios.append(f"Cédula: '{cedula_ant}' ➔ '{cedula}'")
            if nombre_ant != nombre:
                cambios.append(f"Nombre: '{nombre_ant}' ➔ '{nombre}'")
            if telefono:
                cambios.append(f"Teléfono: '{telefono}'")
            if direccion:
                cambios.append(f"Dirección: '{direccion}'")

            detalles_texto = ", ".join(cambios) if cambios else "Sin alteraciones"
            RegistroAuditoria.objects.create(
                usuario=request.user,
                accion=f"Edición de datos de beneficiario en Entrega #{entrega.id} ({entrega.descripcion_prod} x{entrega.cantidad_dada}, Estado: {entrega.status}): {detalles_texto}",
                modulo="Entregas"
            )

            messages.success(request, f"Datos del beneficiario actualizados exitosamente para la entrega #{entrega.id}.")
        except Exception as e:
            logger.error(f"Error al editar beneficiario de entrega #{entrega.id}: {e}", exc_info=True)
            messages.error(request, f"Ocurrió un error al guardar los cambios: {str(e)}")

        return redirect(url_retorno)

    return redirect('historial')

@login_required
@transaction.atomic
def cambiar_estado(request, entrega_id, nuevo_status):
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if not perfil or not perfil.puede_cambiar_estatus_entregas:
            messages.error(request, "Acceso restringido: No tienes permiso para modificar el estado de entregas.")
            return redirect(obtener_url_inicio_usuario(request.user))
    try:
        entrega = BeneficioEntregado.objects.get(id=entrega_id)
        status_anterior = entrega.status
        
        if status_anterior == nuevo_status:
            return redirect('historial')

        producto = obtener_producto_de_entrega(entrega, for_update=True)
        if producto and not entrega.producto_id:
            entrega.producto = producto

        # De Pendiente a Entregado ➔ DESCONTAR del Inventario
        if status_anterior == 'Pendiente' and nuevo_status == 'Entregado':
            if producto:
                if producto.cantidad < entrega.cantidad_dada:
                    messages.error(request, f"Stock insuficiente para cambiar a Entregado. Stock disponible en '{producto.descripcion}': {producto.cantidad} u.")
                    return redirect('historial')
                producto.cantidad -= entrega.cantidad_dada
                producto.save()
                messages.success(request, f"Estado actualizado a 'Entregado'. Se descontaron -{entrega.cantidad_dada} u. de '{producto.descripcion}'. Stock total: {producto.cantidad} u.")
            else:
                messages.warning(request, f"Estado actualizado a 'Entregado', pero no se encontró el producto '{entrega.descripcion_prod}' en el inventario para descontar.")

        # De Entregado a Pendiente o Cancelado ➔ REPONER al Inventario
        elif status_anterior == 'Entregado' and nuevo_status in ['Pendiente', 'Cancelado']:
            if producto:
                producto.cantidad += entrega.cantidad_dada
                producto.save()
                messages.success(request, f"Estado actualizado a '{nuevo_status}'. Se repusieron +{entrega.cantidad_dada} u. a '{producto.descripcion}'. Stock total: {producto.cantidad} u.")
            else:
                messages.warning(request, f"Estado actualizado a '{nuevo_status}', pero no se encontró el producto '{entrega.descripcion_prod}' en el inventario para reponer.")

        fecha_entrega_input = request.POST.get('fecha_entrega', '').strip()
        fecha_equipo = parse_date_safe(fecha_entrega_input) or date.today()

        if nuevo_status == 'Entregado':
            entrega.fecha_entrega = fecha_equipo
        elif nuevo_status == 'Pendiente':
            entrega.fecha_entrega = None

        entrega.status = nuevo_status
        entrega.save()

        # Sincronización automática de estado con el Módulo de Atención al Ciudadano
        sincronizar_estado_solicitud(entrega, nuevo_status)

        RegistroAuditoria.objects.create(
            usuario=request.user,
            accion=f"Cambio de estado en entrega #{entrega.id} ({entrega.nombre_beneficiario}) de '{status_anterior}' a '{nuevo_status}'.",
            modulo="Entregas",
            timestamp=timezone.now()
        )

    except BeneficioEntregado.DoesNotExist:
        messages.error(request, "El registro de entrega no existe.")
         
    return redirect('historial')

@login_required
def buscar_beneficiario(request):
    cedula_raw = request.GET.get('cedula', '').strip()
    cedula = re.sub(r'\D', '', cedula_raw)
    forzar_cne = request.GET.get('forzar_cne', 'false').lower() == 'true'

    if not cedula:
        return JsonResponse({'existe': False, 'error': 'Cédula no especificada'})

    # 1. Historial de entregas previas para esta cédula (independiente de si existe en tabla Beneficiario)
    historial_previo = list(
        BeneficioEntregado.objects.filter(cedula=cedula).values(
            'descripcion_prod', 'cantidad_dada', 'fecha', 'status'
        ).order_by('-fecha')[:5]
    )
    for h in historial_previo:
        h['fecha_str'] = h['fecha'].strftime('%d/%m/%Y') if h['fecha'] else 'N/A'

    # 2. Búsqueda en la base de datos local
    beneficiario = None
    if not forzar_cne:
        beneficiario = Beneficiario.objects.filter(cedula=cedula).first()

    if beneficiario and beneficiario.nombre_apellido and beneficiario.nombre_apellido.strip():
        return JsonResponse({
            'existe': True,
            'origen': 'local',
            'cedula': beneficiario.cedula,
            'nombre_apellido': beneficiario.nombre_apellido,
            'direccion': beneficiario.direccion or '',
            'telefono': beneficiario.telefono or '',
            'historial_previo': historial_previo
        })

    # 3. Si no existe en la base de datos local o se forzó búsqueda en CNE: consultar sistemaspnp.com
    datos_externos = consultar_cedula_sistemaspnp(cedula)
    if datos_externos and datos_externos.get('nombre_completo'):
        nombre_completo = datos_externos['nombre_completo']
        direccion_sugerida = beneficiario.direccion if (beneficiario and beneficiario.direccion) else datos_externos.get('direccion_sugerida', '')
        telefono_existente = beneficiario.telefono if beneficiario else ''

        return JsonResponse({
            'existe': True,
            'origen': 'sistemaspnp',
            'cedula': cedula,
            'nombre_apellido': nombre_completo,
            'direccion': direccion_sugerida,
            'telefono': telefono_existente,
            'historial_previo': historial_previo,
            'datos_cne': datos_externos
        })

    # Si no se encontró en CNE pero existía localmente
    if beneficiario:
        return JsonResponse({
            'existe': True,
            'origen': 'local',
            'cedula': beneficiario.cedula,
            'nombre_apellido': beneficiario.nombre_apellido,
            'direccion': beneficiario.direccion or '',
            'telefono': beneficiario.telefono or '',
            'historial_previo': historial_previo
        })

    return JsonResponse({'existe': False, 'error': 'No encontrado'})

@login_required
@transaction.atomic
def registrar_asignacion_especial(request):
    if request.method == 'POST':
        nombre_receptor = request.POST.get('nombre_receptor')
        departamento_o_cargo = request.POST.get('departamento_o_cargo')
        
        productos_ids = request.POST.getlist('productos[]')
        cantidades = request.POST.getlist('cantidades[]')

        if not productos_ids:
            messages.error(request, "Debe agregar al menos un producto.")
            return redirect('registrar_asignacion')

        try:
            asignacion = AsignacionEspecial.objects.create(
                nombre_receptor=nombre_receptor,
                departamento_o_cargo=departamento_o_cargo,
                registrado_por=request.user
            )

            for i in range(len(productos_ids)):
                prod_id = productos_ids[i]
                cant_dada = int(cantidades[i])
                
                producto = SIA_producto.objects.get(id=prod_id)
                
                if producto.cantidad >= cant_dada:
                    producto.cantidad -= cant_dada
                    producto.save()
                else:
                    raise Exception(f"Stock insuficiente para el producto {producto.descripcion}")

                DetalleAsignacionEspecial.objects.create(
                    asignacion=asignacion,
                    descripcion_prod=producto.descripcion,
                    cantidad=cant_dada
                )

            RegistroAuditoria.objects.create(
                usuario=request.user,
                accion=f"Creación de asignación especial para {nombre_receptor} ({departamento_o_cargo})",
                modulo="Entregas",
                timestamp=timezone.now()
            )

            messages.success(request, "Asignación especial guardada correctamente.")
            return redirect('lista_asignaciones_especiales')
            
        except Exception as e:
            messages.error(request, f"Error al guardar la asignación: {str(e)}")
            return redirect('registrar_asignacion')

    productos = SIA_producto.objects.all()
    return render(request, 'entregas/registrar_asignacion.html', {'productos': productos})

@login_required
def lista_asignaciones_especiales(request):
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and not perfil.permiso_asignaciones_especiales:
            messages.error(request, "Acceso restringido: No tienes permiso para acceder al módulo de Asignaciones Especiales.")
            return redirect(obtener_url_inicio_usuario(request.user))

    asignaciones = AsignacionEspecial.objects.all().order_by('-fecha')
    return render(request, 'entregas/asignaciones_especiales.html', {'asignaciones': asignaciones})

@login_required
@transaction.atomic
def eliminar_asignacion_especial(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "No tienes permisos de superusuario para eliminar esta asignación.")
        return redirect('lista_asignaciones_especiales')
        
    asignacion = get_object_or_404(AsignacionEspecial, id=pk)
  
    if request.method == 'POST':
        reponer_stock = request.POST.get('reponer_stock') == 'on'
  
        if reponer_stock:
            try:
                for detalle in asignacion.detalles.all():
                    producto = SIA_producto.objects.filter(descripcion=detalle.descripcion_prod).first()
                    if producto:
                        producto.cantidad += detalle.cantidad
                        producto.save()
                messages.success(request, "Asignación eliminada y stock repuesto exitosamente.")
            except Exception as e:
                messages.warning(request, f"La asignación se eliminó, pero hubo un error al reponer el stock: {str(e)}")
        else:
            messages.success(request, "Asignación eliminada exitosamente sin modificar el inventario.")
  
        RegistroAuditoria.objects.create(
            usuario=request.user,
            accion=f"Eliminación de asignación especial #{asignacion.id} de {asignacion.nombre_receptor}",
            modulo="Entregas",
            timestamp=timezone.now()
        )
        
        asignacion.delete()
  
    return redirect('lista_asignaciones_especiales')

def imprimir_asignacion_especial(request, pk):
    asignacion = get_object_or_404(AsignacionEspecial, id=pk)
    firma_hash = generar_hash_firma_digital(asignacion)
    return render(request, 'entregas/reporte_asignacion_especial.html', {
        'asignacion': asignacion,
        'firma_hash': firma_hash
    })
