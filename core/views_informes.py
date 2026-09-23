import os
import io
import ssl
import json
import base64
import urllib.request
import urllib.parse
from datetime import date, timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q, Max, Value
from django.db.models.functions import Coalesce, Trim, Cast
from PIL import Image, ImageDraw
from xhtml2pdf import pisa

from entregas.models import BeneficioEntregado
from core.models import SolicitudCiudadano, ConfiguracionInstitucion
from core.utils import parse_date_safe, obtener_logos_base64, generar_hash_firma_digital, obtener_url_inicio_usuario

# Bypass SSL para recursos en Windows / xhtml2pdf
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

def calcular_datos_informe(periodo='semanal', fecha_str=None, fecha_inicio_str=None, fecha_fin_str=None):
    """
    Consolida, procesa y concatena la información de Beneficios Entregados y Solicitudes
    tanto en estatus PENDIENTE como ENTREGADO, calculando métricas, series temporales,
    diagnóstico institucional y texto ejecutivo redactado.
    """
    hoy = timezone.localdate() if hasattr(timezone, 'localdate') else date.today()
    
    fecha_desde = None
    fecha_hasta = hoy
    subtitulo_periodo = ""
    periodo_nombre = ""

    # 1. Determinación del Rango de Fechas
    if periodo == 'diario':
        d_esp = parse_date_safe(fecha_str) if fecha_str else hoy
        fecha_desde = d_esp or hoy
        fecha_hasta = fecha_desde
        periodo_nombre = "Informe Diario"
        subtitulo_periodo = f"Jornada del {fecha_desde.strftime('%d/%m/%Y')}"
    elif periodo == 'semanal':
        fecha_desde = hoy - timedelta(days=6)
        fecha_hasta = hoy
        periodo_nombre = "Informe Semanal"
        subtitulo_periodo = f"Semana del {fecha_desde.strftime('%d/%m/%Y')} al {fecha_hasta.strftime('%d/%m/%Y')}"
    elif periodo == 'mensual':
        if fecha_str:
            d_mes = parse_date_safe(fecha_str)
            if d_mes:
                fecha_desde = date(d_mes.year, d_mes.month, 1)
                sig_mes = date(d_mes.year + 1, 1, 1) if d_mes.month == 12 else date(d_mes.year, d_mes.month + 1, 1)
                fecha_hasta = sig_mes - timedelta(days=1)
            else:
                fecha_desde = date(hoy.year, hoy.month, 1)
                fecha_hasta = hoy
        else:
            fecha_desde = date(hoy.year, hoy.month, 1)
            fecha_hasta = hoy
        periodo_nombre = "Informe Mensual"
        meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        nombre_mes = meses_nombres[fecha_desde.month - 1]
        subtitulo_periodo = f"Mes de {nombre_mes} de {fecha_desde.year} ({fecha_desde.strftime('%d/%m')} al {fecha_hasta.strftime('%d/%m')})"
    elif periodo == 'personalizado':
        d_ini = parse_date_safe(fecha_inicio_str)
        d_fin = parse_date_safe(fecha_fin_str)
        if d_ini:
            fecha_desde = d_ini
        if d_fin:
            fecha_hasta = d_fin
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
        periodo_nombre = "Informe por Rango Personalizado"
        subtitulo_periodo = f"Período: {fecha_desde.strftime('%d/%m/%Y') if fecha_desde else 'Histórico'} al {fecha_hasta.strftime('%d/%m/%Y') if fecha_hasta else 'Presente'}"
    else: # total
        periodo = 'total'
        fecha_desde = None
        fecha_hasta = None
        periodo_nombre = "Informe General Consolidado"
        subtitulo_periodo = "Histórico Total Acumulado en el Sistema"

    # 2. Querysets Base de Beneficios (entregas.BeneficioEntregado)
    base_beneficios = BeneficioEntregado.objects.annotate(
        status_clean=Trim('status'),
        fecha_efectiva=Coalesce(
            'fecha',
            'fecha_entrega',
            Cast('timestamp', output_field=models.DateField()),
            output_field=models.DateField()
        )
    )

    # Entregados: filtrados estrictamente por el rango de fechas del período seleccionado
    beneficios_entregados_qs = base_beneficios.filter(status_clean__iexact='Entregado')
    if fecha_desde:
        beneficios_entregados_qs = beneficios_entregados_qs.filter(fecha_efectiva__gte=fecha_desde)
    if fecha_hasta:
        beneficios_entregados_qs = beneficios_entregados_qs.filter(fecha_efectiva__lte=fecha_hasta)

    # Pendientes: evaluados de TODO EN GENERAL (cartera activa acumulada, sin restricción de rango)
    beneficios_pendientes_qs = base_beneficios.filter(
        Q(status_clean__iexact='Pendiente') | Q(status_clean__isnull=True) | ~Q(status_clean__iexact='Entregado')
    )

    beneficios_entregados_count = beneficios_entregados_qs.count()
    beneficios_pendientes_count = beneficios_pendientes_qs.count()
    total_beneficios_count = beneficios_entregados_count + beneficios_pendientes_count

    articulos_entregados_sum = beneficios_entregados_qs.aggregate(t=Sum('cantidad_dada'))['t'] or 0
    articulos_pendientes_sum = beneficios_pendientes_qs.aggregate(t=Sum('cantidad_dada'))['t'] or 0
    total_articulos_sum = articulos_entregados_sum + articulos_pendientes_sum

    beneficiarios_entregados_count = beneficios_entregados_qs.exclude(cedula__isnull=True).exclude(cedula__exact='').values('cedula').distinct().count()
    beneficiarios_pendientes_count = beneficios_pendientes_qs.exclude(cedula__isnull=True).exclude(cedula__exact='').values('cedula').distinct().count()
    total_beneficiarios_unicos = beneficiarios_entregados_count + beneficiarios_pendientes_count

    # 3. Querysets Base de Solicitudes (core.SolicitudCiudadano)
    base_solicitudes = SolicitudCiudadano.objects.annotate(
        fecha_efectiva=Coalesce(
            Cast('fecha_solicitud', output_field=models.DateField()),
            'fecha_entrega',
            output_field=models.DateField()
        )
    )

    # Solicitudes Entregadas: filtradas estrictamente por el rango de fechas
    solicitudes_entregadas_qs = base_solicitudes.filter(status__iexact='Entregada')
    if fecha_desde:
        solicitudes_entregadas_qs = solicitudes_entregadas_qs.filter(fecha_efectiva__gte=fecha_desde)
    if fecha_hasta:
        solicitudes_entregadas_qs = solicitudes_entregadas_qs.filter(fecha_efectiva__lte=fecha_hasta)

    # Solicitudes Pendientes (en trámite/proceso): evaluadas de TODO EN GENERAL
    solicitudes_pendientes_qs = base_solicitudes.filter(
        status__in=['Recibida', 'En Proceso', 'Aprobada']
    )
    solicitudes_rechazadas_qs = base_solicitudes.filter(status__iexact='Rechazada')
    if fecha_desde:
        solicitudes_rechazadas_qs = solicitudes_rechazadas_qs.filter(fecha_efectiva__gte=fecha_desde)
    if fecha_hasta:
        solicitudes_rechazadas_qs = solicitudes_rechazadas_qs.filter(fecha_efectiva__lte=fecha_hasta)

    solicitudes_entregadas_count = solicitudes_entregadas_qs.count()
    solicitudes_pendientes_count = solicitudes_pendientes_qs.count()
    total_solicitudes_count = solicitudes_entregadas_count + solicitudes_pendientes_count

    solicitudes_aprobadas_count = solicitudes_pendientes_qs.filter(status__iexact='Aprobada').count()
    solicitudes_en_proceso_count = solicitudes_pendientes_qs.filter(status__iexact='En Proceso').count()
    solicitudes_recibidas_count = solicitudes_pendientes_qs.filter(status__iexact='Recibida').count()
    solicitudes_rechazadas_count = solicitudes_rechazadas_qs.count()

    # 4. Concatenación de Métricas Totales del Sistema
    gran_total_operaciones = total_beneficios_count + total_solicitudes_count
    gran_total_entregados = beneficios_entregados_count + solicitudes_entregadas_count
    gran_total_pendientes = beneficios_pendientes_count + solicitudes_pendientes_count

    tasa_efectividad_entregas = round((beneficios_entregados_count / total_beneficios_count * 100), 1) if total_beneficios_count > 0 else 0
    tasa_resolucion_solicitudes = round((solicitudes_entregadas_count / total_solicitudes_count * 100), 1) if total_solicitudes_count > 0 else 0
    tasa_efectividad_global = round((gran_total_entregados / gran_total_operaciones * 100), 1) if gran_total_operaciones > 0 else 0

    # 5. Agrupaciones para Gráficos
    # A) Insumos Más Entregados (en período) vs Pendientes (en cartera general)
    prods_entregados_agg = {
        item['descripcion_prod']: item['cant']
        for item in beneficios_entregados_qs.values('descripcion_prod').annotate(cant=Sum('cantidad_dada'))
        if item['descripcion_prod']
    }
    prods_pendientes_agg = {
        item['descripcion_prod']: item['cant']
        for item in beneficios_pendientes_qs.values('descripcion_prod').annotate(cant=Sum('cantidad_dada'))
        if item['descripcion_prod']
    }

    todos_los_prods = set(prods_entregados_agg.keys()) | set(prods_pendientes_agg.keys())
    top_insumos_lista = []
    for desc in todos_los_prods:
        c_ent = prods_entregados_agg.get(desc, 0) or 0
        c_pen = prods_pendientes_agg.get(desc, 0) or 0
        top_insumos_lista.append({
            'descripcion': desc,
            'entregadas': c_ent,
            'pendientes': c_pen,
            'total': c_ent + c_pen
        })
    top_insumos_lista.sort(key=lambda x: x['total'], reverse=True)
    top_insumos_recortado = top_insumos_lista[:7]

    # B) Tipos de Solicitud Ciudadana (Entregadas en período vs Pendientes en general)
    tipos_sol_agg = []
    tipos_unicos = set(solicitudes_entregadas_qs.values_list('tipo_solicitud', flat=True)) | set(solicitudes_pendientes_qs.values_list('tipo_solicitud', flat=True))
    for t_nom in tipos_unicos:
        if not t_nom:
            continue
        c_ent = solicitudes_entregadas_qs.filter(tipo_solicitud=t_nom).count()
        c_pen = solicitudes_pendientes_qs.filter(tipo_solicitud=t_nom).count()
        tipos_sol_agg.append({
            'tipo_solicitud': t_nom,
            'entregadas': c_ent,
            'pendientes': c_pen,
            'total': c_ent + c_pen
        })
    tipos_sol_agg.sort(key=lambda x: x['total'], reverse=True)

    # C) Distribución de Estados Conciliados
    estatus_labels = ['Completados / Entregados', 'En Espera / Pendientes', 'Rechazados']
    estatus_valores = [gran_total_entregados, gran_total_pendientes, solicitudes_rechazadas_count]

    # D) Serie Temporal (Evolución diaria cronológica)
    fechas_labels = []
    fechas_entregados = []
    fechas_pendientes = []
    fechas_solicitudes = []

    if fecha_desde and fecha_hasta and (fecha_hasta - fecha_desde).days <= 60:
        agg_ent = {
            item['fecha_efectiva']: item['cnt']
            for item in beneficios_entregados_qs.values('fecha_efectiva').annotate(cnt=Count('id'))
        }
        agg_pen = {
            item['fecha_efectiva']: item['cnt']
            for item in beneficios_pendientes_qs.values('fecha_efectiva').annotate(cnt=Count('id'))
        }
        agg_sol = {
            item['fecha_efectiva']: item['cnt']
            for item in solicitudes_entregadas_qs.values('fecha_efectiva').annotate(cnt=Count('id'))
        }

        curr = fecha_desde
        while curr <= fecha_hasta:
            fechas_labels.append(curr.strftime('%d/%m'))
            fechas_entregados.append(agg_ent.get(curr, 0))
            fechas_pendientes.append(agg_pen.get(curr, 0))
            fechas_solicitudes.append(agg_sol.get(curr, 0))
            curr += timedelta(days=1)
    else:
        # Modo total o rango muy amplio
        fechas_labels = ['Total Acumulado']
        fechas_entregados = [beneficios_entregados_count]
        fechas_pendientes = [beneficios_pendientes_count]
        fechas_solicitudes = [solicitudes_entregadas_count]

    # 6. Registros Concatenados: Entregas del Período + Cartera General Pendiente
    registros_unificados = []
    
    # A) Entregas correspondientes al período seleccionado
    for b in beneficios_entregados_qs.order_by('-fecha_efectiva', '-id')[:100].values(
        'id', 'nombre_beneficiario', 'cedula', 'descripcion_prod', 'cantidad_dada', 'status_clean', 'fecha_efectiva', 'via'
    ):
        registros_unificados.append({
            'tipo': 'ENTREGA',
            'beneficiario': b['nombre_beneficiario'] or 'No identificado',
            'cedula': b['cedula'] or 'S/C',
            'detalle': b['descripcion_prod'] or 'Insumo de Almacén',
            'cantidad': f"{b['cantidad_dada']} u.",
            'status': 'Entregado',
            'is_entregado': True,
            'fecha': b['fecha_efectiva'],
        })

    for s in solicitudes_entregadas_qs.order_by('-fecha_efectiva', '-id')[:100].values(
        'id', 'nombre_apellido', 'cedula', 'tipo_solicitud', 'prioridad', 'status', 'fecha_efectiva'
    ):
        registros_unificados.append({
            'tipo': 'SOLICITUD',
            'beneficiario': s['nombre_apellido'],
            'cedula': s['cedula'] or 'S/C',
            'detalle': s['tipo_solicitud'],
            'cantidad': '1 caso',
            'status': 'Entregada',
            'is_entregado': True,
            'fecha': s['fecha_efectiva'],
        })

    # B) Cartera general de compromisos pendientes (todo en general sin restricción)
    for b in beneficios_pendientes_qs.order_by('-fecha_efectiva', '-id')[:100].values(
        'id', 'nombre_beneficiario', 'cedula', 'descripcion_prod', 'cantidad_dada', 'status_clean', 'fecha_efectiva', 'via'
    ):
        registros_unificados.append({
            'tipo': 'ENTREGA',
            'beneficiario': b['nombre_beneficiario'] or 'No identificado',
            'cedula': b['cedula'] or 'S/C',
            'detalle': b['descripcion_prod'] or 'Insumo de Almacén',
            'cantidad': f"{b['cantidad_dada']} u.",
            'status': b['status_clean'] or 'Pendiente',
            'is_entregado': False,
            'fecha': b['fecha_efectiva'],
        })

    for s in solicitudes_pendientes_qs.order_by('-fecha_efectiva', '-id')[:100].values(
        'id', 'nombre_apellido', 'cedula', 'tipo_solicitud', 'prioridad', 'status', 'fecha_efectiva'
    ):
        registros_unificados.append({
            'tipo': 'SOLICITUD',
            'beneficiario': s['nombre_apellido'],
            'cedula': s['cedula'] or 'S/C',
            'detalle': s['tipo_solicitud'],
            'cantidad': '1 caso',
            'status': s['status'],
            'is_entregado': False,
            'fecha': s['fecha_efectiva'],
        })

    # Ordenar unificados por fecha estrictamente descendente
    registros_unificados.sort(key=lambda x: (x['fecha'] or date.min), reverse=True)

    recientes_beneficios = list(beneficios_entregados_qs.order_by('-fecha_efectiva', '-id')[:50].values(
        'id', 'nombre_beneficiario', 'cedula', 'descripcion_prod', 'cantidad_dada', 'status_clean', 'fecha_efectiva', 'via'
    )) + list(beneficios_pendientes_qs.order_by('-fecha_efectiva', '-id')[:50].values(
        'id', 'nombre_beneficiario', 'cedula', 'descripcion_prod', 'cantidad_dada', 'status_clean', 'fecha_efectiva', 'via'
    ))

    recientes_solicitudes = list(solicitudes_entregadas_qs.order_by('-fecha_efectiva', '-id')[:50].values(
        'id', 'nombre_apellido', 'cedula', 'tipo_solicitud', 'prioridad', 'status', 'fecha_efectiva'
    )) + list(solicitudes_pendientes_qs.order_by('-fecha_efectiva', '-id')[:50].values(
        'id', 'nombre_apellido', 'cedula', 'tipo_solicitud', 'prioridad', 'status', 'fecha_efectiva'
    ))

    # 7. Redacción Inteligente del Análisis y Diagnóstico Institucional (Texto Ejecutivo)
    # A) Balance General Operativo
    if gran_total_operaciones == 0:
        analisis_balance = (
            f"Durante el período evaluado ({subtitulo_periodo}), no se evidenció actividad ni registros de "
            "nuevas solicitudes ciudadanas o despacho de beneficios en los módulos del sistema. "
            "El sistema se encuentra en estado de espera operativa y listo para la carga de expedientes."
        )
    else:
        analisis_balance = (
            f"En el transcurso del {periodo_nombre.lower()} ({subtitulo_periodo}), se completaron de manera efectiva "
            f"{gran_total_entregados:,} entregas de beneficios ({beneficios_entregados_count:,} asignaciones directas de almacén "
            f"y {solicitudes_entregadas_count:,} solicitudes resueltas). Paralelamente, la cartera general activa de compromisos "
            f"pendientes en todo el sistema acumula {gran_total_pendientes:,} casos en cola total por procesar "
            f"({beneficios_pendientes_count:,} asignaciones de inventario en espera y {solicitudes_pendientes_count:,} solicitudes "
            f"ciudadanas en trámite), representando un universo operativo de {gran_total_operaciones:,} gestiones evaluadas globalmente."
        )

    # B) Diagnóstico de Demanda y Necesidades Sociales
    if total_solicitudes_count > 0:
        top_tipo = tipos_sol_agg[0]['tipo_solicitud'] if tipos_sol_agg else 'Ayuda Social'
        cant_top_tipo = tipos_sol_agg[0]['total'] if tipos_sol_agg else 0
        pct_top_tipo = round((cant_top_tipo / total_solicitudes_count) * 100, 1)
        alta_prioridad = solicitudes_pendientes_qs.filter(prioridad='Alta').count()

        analisis_demanda = (
            f"El diagnóstico de atención al ciudadano revela que el requerimiento con mayor demanda en este período fue "
            f"'{top_tipo}', abarcando {cant_top_tipo} solicitudes ({pct_top_tipo}% del total radicado). "
            f"Asimismo, se identificaron {alta_prioridad} expedientes clasificados en condición de 'Alta Prioridad', "
            f"los cuales demandan intervención preferencial. De las solicitudes recibidas, {solicitudes_entregadas_count} "
            f"ya han culminado con la entrega material del beneficio y {solicitudes_pendientes_count} continúan en seguimiento administrativo."
        )
    else:
        analisis_demanda = (
            "No se registraron cartas ni solicitudes formales de ayuda social ciudadana en el lapso consultado. "
            "La actividad registrada correspondió primordialmente a la logística y distribución directa de almacén."
        )

    # C) Comportamiento de Insumos y Almacén (Entregados vs Pendientes)
    if top_insumos_recortado:
        insumo_mas_despachado = top_insumos_recortado[0]
        analisis_insumos = (
            f"En materia de insumos y recursos de almacén, se movilizaron un total de {total_articulos_sum:,} unidades físicas "
            f"({articulos_entregados_sum:,} unidades efectivamente entregadas y {articulos_pendientes_sum:,} unidades comprometidas en estatus pendiente). "
            f"El renglón con mayor demanda fue '{insumo_mas_despachado['descripcion']}', con un total de "
            f"{insumo_mas_despachado['total']:,} unidades solicitadas ({insumo_mas_despachado['entregadas']:,} entregadas y "
            f"{insumo_mas_despachado['pendientes']:,} pendientes por entregar a beneficiarios)."
        )
    else:
        analisis_insumos = (
            "No se identificó despacho ni compromiso de insumos físicos durante el lapso de tiempo especificado."
        )

    # D) Conclusiones y Recomendaciones Ejecutivas
    recomendaciones = []
    if gran_total_pendientes > 0:
        recomendaciones.append(
            f"Priorizar la agenda de despacho para los {gran_total_pendientes} casos en estatus 'Pendiente', "
            "coordinando con el equipo de almacén para verificar la disponibilidad física inmediata."
        )
    if articulos_pendientes_sum > 0:
        recomendaciones.append(
            f"Asegurar la reserva de inventario para las {articulos_pendientes_sum:,} unidades de artículos comprometidos "
            "a fin de evitar quiebres de stock antes de concretar las entregas programadas."
        )
    if total_solicitudes_count > 0 and solicitudes_recibidas_count > 0:
        recomendaciones.append(
            f"Agilizar la evaluación técnica y social de las {solicitudes_recibidas_count} solicitudes que aún permanecen "
            "en estatus 'Recibida' para dictaminar su aprobación y asignación correspondiente."
        )
    if not recomendaciones:
        recomendaciones.append(
            "Mantener el ritmo continuo de atención y los protocolos de auditoría vigentes. "
            "Todos los casos tramitados en el período han sido solventados con efectividad plena."
        )

    analisis_recomendaciones = " ".join(recomendaciones)

    return {
        'periodo': periodo,
        'periodo_nombre': periodo_nombre,
        'subtitulo_periodo': subtitulo_periodo,
        'fecha_desde': fecha_desde.strftime('%Y-%m-%d') if fecha_desde else '',
        'fecha_hasta': fecha_hasta.strftime('%Y-%m-%d') if fecha_hasta else '',
        'fecha_desde_display': fecha_desde.strftime('%d/%m/%Y') if fecha_desde else 'Inicio',
        'fecha_hasta_display': fecha_hasta.strftime('%d/%m/%Y') if fecha_hasta else 'Presente',
        'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M'),

        # Totales Beneficios
        'total_beneficios_count': total_beneficios_count,
        'beneficios_entregados_count': beneficios_entregados_count,
        'beneficios_pendientes_count': beneficios_pendientes_count,
        'articulos_entregados_sum': articulos_entregados_sum,
        'articulos_pendientes_sum': articulos_pendientes_sum,
        'total_articulos_sum': total_articulos_sum,
        'beneficiarios_entregados_count': beneficiarios_entregados_count,
        'beneficiarios_pendientes_count': beneficiarios_pendientes_count,
        'total_beneficiarios_unicos': total_beneficiarios_unicos,
        'tasa_efectividad_entregas': tasa_efectividad_entregas,

        # Totales Solicitudes
        'total_solicitudes_count': total_solicitudes_count,
        'solicitudes_entregadas_count': solicitudes_entregadas_count,
        'solicitudes_pendientes_count': solicitudes_pendientes_count,
        'solicitudes_aprobadas_count': solicitudes_aprobadas_count,
        'solicitudes_en_proceso_count': solicitudes_en_proceso_count,
        'solicitudes_recibidas_count': solicitudes_recibidas_count,
        'solicitudes_rechazadas_count': solicitudes_rechazadas_count,
        'tasa_resolucion_solicitudes': tasa_resolucion_solicitudes,

        # Concatenación Consolidada
        'gran_total_operaciones': gran_total_operaciones,
        'gran_total_entregados': gran_total_entregados,
        'gran_total_pendientes': gran_total_pendientes,
        'tasa_efectividad_global': tasa_efectividad_global,

        # Datos para Gráficos
        'top_insumos': top_insumos_recortado,
        'tipos_solicitudes': tipos_sol_agg,
        'estatus_labels': estatus_labels,
        'estatus_valores': estatus_valores,
        'fechas_labels': fechas_labels,
        'fechas_entregados': fechas_entregados,
        'fechas_pendientes': fechas_pendientes,
        'fechas_solicitudes': fechas_solicitudes,

        # Tablas Detalladas Concatenadas
        'recientes_beneficios': recientes_beneficios,
        'recientes_solicitudes': recientes_solicitudes,
        'registros_unificados': registros_unificados,
        'fecha_desde_iso': fecha_desde.strftime('%Y-%m-%d') if fecha_desde else '',
        'fecha_hasta_iso': fecha_hasta.strftime('%Y-%m-%d') if fecha_hasta else '',

        # Textos Redactados de Análisis
        'analisis_balance': analisis_balance,
        'analisis_demanda': analisis_demanda,
        'analisis_insumos': analisis_insumos,
        'analisis_recomendaciones': analisis_recomendaciones,
    }

