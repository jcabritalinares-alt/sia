"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from core import views # Las vistas de autenticación core/views.py
from SIA import views as inv_views
from entregas import views as entregas_views # Importamos la nueva app
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # path('inicio/', views.inicio_view, name='inicio'), # Esta la crearemos luego
    path('inventario/', inv_views.lista_inventario, name='inventario'),
    path('entregar/', entregas_views.registrar_entrega, name='asignar_beneficio'),
    path('historial/', entregas_views.historial_entregas, name='historial'),
    path('buscar-beneficiario/', entregas_views.buscar_beneficiario, name='buscar_beneficiario'),
    path('eliminar/<str:entrega_id>/', entregas_views.eliminar_entrega, name='eliminar_entrega'),
    path('cambiar-estado/<str:entrega_id>/<str:nuevo_status>/', entregas_views.cambiar_estado, name='cambiar_estado'), 
    path('dashboard/', entregas_views.dashboard, name='dashboard'),
    path('inventario/registrar/', inv_views.registrar_inventario, name='registrar_inventario'),
    path('verificar-producto/', inv_views.verificar_producto, name='verificar_producto'),
    path('obtener-inventario/', inv_views.obtener_todo_inventario, name='obtener_todo_inventario'),
    path('confirmar_entrega/<str:entrega_id>/', entregas_views.confirmar_entrega, name='confirmar_entrega'),
    path('usuarios/registrar/', views.registrar_usuario, name='registrar_usuario'),
    path('reporte-pdf/', views.generar_pdf_inventario, name='reporte_pdf'),
]
