from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.db.models import Sum
from xhtml2pdf import pisa
from SIA.models import SIA_producto
from entregas.models import BeneficioEntregado

@login_required
def dashboard(request):
    if not request.session.get('bienvenida_mostrada', False):
        messages.success(request, f'¡Hola, {request.user.username}! Bienvenido de nuevo.', extra_tags='bienvenida')
        request.session['bienvenida_mostrada'] = True
    
    entregas = BeneficioEntregado.objects.all()
    
    # Métricas principales
    pendientes = entregas.filter(status__iexact='Pendiente').count()
    entregados = entregas.filter(status__iexact='Entregado').count()
    
    # Conteo exacto de registros en la tabla Producto
    total_articulos = SIA_producto.objects.count()

    # Alertas de stock bajo (<= 5)
    productos_bajos = list(SIA_producto.objects.filter(cantidad__lte=5).values('descripcion', 'cantidad'))
    
    # Últimas operaciones ordenadas de forma descendente
    recientes = list(BeneficioEntregado.objects.all().order_by('-id')[:5].values(
        'nombre_beneficiario', 'descripcion_prod', 'fecha'
    ))
    
    # Datos para el gráfico
    resumen_productos = entregas.values('descripcion_prod').annotate(total_cant=Sum('cantidad_dada'))
    nombres_productos = [item['descripcion_prod'] or 'Desconocido' for item in resumen_productos]
    cantidades_productos = [item['total_cant'] for item in resumen_productos]

    context = {
        'pendientes': pendientes,
        'entregados': entregados,
        'total_articulos': total_articulos, 
        'alertas': productos_bajos,
        'recientes': recientes,
        'nombres_productos': nombres_productos,
        'cantidades_productos': cantidades_productos
    }

    return render(request, 'dashboard.html', context)


def generar_reporte_inventario_independiente(request):
    try:
        # 1. Consulta directa a PostgreSQL usando el ORM de Django
        productos = SIA_producto.objects.all().values()
        
        # 2. Convertir el QuerySet a una lista de diccionarios para mantener compatibilidad
        lista_productos = list(productos)
        
        # 3. Renderizar usando la plantilla exclusiva para este reporte
        html = render_to_string('reportes/inventario_pdf.html', {'productos': lista_productos})
        
        # 4. Crear respuesta HTTP para descarga de PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="Reporte_Inventario_Actual.pdf"'
        
        # 5. Generar PDF
        pisa_status = pisa.CreatePDF(html, dest=response)
        
        if pisa_status.err:
            return HttpResponse('Error interno al generar el PDF', status=500)
            
        return response
        
    except Exception as e:
        return HttpResponse(f'Error al generar reporte: {str(e)}', status=500)


@login_required
def lista_inventario(request):
    # Obtener todos los productos desde PostgreSQL
    productos = SIA_producto.objects.all()
    return render(request, 'inventario.html', {'productos': productos})

def registrar_inventario(request):
    if request.method == 'POST':
        codigo = request.POST.get('codigo')
        
        try:
            cantidad_ingresada = int(request.POST.get('cantidad', 0))
        except ValueError:
            cantidad_ingresada = 0

        tipo_ingreso = request.POST.get('tipo_ingreso', 'unidad')
        unidades_por_caja = 1
        
        if tipo_ingreso == 'caja':
            try:
                unidades_por_caja = int(request.POST.get('unidades_por_caja', 1))
            except ValueError:
                unidades_por_caja = 1
            
            nueva_cantidad = cantidad_ingresada * unidades_por_caja
        else:
            nueva_cantidad = cantidad_ingresada
        
        # Buscar o crear el producto asegurando que guarde la presentación seleccionada
        producto, creado = SIA_producto.objects.get_or_create(
            codigo=codigo,
            defaults={
                'descripcion': request.POST.get('descripcion'),
                'almacen': request.POST.get('almacen', 'Principal'),
                'cantidad': nueva_cantidad,
                'tipo_presentacion': tipo_ingreso,
                'unidades_por_empaque': unidades_por_caja
            }
        )
        
        if not creado:
            producto.cantidad += nueva_cantidad
            # Actualizamos también la presentación y empaque si se vuelve a registrar
            producto.tipo_presentacion = tipo_ingreso
            producto.unidades_por_empaque = unidades_por_caja
            producto.save()
            messages.success(request, f"Stock actualizado exitosamente. Total: {producto.cantidad}")
        else:
            messages.success(request, "Producto registrado exitosamente.")
            
        return redirect('inventario')
        
    return render(request, 'registrar_inventario.html')

def verificar_producto(request):
    codigo = request.GET.get('codigo', '')
    try:
        producto = SIA_producto.objects.get(codigo=codigo)
        return JsonResponse({
            'existe': True, 
            'descripcion': producto.descripcion, 
            'almacen': producto.almacen
        })
    except Producto.DoesNotExist:
        return JsonResponse({'existe': False})

def obtener_todo_inventario(request):
    # Consultar todos los registros de PostgreSQL y enviarlos en formato JSON
    productos = list(SIA_producto.objects.values('id', 'codigo', 'descripcion', 'almacen', 'cantidad'))
    return JsonResponse({'productos': productos})

@login_required
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(SIA_producto, codigo=producto_id)
    if request.method == 'POST':
        producto.delete()
        messages.success(request, "Producto eliminado exitosamente del inventario.")
    return redirect('inventario')
