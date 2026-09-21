from django.contrib import admin
from django.urls import path
from core import views as core_views
from SIA import views as inv_views
from entregas import views as entregas_views
from django.conf import settings
from django.conf.urls.static import static
from .views import vista_usuarios_conectados, api_usuarios_conectados
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', core_views.login_view, name='home'),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    path('inventario/', inv_views.lista_inventario, name='inventario'),
    path('entregar/', entregas_views.registrar_entrega, name='asignar_beneficio'),
    path('historial/', entregas_views.historial_entregas, name='historial'),
    path('buscar-beneficiario/', entregas_views.buscar_beneficiario, name='buscar_beneficiario'),
    path('eliminar/<str:entrega_id>/', entregas_views.eliminar_entrega, name='eliminar_entrega'),
    path('cambiar-estado/<str:entrega_id>/<str:nuevo_status>/', entregas_views.cambiar_estado, name='cambiar_estado'), 
    path('dashboard/', inv_views.dashboard, name='dashboard'),
    path('inventario/registrar/', inv_views.registrar_inventario, name='registrar_inventario'),
    path('verificar-producto/', inv_views.verificar_producto, name='verificar_producto'),
    path('obtener-inventario/', inv_views.obtener_todo_inventario, name='obtener_todo_inventario'),
    path('confirmar_entrega/<str:entrega_id>/', entregas_views.confirmar_entrega, name='confirmar_entrega'),
    path('usuarios/registrar/', core_views.registrar_usuario, name='registrar_usuario'),
    path('reporte-pdf/', inv_views.generar_reporte_inventario_independiente, name='reporte_pdf'),
    path('verificar-beneficio/', entregas_views.verificar_beneficio, name='verificar_beneficio'),
    path('inventario/eliminar/<int:producto_id>/', inv_views.eliminar_producto, name='eliminar_producto'),
    path('usuarios-conectados/', vista_usuarios_conectados, name='usuarios_conectados_view'),
    path('api/usuarios-conectados/', api_usuarios_conectados, name='api_usuarios_conectados'),
    path('asignaciones-especiales/', views.lista_asignaciones_especiales, name='lista_asignaciones_especiales'),
    path('asignaciones-especiales/nueva/', views.registrar_asignacion_especial, name='registrar_asignacion'),
    path('asignaciones-especiales/eliminar/<int:pk>/', views.eliminar_asignacion_especial, name='eliminar_asignacion_especial'),
    path('asignaciones-especiales/imprimir/<int:pk>/', views.imprimir_asignacion_especial, name='imprimir_asignacion_especial'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
