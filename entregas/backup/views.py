from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
import cloudinary
import cloudinary.uploader
from SIA.models import SIA_producto
from beneficiarios.models import Beneficiario
from entregas.models import BeneficioEntregado
from core.models import AsignacionEspecial, DetalleAsignacionEspecial, RegistroAuditoria
from django.utils import timezone

# Configuración única de Cloudinary (para la gestión de evidencias fotográficas)
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

    productos_bajos = SIA_producto.objects.filter(cantidad__lte=5).values('descripcion', 'cantidad')
     
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

        # Verificar si el beneficiario ya tiene un beneficio registrado
        if BeneficioEntregado.objects.filter(cedula=cedula).exists():
            messages.error(request, "Error: El beneficiario ya tiene un beneficio registrado.")
            return redirect('asignar_beneficio')

        nombre_beneficiario = request.POST.get('nombre_beneficiario')
        direccion = request.POST.get('direccion')
        telefono = request.POST.get('telefono')
        codigo_prod = request.POST.get('codigo_prod') # Código o identificador del producto seleccionado
  
        try:
            cantidad_dada = int(request.POST.get('cantidad_dada', 0))
        except (ValueError, TypeError):
            cantidad_dada = 0

        via = request.POST.get('via')
        status = request.POST.get('status')
        fecha_input = request.POST.get('fecha')
        fecha_a_guardar = fecha_input if fecha_input else date.today()

        # Subida de evidencias a Cloudinary mapeadas a url_evidencia_1 y url_evidencia_2
        url_evidencia_1_str = None
        url_evidencia_2_str = None
  
        if request.FILES.get('evidencia1'):
            resp1 = cloudinary.uploader.upload(request.FILES['evidencia1'])
            url_evidencia_1_str = resp1.get('secure_url')
  
        if request.FILES.get('evidencia2'):
            resp2 = cloudinary.uploader.upload(request.FILES['evidencia2'])
            url_evidencia_2_str = resp2.get('secure_url')

        # Buscar el producto de forma flexible (por código o id)
        producto = None
        try:
            if codigo_prod:
                producto = SIA_producto.objects.filter(Q(codigo=codigo_prod) | Q(id=str(codigo_prod))).first()
            
            if not producto:
                raise SIA_producto.DoesNotExist
        except SIA_producto.DoesNotExist:
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

        # Crear el registro del beneficio entregado en PostgreSQL
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
        lista_inventario = list(SIA_producto.objects.values('id', 'codigo', 'descripcion', 'almacen', 'cantidad'))
        return render(request, 'asignar_beneficio.html', {'inventario': lista_inventario, 'hoy': date.today().strftime("%Y-%m-%d")})

@login_required
def confirmar_entrega(request, entrega_id):
    if request.method == 'POST' and request.FILES.get('evidencia'):
        try:
            respuesta = cloudinary.uploader.upload(request.FILES['evidencia'])
            url_foto = respuesta.get('secure_url')
             
            entrega = BeneficioEntregado.objects.get(id=entrega_id)
             
            if entrega.status == 'Pendiente':
                try:
                    producto = SIA_producto.objects.filter(Q(codigo=entrega.codigo_prod) | Q(id=str(entrega.codigo_prod))).first()
                    if producto:
                        producto.cantidad -= entrega.cantidad_dada
                        producto.save()
                except Exception:
                    pass
             
            if not entrega.url_evidencia_1:
                entrega.url_evidencia_1 = url_foto
            elif not entrega.url_evidencia_2:
                entrega.url_evidencia_2 = url_foto
            else:
                entrega.url_evidencia_2 = url_foto
  
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

        urls = []
        if e.url_evidencia_1:
            urls.append(e.url_evidencia_1)
        if e.url_evidencia_2:
            urls.append(e.url_evidencia_2)

        data = {
            'id': e.id,
            'cedula': e.cedula,
            'nombre_beneficiario': e.nombre_beneficiario,
            'descripcion_prod': e.descripcion_prod,
            'cantidad_dada': e.cantidad_dada,
            'status': e.status,
            'url_evidencia_1': e.url_evidencia_1,
            'url_evidencia_2': e.url_evidencia_2,
            'urls_evidencia': urls,
            'fecha_legible': fecha_legible
        }
  
        if status_filtro == 'Todos' or data['status'] == status_filtro:
            lista_entregas.append(data)
  
    return render(request, 'historial.html', {'entregas': lista_entregas, 'status_actual': status_filtro})

