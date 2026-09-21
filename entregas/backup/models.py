from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
import cloudinary
import cloudinary.uploader

# Importaciones de los modelos locales en PostgreSQL
from SIA.models import Producto
from beneficiarios.models import Beneficiario
from entregas.models import BeneficioEntregado

# Configuración única de Cloudinary
cloudinary.config(  
    cloud_name = 'tehn5bfb',  
    api_key = '938977265767173',  
    api_secret = '07Fm7ApGJAf7KKJ9z0P4b1TwLBU'  
)

@login_required
def dashboard(request):
    entregas = BeneficioEntregado.objects.all()
    pendientes = entregas.filter(status='Pendiente').count()
    entregados_qs = entregas.filter(status='Entregado')
    entregados = entregados_qs.count()
    
    total_articulos = entregados_qs.aggregate(total=Sum('cantidad_dada'))['total'] or 0
    productos_bajos = Producto.objects.filter(cantidad__lte=5).values('descripcion', 'cantidad')
    
    recientes = BeneficioEntregado.objects.all().order_by('-id')[:5]
    lista_recientes = [{
        'nombre_beneficiario': r.nombre_beneficiario,
        'descripcion_prod': r.descripcion_prod,
        'fecha': r.fecha
    } for r in recientes]
    
    resumen_productos = entregas.values('descripcion_prod').annotate(total_cant=Sum('cantidad_dada'))
    nombres_productos = [item['descripcion_prod'] or 'Desconocido' for item in resumen_productos]
    cantidades_productos = [item['total_cant'] for item in resumen_productos]

    context = {
        'pendientes': pendientes, 
        'entregados': entregados, 
        'total_entregado': total_articulos,
        'alertas': list(productos_bajos), 
        'recientes': lista_recientes,
        'nombres_productos': nombres_productos, 
        'cantidades_productos': cantidades_productos,
    }
    return render(request, 'dashboard.html', context)

@login_required
def registrar_entrega(request):
    if request.method == 'POST':
        cedula = request.POST.get('cedula')

        if BeneficioEntregado.objects.filter(cedula=cedula).exists():
            messages.error(request, "Error: El beneficiario ya tiene un beneficio registrado.")
            return redirect('asignar_beneficio')

        nombre_beneficiario = request.POST.get('nombre_beneficiario')
        direccion = request.POST.get('direccion')
        telefono = request.POST.get('telefono')
        codigo_prod = request.POST.get('codigo_prod')
        
        try:
            cantidad_dada = int(request.POST.get('cantidad_dada', 0))
        except (ValueError, TypeError):
            cantidad_dada = 0

        via = request.POST.get('via')
        status = request.POST.get('status')
        fecha_input = request.POST.get('fecha')
        fecha_a_guardar = fecha_input if fecha_input else date.today()

        # Manejo de ambas evidencias (hasta 2 fotos)
        url_evidencia_1_str = None
        url_evidencia_2_str = None
        
        if request.FILES.get('evidencia1') or request.FILES.get('evidencia'):
            img1 = request.FILES.get('evidencia1') or request.FILES.get('evidencia')
            resp1 = cloudinary.uploader.upload(img1)
            url_evidencia_1_str = resp1.get('secure_url')
            
        if request.FILES.get('evidencia2'):
            resp2 = cloudinary.uploader.upload(request.FILES.get('evidencia2'))
            url_evidencia_2_str = resp2.get('secure_url')

        try:
            producto = Producto.objects.get(id=codigo_prod)
        except Producto.DoesNotExist:
            messages.error(request, "El producto seleccionado no existe.")
            return redirect('asignar_beneficio')
        
        stock_actual = producto.cantidad
        descripcion_prod = producto.descripcion
        
        if status == "Entregado":
            if stock_actual < cantidad_dada:
                messages.error(request, f"Stock insuficiente para {descripcion_prod}. Stock disponible: {stock_actual}")
                return redirect('asignar_beneficio')
            producto.cantidad = stock_actual - cantidad_dada
            producto.save()

        # Guardar o actualizar datos en la tabla Beneficiario
        Beneficiario.objects.update_or_create(
            cedula=cedula,
            defaults={
                'nombre_apellido': nombre_beneficiario,
                'direccion': direccion,
                'telefono': telefono
            }
        )

        # Crear el registro con los dos campos de evidencia
        BeneficioEntregado.objects.create(
            cedula=cedula,
            nombre_beneficiario=nombre_beneficiario,
            codigo_prod=str(codigo_prod),
            descripcion_prod=descripcion_prod,
            cantidad_dada=cantidad_dada,
            via=via,
            fecha=fecha_a_guardar,
            status=status,
            url_evidencia_1=url_evidencia_1_str,
            url_evidencia_2=url_evidencia_2_str
        )

        messages.success(request, "Registro guardado correctamente.")
        return redirect('asignar_beneficio')
    else:
        lista_inventario = list(Producto.objects.values('id', 'codigo', 'descripcion', 'almacen', 'cantidad'))
        return render(request, 'asignar_beneficio.html', {'inventario': lista_inventario, 'hoy': date.today().strftime("%Y-%m-%d")})