@login_required
def modulo_informes_view(request):
    """
    Vista principal interactiva del módulo de Informes en pantalla.
    Maneja filtros de período (diario, semanal, mensual, total y personalizado).
    """
    if not request.user.is_superuser:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and not (perfil.permiso_dashboard or perfil.permiso_estadisticas or perfil.permiso_entregas):
            return redirect(obtener_url_inicio_usuario(request.user))

    periodo = request.GET.get('periodo', 'semanal').strip().lower()
    fecha_esp = request.GET.get('fecha', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '').strip()
    fecha_fin = request.GET.get('fecha_fin', '').strip()

    datos = calcular_datos_informe(
        periodo=periodo,
        fecha_str=fecha_esp,
        fecha_inicio_str=fecha_inicio,
        fecha_fin_str=fecha_fin
    )

    context = {
        'd': datos,
        'datos_json': json.dumps(datos, default=str),
    }

    return render(request, 'informes/panel_informes.html', context)

@login_required
def api_datos_informes(request):
    """
    Endpoint JSON para refresco dinámico de datos y gráficos sin recargar la página.
    """
    periodo = request.GET.get('periodo', 'semanal').strip().lower()
    fecha_esp = request.GET.get('fecha', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '').strip()
    fecha_fin = request.GET.get('fecha_fin', '').strip()

    datos = calcular_datos_informe(
        periodo=periodo,
        fecha_str=fecha_esp,
        fecha_inicio_str=fecha_inicio,
        fecha_fin_str=fecha_fin
    )

    return JsonResponse(datos)

