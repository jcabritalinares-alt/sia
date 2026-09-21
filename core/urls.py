from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from SIA import views as inv_views
from entregas import views as entregas_views
from beneficiarios import views as beneficiarios_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', core_views.login_view, name='home'),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    
    # Inventario
    path('inventario/', inv_views.lista_inventario, name='inventario'),
    path('inventario/registrar/', inv_views.registrar_inventario, name='registrar_inventario'),
    path('inventario/entradas/', inv_views.lista_entradas_inventario, name='lista_entradas_inventario'),
    path('inventario/entradas/nueva/', inv_views.registrar_entrada_inventario, name='registrar_entrada_inventario'),
    path('inventario/eliminar/<str:producto_id>/', inv_views.eliminar_producto, name='eliminar_producto'),
    path('inventario/exportar-excel/', inv_views.exportar_inventario_excel, name='exportar_inventario_excel'),
    path('inventario/importar-excel/', inv_views.importar_inventario_excel_view, name='importar_inventario_excel'),
    path('inventario/plantilla-excel/', inv_views.descargar_plantilla_excel_view, name='descargar_plantilla_excel'),
    path('inventario/etiquetas/<int:producto_id>/', inv_views.imprimir_etiquetas_producto, name='imprimir_etiquetas_producto'),
    path('inventario/ficha/<int:producto_id>/', inv_views.ficha_producto_view, name='ficha_producto'),
    path('verificar-producto/', inv_views.verificar_producto, name='verificar_producto'),
    path('obtener-inventario/', inv_views.obtener_todo_inventario, name='obtener_todo_inventario'),
    path('reporte-pdf/', inv_views.generar_reporte_inventario_independiente, name='reporte_pdf'),
    path('api/productos/autocompletar/', inv_views.api_buscar_producto_autocomplete, name='api_buscar_producto_autocomplete'),
    path('api/notificaciones/resumen/', inv_views.api_notificaciones_resumen, name='api_notificaciones_resumen'),

    # Entregas
    path('dashboard/', inv_views.dashboard, name='dashboard'),
    path('entregar/', entregas_views.registrar_entrega, name='asignar_beneficio'),
    path('historial/', entregas_views.historial_entregas, name='historial'),
    path('historial/exportar-excel/', entregas_views.exportar_historial_excel, name='exportar_historial_excel'),
    path('reporte-mensual-pdf/', entregas_views.generar_reporte_mensual_pdf, name='generar_reporte_mensual_pdf'),
    path('comprobante/<int:entrega_id>/pdf/', entregas_views.generar_comprobante_pdf, name='generar_comprobante_pdf'),
    path('comprobante/entrega/<int:entrega_id>/', entregas_views.ver_comprobante_entrega_publico, name='ver_comprobante_entrega_publico'),
    path('buscar-beneficiario/', entregas_views.buscar_beneficiario, name='buscar_beneficiario'),
    path('eliminar/<str:entrega_id>/', entregas_views.eliminar_entrega, name='eliminar_entrega'),
    path('entregas/<int:entrega_id>/editar-beneficiario/', entregas_views.editar_beneficiario_entrega, name='editar_beneficiario_entrega'),
    path('cambiar-estado/<str:entrega_id>/<str:nuevo_status>/', entregas_views.cambiar_estado, name='cambiar_estado'), 
    path('confirmar_entrega/<str:entrega_id>/', entregas_views.confirmar_entrega, name='confirmar_entrega'),
    path('verificar-beneficio/', entregas_views.verificar_beneficio, name='verificar_beneficio'),
    path('api/beneficiarios/autocompletar/', entregas_views.api_buscar_beneficiario_autocomplete, name='api_buscar_beneficiario_autocomplete'),
    path('beneficiarios/', beneficiarios_views.consulta_beneficiarios, name='consulta_beneficiarios'),
    path('api/beneficiarios/consultar/', beneficiarios_views.api_consultar_beneficiario_expediente, name='api_consultar_beneficiario_expediente'),
    path('api/beneficiarios/whatsapp-lista/', beneficiarios_views.api_obtener_beneficiarios_whatsapp, name='api_obtener_beneficiarios_whatsapp'),


    # Asignaciones Especiales
    path('asignaciones-especiales/', entregas_views.lista_asignaciones_especiales, name='lista_asignaciones_especiales'),
    path('asignaciones-especiales/nueva/', entregas_views.registrar_asignacion_especial, name='registrar_asignacion'),
    path('asignaciones-especiales/eliminar/<int:pk>/', entregas_views.eliminar_asignacion_especial, name='eliminar_asignacion_especial'),
    path('asignaciones-especiales/imprimir/<int:pk>/', entregas_views.imprimir_asignacion_especial, name='imprimir_asignacion_especial'),

    # Atención al Ciudadano
    path('atencion-ciudadano/', core_views.lista_solicitudes_ciudadano, name='lista_solicitudes_ciudadano'),
    path('atencion-ciudadano/nueva/', core_views.registrar_solicitud_ciudadano, name='registrar_solicitud_ciudadano'),
    path('atencion-ciudadano/exportar-excel/', core_views.exportar_solicitudes_excel, name='exportar_solicitudes_excel'),
    path('atencion-ciudadano/reporte-pdf/', core_views.generar_reporte_solicitudes_pdf, name='generar_reporte_solicitudes_pdf'),
    path('atencion-ciudadano/<int:pk>/estado/', core_views.cambiar_estado_solicitud, name='cambiar_estado_solicitud'),
    path('atencion-ciudadano/<int:pk>/entregar/', core_views.entregar_solicitud_desde_inventario, name='entregar_solicitud_desde_inventario'),
    path('atencion-ciudadano/<int:pk>/eliminar/', core_views.eliminar_solicitud_ciudadano, name='eliminar_solicitud_ciudadano'),
    path('atencion-ciudadano/<int:pk>/imprimir/', core_views.imprimir_comprobante_solicitud, name='imprimir_comprobante_solicitud'),
    path('atencion-ciudadano/<int:solicitud_id>/constancia-pdf/', core_views.generar_constancia_solicitud_pdf, name='generar_constancia_solicitud_pdf'),
    path('ciudadano/<str:cedula>/ficha/', core_views.ficha_ciudadano_360, name='ficha_ciudadano_360'),

    # Estadísticas Avanzadas e Inteligencia Social
    path('estadisticas/', core_views.panel_estadisticas_avanzadas, name='panel_estadisticas_avanzadas'),

    # Nuevas APIs para UX/UI
    path('api/busqueda-global/', core_views.api_busqueda_global, name='api_busqueda_global'),
    path('api/verificar-duplicados/', core_views.api_verificar_duplicados_ciudadano, name='api_verificar_duplicados_ciudadano'),
    path('api/estadisticas-filtradas/', core_views.api_estadisticas_filtradas, name='api_estadisticas_filtradas'),
    path('api/clear-welcome-splash/', core_views.api_clear_welcome_splash, name='api_clear_welcome_splash'),
    path('estadisticas/reporte-parroquias-pdf/', core_views.generar_reporte_parroquias_pdf, name='generar_reporte_parroquias_pdf'),

    # Usuarios y Auditoría
    path('usuarios/registrar/', core_views.registrar_usuario, name='registrar_usuario'),
    path('usuarios/<int:user_id>/cambiar-rol/', core_views.cambiar_rol_usuario, name='cambiar_rol_usuario'),
    path('usuarios/<int:user_id>/cambiar-password/', core_views.cambiar_password_usuario, name='cambiar_password_usuario'),
    path('usuarios/<int:user_id>/actualizar-permisos/', core_views.actualizar_permisos_usuario, name='actualizar_permisos_usuario'),
    path('usuarios/<int:user_id>/alternar-estado/', core_views.alternar_estado_usuario, name='alternar_estado_usuario'),
    path('usuarios-conectados/', core_views.vista_usuarios_conectados, name='usuarios_conectados_view'),
    path('api/usuarios-conectados/', core_views.api_usuarios_conectados, name='api_usuarios_conectados'),
    path('auditoria/', core_views.lista_auditoria, name='lista_auditoria'),
    path('auditoria/exportar-excel/', core_views.exportar_auditoria_excel, name='exportar_auditoria_excel'),

    # Respaldo, Restauración e Identidad Institucional
    path('admin-sistema/institucion/', core_views.configurar_institucion_view, name='configurar_institucion'),
    path('admin-sistema/respaldos/', core_views.gestion_respaldos, name='gestion_respaldos'),
    path('admin-sistema/respaldos/generar/', core_views.generar_respaldo_manual_view, name='generar_respaldo_manual'),
    path('admin-sistema/respaldos/descargar/<str:filename>/', core_views.descargar_respaldo, name='descargar_respaldo'),
    path('admin-sistema/respaldos/restaurar/', core_views.restaurar_respaldo_view, name='restaurar_respaldo'),
    path('admin-sistema/respaldos/eliminar/<str:filename>/', core_views.eliminar_respaldo_view, name='eliminar_respaldo'),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

