import os
import ssl
import json
import base64
from datetime import date, timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q, Max, Value
from django.db.models.functions import Coalesce, Trim, Cast
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

    # 2. Filtrado y Anotación de Beneficios (entregas.BeneficioEntregado)
    qs_beneficios = BeneficioEntregado.objects.annotate(
        status_clean=Trim('status'),
        fecha_efectiva=Coalesce(
            'fecha_entrega',
            'fecha',
            Cast('timestamp', output_field=models.DateField()),
            Value(hoy),
            output_field=models.DateField()
        )
    )
    if fecha_desde:
        qs_beneficios = qs_beneficios.filter(fecha_efectiva__gte=fecha_desde)
    if fecha_hasta:
        qs_beneficios = qs_beneficios.filter(fecha_efectiva__lte=fecha_hasta)

    # Separación y Concatenación por Estatus de Beneficios
    beneficios_entregados_qs = qs_beneficios.filter(status_clean__iexact='Entregado')
    beneficios_pendientes_qs = qs_beneficios.filter(Q(status_clean__iexact='Pendiente') | Q(status_clean__isnull=True) | ~Q(status_clean__iexact='Entregado'))

    total_beneficios_count = qs_beneficios.count()
    beneficios_entregados_count = beneficios_entregados_qs.count()
    beneficios_pendientes_count = beneficios_pendientes_qs.count()

    articulos_entregados_sum = beneficios_entregados_qs.aggregate(t=Sum('cantidad_dada'))['t'] or 0
    articulos_pendientes_sum = beneficios_pendientes_qs.aggregate(t=Sum('cantidad_dada'))['t'] or 0
    total_articulos_sum = articulos_entregados_sum + articulos_pendientes_sum

    beneficiarios_entregados_count = beneficios_entregados_qs.exclude(cedula__isnull=True).exclude(cedula__exact='').values('cedula').distinct().count()
    beneficiarios_pendientes_count = beneficios_pendientes_qs.exclude(cedula__isnull=True).exclude(cedula__exact='').values('cedula').distinct().count()
    total_beneficiarios_unicos = qs_beneficios.exclude(cedula__isnull=True).exclude(cedula__exact='').values('cedula').distinct().count()

    # 3. Filtrado y Anotación de Solicitudes (core.SolicitudCiudadano)
    qs_solicitudes = SolicitudCiudadano.objects.annotate(
        fecha_efectiva=Cast('fecha_solicitud', output_field=models.DateField())
    )
    if fecha_desde:
        qs_solicitudes = qs_solicitudes.filter(fecha_efectiva__gte=fecha_desde)
    if fecha_hasta:
        qs_solicitudes = qs_solicitudes.filter(fecha_efectiva__lte=fecha_hasta)

    total_solicitudes_count = qs_solicitudes.count()
    solicitudes_entregadas_count = qs_solicitudes.filter(status__iexact='Entregada').count()
    solicitudes_aprobadas_count = qs_solicitudes.filter(status__iexact='Aprobada').count()
    solicitudes_en_proceso_count = qs_solicitudes.filter(status__iexact='En Proceso').count()
    solicitudes_recibidas_count = qs_solicitudes.filter(status__iexact='Recibida').count()
    solicitudes_rechazadas_count = qs_solicitudes.filter(status__iexact='Rechazada').count()

    # Concatenación de solicitudes en trámite/pendientes (Recibida, En Proceso, Aprobada)
    solicitudes_pendientes_count = solicitudes_recibidas_count + solicitudes_en_proceso_count + solicitudes_aprobadas_count

    # 4. Concatenación de Métricas Totales del Sistema
    gran_total_operaciones = total_beneficios_count + total_solicitudes_count
    gran_total_entregados = beneficios_entregados_count + solicitudes_entregadas_count
    gran_total_pendientes = beneficios_pendientes_count + solicitudes_pendientes_count

    tasa_efectividad_entregas = round((beneficios_entregados_count / total_beneficios_count * 100), 1) if total_beneficios_count > 0 else 0
    tasa_resolucion_solicitudes = round((solicitudes_entregadas_count / total_solicitudes_count * 100), 1) if total_solicitudes_count > 0 else 0
    tasa_efectividad_global = round((gran_total_entregados / gran_total_operaciones * 100), 1) if gran_total_operaciones > 0 else 0

    # 5. Agrupaciones para Gráficos
    # A) Insumos Más Entregados vs Pendientes
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

    # B) Tipos de Solicitud Ciudadana
    tipos_sol_agg = list(qs_solicitudes.values('tipo_solicitud').annotate(
        total=Count('id'),
        entregadas=Count('id', filter=Q(status__iexact='Entregada')),
        pendientes=Count('id', filter=Q(status__in=['Recibida', 'En Proceso', 'Aprobada']))
    ).order_by('-total'))

    # C) Distribución de Estados Conciliados
    estatus_labels = ['Completados / Entregados', 'En Espera / Pendientes', 'Rechazados']
    estatus_valores = [gran_total_entregados, gran_total_pendientes, solicitudes_rechazadas_count]

    # D) Serie Temporal (Evolución diaria cronológica de Entregados y Pendientes)
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
            for item in qs_solicitudes.values('fecha_efectiva').annotate(cnt=Count('id'))
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
        fechas_solicitudes = [total_solicitudes_count]

    # 6. Registros Recientes Concatenados para Tablas de Detalle
    recientes_beneficios = list(qs_beneficios.order_by('-id')[:10].values(
        'id', 'nombre_beneficiario', 'cedula', 'descripcion_prod', 'cantidad_dada', 'status_clean', 'fecha_efectiva', 'via'
    ))

    recientes_solicitudes = list(qs_solicitudes.order_by('-fecha_solicitud')[:10].values(
        'id', 'nombre_apellido', 'cedula', 'tipo_solicitud', 'prioridad', 'status', 'fecha_solicitud'
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
            f"En el transcurso del {periodo_nombre.lower()} ({subtitulo_periodo}), se gestionó un volumen consolidado de "
            f"{gran_total_operaciones:,} operaciones institucionales, conformadas por {total_beneficios_count:,} asignaciones directas "
            f"de inventario y {total_solicitudes_count:,} solicitudes formales ingresadas por los ciudadanos. "
            f"Del total de acciones, se consolidaron de manera efectiva {gran_total_entregados:,} beneficios entregados "
            f"(representando una tasa de efectividad y resolución global del {tasa_efectividad_global}%), "
            f"mientras que {gran_total_pendientes:,} requerimientos se encuentran actualmente en estatus pendiente o en proceso de gestión."
        )

    # B) Diagnóstico de Demanda y Necesidades Sociales
    if total_solicitudes_count > 0:
        top_tipo = tipos_sol_agg[0]['tipo_solicitud'] if tipos_sol_agg else 'Ayuda Social'
        cant_top_tipo = tipos_sol_agg[0]['total'] if tipos_sol_agg else 0
        pct_top_tipo = round((cant_top_tipo / total_solicitudes_count) * 100, 1)
        alta_prioridad = qs_solicitudes.filter(prioridad='Alta').count()

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

@login_required
def generar_informe_pdf_view(request):
    """
    Genera y descarga el archivo PDF oficial del informe de gestión,
    incorporando membrete institucional, análisis redactado, métricas concatenadas
    y representación gráfica de distribución.
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

    logos = obtener_logos_base64()
    firma_digital = generar_hash_firma_digital(f"INFORME_{periodo}_{datos['fecha_desde']}_{datos['fecha_hasta']}_{request.user.username}")

    html_string = render_to_string('informes/informe_pdf.html', {
        'd': datos,
        'config': logos['config'],
        'logo_alcaldia_b64': logos['logo_alcaldia'],
        'logo_valera_b64': logos['logo_valera'],
        'usuario_emisor': request.user.username,
        'firma_digital': firma_digital,
        'fecha_emision': datetime.now(),
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"Informe_Gestion_{datos['periodo'].capitalize()}_{datos['fecha_desde'] or 'Total'}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html_string, dest=response)
    if pisa_status.err:
        return HttpResponse('Error interno al generar el PDF del Informe', status=500)

    return response