def limpiar_base64_img(val):
    """Limpia cadenas data URI base64 a formato puro sin prefijo."""
    if not val:
        return ''
    if ',' in val:
        val = val.split(',', 1)[1]
    return val.strip().replace(' ', '+')

def obtener_chart_quickchart(qc_config, width=650, height=360):
    """Consulta la API de QuickChart para generar un gráfico en PNG de alta resolución y nitidez."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        params = urllib.parse.urlencode({
            'c': json.dumps(qc_config),
            'w': width,
            'h': height,
            'bkg': 'white',
            'devicePixelRatio': 2.0
        })
        url = f"https://quickchart.io/chart?{params}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (SIA-PDF)'})
        with urllib.request.urlopen(req, timeout=3, context=ctx) as r:
            img_bytes = r.read()
            return base64.b64encode(img_bytes).decode('ascii')
    except Exception:
        return ''

def draw_pil_donut(entregados, pendientes, w=550, h=340):
    """Fallback local con PIL para gráfico tipo dona amplio (Entregados vs Pendientes con cantidades visibles)."""
    try:
        img = Image.new('RGB', (w, h), color='#ffffff')
        d = ImageDraw.Draw(img)
        total = max(entregados + pendientes, 1)
        angle_ent = int((entregados / total) * 360)
        pct_ent = int((entregados / total) * 100)
        pct_pen = int((pendientes / total) * 100)
        
        # Donut amplio y grueso
        d.pieslice([40, 30, 310, 300], start=0, end=angle_ent, fill='#10b981')
        d.pieslice([40, 30, 310, 300], start=angle_ent, end=360, fill='#f59e0b')
        d.ellipse([115, 105, 235, 225], fill='#ffffff')
        
        # Leyenda lateral con cajas de color y números destacados
        d.rectangle([340, 95, 360, 115], fill='#10b981')
        d.text((370, 97), f'Entregados: {entregados} ({pct_ent}%)', fill='#166534')
        
        d.rectangle([340, 150, 360, 170], fill='#f59e0b')
        d.text((370, 152), f'Pendientes: {pendientes} ({pct_pen}%)', fill='#92400e')
        
        d.text((340, 210), f'Total Evaluado: {entregados + pendientes}', fill='#1e293b')
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''

def draw_pil_line(labels, d1, d2, w=650, h=340):
    """Fallback local con PIL para gráfico de líneas de evolución temporal con cantidades legibles."""
    try:
        img = Image.new('RGB', (w, h), color='#ffffff')
        d = ImageDraw.Draw(img)
        d.line([(30, 20), (60, 20)], fill='#10b981', width=4)
        d.text((70, 14), 'Entregados', fill='#1e293b')
        d.line([(180, 20), (210, 20)], fill='#f59e0b', width=4)
        d.text((220, 14), 'Pendientes', fill='#1e293b')
        
        # Eje base horizontal
        d.line([(45, 275), (w-25, 275)], fill='#cbd5e1', width=2)
        
        max_val = max(max(d1 or [1]), max(d2 or [1]), 1)
        n = max(len(labels), 1)
        step = (w - 100) // max(n - 1, 1)
        
        pts1, pts2 = [], []
        for i in range(n):
            x = 55 + i * step
            v1 = d1[i] if i < len(d1) else 0
            v2 = d2[i] if i < len(d2) else 0
            y1 = 275 - int((v1 / max_val) * 200)
            y2 = 275 - int((v2 / max_val) * 200)
            pts1.append((x, y1))
            pts2.append((x, y2))
            
            # Puntos y valores
            if v1 > 0 and n <= 20:
                d.ellipse([x - 4, y1 - 4, x + 4, y1 + 4], fill='#10b981')
                d.text((x - 6, max(y1 - 18, 35)), str(v1), fill='#10b981')
            if v2 > 0 and n <= 20:
                d.ellipse([x - 4, y2 - 4, x + 4, y2 + 4], fill='#f59e0b')
                d.text((x - 6, max(y2 - 18, 35)), str(v2), fill='#f59e0b')
            if i % max(1, n // 6) == 0 and i < len(labels):
                d.text((x - 12, 285), str(labels[i])[:5], fill='#64748b')
                
        if len(pts1) > 1:
            d.line(pts1, fill='#10b981', width=4)
        if len(pts2) > 1:
            d.line(pts2, fill='#f59e0b', width=4)
            
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''

def draw_pil_bars(labels, d1, d2, label1='Entregadas', label2='Pendientes', color1='#10b981', color2='#f59e0b', w=650, h=340):
    """Fallback local con PIL para gráficos de barras comparativas con cantidades visibles."""
    try:
        img = Image.new('RGB', (w, h), color='#ffffff')
        d = ImageDraw.Draw(img)
        d.rectangle([30, 15, 50, 30], fill=color1)
        d.text((58, 17), label1, fill='#1e293b')
        d.rectangle([(w // 2), 15, (w // 2) + 20, 30], fill=color2)
        d.text(((w // 2) + 28, 17), label2, fill='#1e293b')
        
        # Eje horizontal
        d.line([(45, 275), (w-25, 275)], fill='#cbd5e1', width=2)
        
        n = max(len(labels), 1)
        bar_width = max((w - 120) // (n * 2 + 1), 12)
        max_val = max(max(d1 or [1]), max(d2 or [1]), 1)
        
        for i, lab in enumerate(labels[:6]):
            x = 60 + i * (bar_width * 2 + 18)
            v1 = d1[i] if i < len(d1) else 0
            v2 = d2[i] if i < len(d2) else 0
            h1 = int((v1 / max_val) * 200)
            h2 = int((v2 / max_val) * 200)
            d.rectangle([x, 275 - h1, x + bar_width, 275], fill=color1)
            d.rectangle([x + bar_width + 4, 275 - h2, x + bar_width * 2 + 4, 275], fill=color2)
            if v1 > 0:
                d.text((x + 2, max(275 - h1 - 18, 38)), str(v1), fill=color1)
            if v2 > 0:
                d.text((x + bar_width + 6, max(275 - h2 - 18, 38)), str(v2), fill=color2)
            d.text((x, 283), str(lab)[:9], fill='#64748b')
            
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''

def obtener_o_generar_graficos_pdf(request, datos):
    """
    Obtiene las imágenes de los gráficos para el informe PDF con cantidades numéricas explícitas.
    Prioriza las imágenes Base64 generadas en el navegador por Chart.js enviadas vía POST.
    Si no fueron enviadas, genera gráficos con QuickChart o con el motor PIL local como respaldo.
    """
    params = request.POST if request.method == 'POST' else request.GET
    
    chart_evolucion = limpiar_base64_img(params.get('chart_evolucion', ''))
    chart_status = limpiar_base64_img(params.get('chart_status', ''))
    chart_insumos = limpiar_base64_img(params.get('chart_insumos', ''))
    chart_tipos = limpiar_base64_img(params.get('chart_tipos', ''))
    
    # 1. Gráfico de Dona: Distribución de Estatus con Cantidades
    if not chart_status:
        entregados = datos.get('gran_total_entregados', 0)
        pendientes = datos.get('gran_total_pendientes', 0)
        tot = max(entregados + pendientes, 1)
        qc_status = {
            'type': 'doughnut',
            'data': {
                'labels': [f'Entregados: {entregados}', f'Pendientes: {pendientes}'],
                'datasets': [{'data': [entregados, pendientes], 'backgroundColor': ['#10b981', '#f59e0b']}]
            },
            'options': {
                'cutoutPercentage': 50,
                'plugins': {
                    'legend': {'position': 'bottom', 'labels': {'fontSize': 13, 'fontStyle': 'bold'}},
                    'datalabels': {
                        'display': True,
                        'color': '#ffffff',
                        'font': {'weight': 'bold', 'size': 14},
                        'formatter': '(val) => val > 0 ? val + " (" + Math.round(val/' + str(tot) + '*100) + "%)" : ""'
                    }
                }
            }
        }
        chart_status = obtener_chart_quickchart(qc_status, 550, 350) or draw_pil_donut(entregados, pendientes)
        
    # 2. Gráfico de Líneas: Evolución Temporal con Cantidades
    if not chart_evolucion:
        labels = datos.get('fechas_labels', []) or ['Inicio', 'Cierre']
        d_ent = datos.get('fechas_entregados', []) or [0, 0]
        d_pen = datos.get('fechas_pendientes', []) or [0, 0]
        qc_evol = {
            'type': 'line',
            'data': {
                'labels': labels,
                'datasets': [
                    {'label': 'Entregados', 'data': d_ent, 'borderColor': '#10b981', 'backgroundColor': 'rgba(16,185,129,0.15)', 'fill': True, 'borderWidth': 3},
                    {'label': 'Pendientes', 'data': d_pen, 'borderColor': '#f59e0b', 'backgroundColor': 'rgba(245,158,11,0.15)', 'fill': True, 'borderWidth': 3}
                ]
            },
            'options': {
                'plugins': {
                    'legend': {'position': 'top', 'labels': {'fontSize': 12, 'fontStyle': 'bold'}},
                    'datalabels': {'display': True, 'align': 'top', 'anchor': 'end', 'font': {'weight': 'bold', 'size': 12}}
                }
            }
        }
        chart_evolucion = obtener_chart_quickchart(qc_evol, 650, 350) or draw_pil_line(labels, d_ent, d_pen)
        
    # 3. Gráfico de Barras: Top Insumos con Cantidades
    if not chart_insumos:
        top_list = datos.get('top_insumos', [])[:6]
        labels_ins = [item['descripcion'][:15] + ('...' if len(item['descripcion']) > 15 else '') for item in top_list] or ['Sin insumos']
        d_ins_ent = [item['entregadas'] for item in top_list] or [0]
        d_ins_pen = [item['pendientes'] for item in top_list] or [0]
        qc_ins = {
            'type': 'horizontalBar',
            'data': {
                'labels': labels_ins,
                'datasets': [
                    {'label': 'Entregadas (u.)', 'data': d_ins_ent, 'backgroundColor': '#10b981'},
                    {'label': 'Pendientes (u.)', 'data': d_ins_pen, 'backgroundColor': '#f59e0b'}
                ]
            },
            'options': {
                'scales': {'xAxes': [{'stacked': True}], 'yAxes': [{'stacked': True}]},
                'plugins': {
                    'legend': {'position': 'top', 'labels': {'fontSize': 12, 'fontStyle': 'bold'}},
                    'datalabels': {'display': True, 'color': '#ffffff', 'font': {'weight': 'bold', 'size': 12}}
                }
            }
        }
        chart_insumos = obtener_chart_quickchart(qc_ins, 650, 350) or draw_pil_bars(labels_ins, d_ins_ent, d_ins_pen, 'Entregadas', 'Pendientes', '#10b981', '#f59e0b')
        
    # 4. Gráfico de Barras: Tipos de Solicitud con Cantidades
    if not chart_tipos:
        tipos_list = datos.get('tipos_solicitudes', [])[:6]
        labels_tip = [item['tipo_solicitud'][:14] for item in tipos_list] or ['Sin solicitudes']
        d_tip_ent = [item['entregadas'] for item in tipos_list] or [0]
        d_tip_pen = [item['pendientes'] for item in tipos_list] or [0]
        qc_tip = {
            'type': 'bar',
            'data': {
                'labels': labels_tip,
                'datasets': [
                    {'label': 'Completadas', 'data': d_tip_ent, 'backgroundColor': '#4f46e5'},
                    {'label': 'En Proceso', 'data': d_tip_pen, 'backgroundColor': '#06b6d4'}
                ]
            },
            'options': {
                'plugins': {
                    'legend': {'position': 'top', 'labels': {'fontSize': 12, 'fontStyle': 'bold'}},
                    'datalabels': {'display': True, 'align': 'top', 'anchor': 'end', 'font': {'weight': 'bold', 'size': 12}}
                }
            }
        }
        chart_tipos = obtener_chart_quickchart(qc_tip, 650, 350) or draw_pil_bars(labels_tip, d_tip_ent, d_tip_pen, 'Completadas', 'En Proceso', '#4f46e5', '#06b6d4')
        
    return {
        'chart_evolucion': chart_evolucion,
        'chart_status': chart_status,
        'chart_insumos': chart_insumos,
        'chart_tipos': chart_tipos,
    }

@login_required
def generar_informe_pdf_view(request):
    """
    Genera y descarga el archivo PDF oficial del informe de gestión,
    incorporando membrete institucional, análisis redactado, métricas concatenadas,
    representación gráfica visual (Chart.js / QuickChart / PIL) y tabla de auditoría.
    Soporta tanto peticiones GET como POST (para recibir gráficos Base64 del navegador).
    """
    params = request.POST if request.method == 'POST' else request.GET

    periodo = params.get('periodo', 'semanal').strip().lower()
    fecha_esp = params.get('fecha', '').strip()
    fecha_inicio = params.get('fecha_inicio', '').strip()
    fecha_fin = params.get('fecha_fin', '').strip()

    datos = calcular_datos_informe(
        periodo=periodo,
        fecha_str=fecha_esp,
        fecha_inicio_str=fecha_inicio,
        fecha_fin_str=fecha_fin
    )

    logos = obtener_logos_base64()
    firma_digital = generar_hash_firma_digital(f"INFORME_{periodo}_{datos['fecha_desde']}_{datos['fecha_hasta']}_{request.user.username}")
    graficos_b64 = obtener_o_generar_graficos_pdf(request, datos)

    html_string = render_to_string('informes/informe_pdf.html', {
        'd': datos,
        'config': logos['config'],
        'logo_alcaldia_b64': logos['logo_alcaldia'],
        'logo_valera_b64': logos['logo_valera'],
        'usuario_emisor': request.user.username,
        'firma_digital': firma_digital,
        'fecha_emision': datetime.now(),
        # Gráficos integrados en Base64
        'chart_evolucion_b64': graficos_b64['chart_evolucion'],
        'chart_status_b64': graficos_b64['chart_status'],
        'chart_insumos_b64': graficos_b64['chart_insumos'],
        'chart_tipos_b64': graficos_b64['chart_tipos'],
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"Informe_Gestion_{datos['periodo'].capitalize()}_{datos['fecha_desde'] or 'Total'}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html_string, dest=response)
    if pisa_status.err:
        return HttpResponse('Error interno al generar el PDF del Informe', status=500)

    return response