@login_required
def confirmar_entrega(request, entrega_id):
    if request.method == 'POST' and request.FILES.get('evidencia'):
        try:
            respuesta = cloudinary.uploader.upload(request.FILES['evidencia'])
            url_foto = respuesta.get('secure_url')
            
            entrega = BeneficioEntregado.objects.get(id=entrega_id)
            
            # Asignar a la ranura vacía disponible (1 o 2)
            if not entrega.url_evidencia_1:
                entrega.url_evidencia_1 = url_foto
            elif not entrega.url_evidencia_2:
                entrega.url_evidencia_2 = url_foto
            
            if entrega.status == 'Pendiente':
                try:
                    producto = Producto.objects.get(id=entrega.codigo_prod)
                    if producto.cantidad >= entrega.cantidad_dada:
                        producto.cantidad -= entrega.cantidad_dada
                        producto.save()
                except Producto.DoesNotExist:
                    pass
                entrega.status = "Entregado"
            
            entrega.save()
            messages.success(request, "Evidencia agregada correctamente.")
        except Exception as e:
            messages.error(request, f"Error al subir evidencia: {str(e)}")
    else:
        messages.error(request, "No se seleccionó ninguna imagen.")
    return redirect('historial')

@login_required
def historial_entregas(request):
    status_filtro = request.GET.get('status', 'Todos')
    entregas = BeneficioEntregado.objects.all().order_by('-id')
    
    lista_entregas = []
    for e in entregas:
        fecha_legible = 'N/A'
        if e.fecha:
            try:
                fecha_legible = e.fecha.strftime('%d/%m/%Y')
            except AttributeError:
                fecha_legible = str(e.fecha)

        data = {
            'id': e.id,
            'cedula': e.cedula,
            'nombre_beneficiario': e.nombre_beneficiario,
            'descripcion_prod': e.descripcion_prod,
            'cantidad_dada': e.cantidad_dada,
            'status': e.status,
            'url_evidencia_1': e.url_evidencia_1,
            'url_evidencia_2': e.url_evidencia_2,
            'fecha_legible': fecha_legible
        }
        
        if status_filtro == 'Todos' or data['status'] == status_filtro:
            lista_entregas.append(data)
            
    return render(request, 'historial.html', {'entregas': lista_entregas, 'status_actual': status_filtro})

@login_required
def eliminar_entrega(request, entrega_id):
    try:
        entrega = BeneficioEntregado.objects.get(id=entrega_id)
        if entrega.status == 'Pendiente':
            entrega.delete()
            messages.success(request, "Registro eliminado correctamente.")
        else:
            messages.error(request, "No se puede eliminar un registro que ya ha sido entregado.")
    except BeneficioEntregado.DoesNotExist:
        messages.error(request, "El registro no existe.")
        
    return redirect('historial')

@login_required
def cambiar_estado(request, entrega_id, nuevo_status):
    try:
        entrega = BeneficioEntregado.objects.get(id=entrega_id)
        if entrega.status == 'Pendiente' and nuevo_status == 'Entregado':
            try:
                producto = Producto.objects.get(id=entrega.codigo_prod)
                if producto.cantidad < entrega.cantidad_dada:
                    messages.error(request, f"Stock insuficiente para cambiar a Entregado.")
                    return redirect('historial')
                producto.cantidad -= entrega.cantidad_dada
                producto.save()
            except Producto.DoesNotExist:
                pass
        entrega.status = nuevo_status
        entrega.save()
        messages.success(request, f"Estado actualizado a {nuevo_status}.")
    except BeneficioEntregado.DoesNotExist:
        messages.error(request, "El registro no existe.")
        
    return redirect('historial')

@login_required
def buscar_beneficiario(request):
    cedula = request.GET.get('cedula', '')
    try:
        beneficiario = Beneficiario.objects.get(cedula=cedula)
        return JsonResponse({
            'cedula': beneficiario.cedula,
            'nombre_apellido': beneficiario.nombre_apellido,
            'direccion': beneficiario.direccion,
            'telefono': beneficiario.telefono
        })
    except Beneficiario.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)

@login_required
def verificar_beneficio(request):
    cedula = request.GET.get('cedula', '')
    telefono = request.GET.get('telefono', '')

    if BeneficioEntregado.objects.filter(cedula=cedula).exists():
        return JsonResponse({'bloqueado': True, 'mensaje': 'Esta cédula ya tiene un beneficio registrado.'})

    return JsonResponse({'bloqueado': False})