@login_required
def eliminar_entrega(request, entrega_id):
    entrega = get_object_or_404(BeneficioEntregado, id=entrega_id)
  
    if request.method == 'POST':
        reponer_stock = request.POST.get('reponer_stock') == 'on'
  
        if reponer_stock:
            try:
                producto = SIA_producto.objects.get(descripcion=entrega.descripcion_prod)
                producto.cantidad += entrega.cantidad_dada
                producto.save()
                messages.success(request, f"Registro eliminado y stock repuesto: +{entrega.cantidad_dada} unidades sumadas a {producto.descripcion}.")
            except SIA_producto.DoesNotExist:
                messages.warning(request, "El registro se eliminó, pero no se encontró el producto en el inventario para reponer el stock.")
        else:
            messages.success(request, "Registro eliminado exitosamente sin modificar el inventario.")
  
        entrega.delete()
  
    return redirect('historial')

@login_required
def cambiar_estado(request, entrega_id, nuevo_status):
    try:
        entrega = BeneficioEntregado.objects.get(id=entrega_id)
        if entrega.status == 'Pendiente' and nuevo_status == 'Entregado':
            try:
                producto = SIA_producto.objects.filter(Q(codigo=entrega.codigo_prod) | Q(id=str(entrega.codigo_prod))).first()
                if not producto:
                    raise SIA_producto.DoesNotExist
                if producto.cantidad < entrega.cantidad_dada:
                    messages.error(request, f"Stock insuficiente para cambiar a Entregado.")
                    return redirect('historial')
                producto.cantidad -= entrega.cantidad_dada
                producto.save()
            except SIA_producto.DoesNotExist:
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

    if telefono and telefono.strip() != "":
        conflicto = Beneficiario.objects.filter(telefono=telefono).exclude(cedula=cedula).exists()
        if conflicto:
            return JsonResponse({
                'bloqueado': True, 
                'mensaje': 'Este número de teléfono ya tiene un beneficio asignado a otra persona.'
            })

    return JsonResponse({'bloqueado': False})

@login_required
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
            # 1. Crear el registro principal de la asignación especial
            asignacion = AsignacionEspecial.objects.create(
                nombre_receptor=nombre_receptor,
                departamento_o_cargo=departamento_o_cargo,
                registrado_por=request.user
            )

            # 2. Iterar sobre los productos seleccionados, descontar stock y crear los detalles
            for i in range(len(productos_ids)):
                prod_id = productos_ids[i]
                cant_dada = int(cantidades[i])
                
                producto = SIA_producto.objects.get(id=prod_id)
                
                if producto.cantidad >= cant_dada:
                    producto.cantidad -= cant_dada
                    producto.save()
                else:
                    raise Exception(f"Stock insuficiente para el producto {producto.descripcion}")

                # ¡Línea clave faltante! Crear el detalle vinculado a la asignación
                DetalleAsignacionEspecial.objects.create(
                    asignacion=asignacion,
                    descripcion_prod=producto.descripcion,
                    cantidad=cant_dada
                )

            # 3. Registrar en la auditoría
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

    # Al cargar por método GET, enviamos el inventario completo al HTML
    productos = SIA_producto.objects.all()
    return render(request, 'entregas/registrar_asignacion.html', {'productos': productos})

@login_required
def lista_asignaciones_especiales(request):
    asignaciones = AsignacionEspecial.objects.all().order_by('-fecha')
    return render(request, 'entregas/asignaciones_especiales.html', {'asignaciones': asignaciones})

@login_required
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
  
        # Registrar en auditoría
        RegistroAuditoria.objects.create(
            usuario=request.user,
            accion=f"Eliminación de asignación especial #{asignacion.id} de {asignacion.nombre_receptor}",
            modulo="Entregas",
            timestamp=timezone.now()
        )
        
        asignacion.delete()
  
    return redirect('lista_asignaciones_especiales')

@login_required
def imprimir_asignacion_especial(request, pk):
    asignacion = get_object_or_404(AsignacionEspecial, id=pk)
    return render(request, 'entregas/reporte_asignacion_especial.html', {'asignacion': asignacion})
