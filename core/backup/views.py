from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.db.models import Sum
from xhtml2pdf import pisa
from SIA.models import SIA_producto
from entregas.models import BeneficioEntregado
from core.utils import registrar_auditoria  # <--- Importación de la utilidad de auditoría
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from .utils import RegistroAuditoria
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, logout
from django.core.cache import cache

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
        
        descripcion_form = request.POST.get('descripcion')
        almacen_form = request.POST.get('almacen', 'Principal')

        # Buscar o crear el producto asegurando que guarde la presentación seleccionada
        producto, creado = SIA_producto.objects.get_or_create(
            codigo=codigo,
            defaults={
                'descripcion': descripcion_form,
                'almacen': almacen_form,
                'cantidad': nueva_cantidad,
                'tipo_presentacion': tipo_ingreso,
                'unidades_por_empaque': unidades_por_caja
            }
        )
        
        if not creado:
            producto.cantidad += nueva_cantidad
            producto.tipo_presentacion = tipo_ingreso
            producto.unidades_por_empaque = unidades_por_caja
            producto.save()
            
            # === REGISTRO DE AUDITORÍA (Actualización de stock) ===
            registrar_auditoria(
                request, 
                f"Se actualizó el stock del producto {producto.codigo} - {producto.descripcion}: +{nueva_cantidad} unidades (Total: {producto.cantidad})", 
                modulo="Inventario"
            )
            
            messages.success(request, f"Stock actualizado exitosamente. Total: {producto.cantidad}")
        else:
            # === REGISTRO DE AUDITORÍA (Creación de producto) ===
            registrar_auditoria(
                request, 
                f"Se registró un nuevo producto en inventario: {producto.codigo} - {producto.descripcion} ({nueva_cantidad} unidades)", 
                modulo="Inventario"
            )
            
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
    except SIA_producto.DoesNotExist:
        return JsonResponse({'existe': False})

def obtener_todo_inventario(request):
    # Consultar todos los registros de PostgreSQL y enviarlos en formato JSON
    productos = list(SIA_producto.objects.values('id', 'codigo', 'descripcion', 'almacen', 'cantidad'))
    return JsonResponse({'productos': productos})

@login_required
def eliminar_producto(request, producto_id):
    print(f"VALOR RECIBIDO EN LA URL: '{producto_id}' (Tipo: {type(producto_id)})") # <--- Línea temporal de depuración
    producto = get_object_or_404(SIA_producto, codigo=producto_id)
    if request.method == 'POST':
        prod_codigo = producto.codigo
        prod_desc = producto.descripcion

        producto.delete()

        registrar_auditoria(
            request, 
            f"Se eliminó el producto del inventario: {prod_codigo} - {prod_desc}", 
            modulo="Inventario"
        )

        messages.success(request, "Producto eliminado exitosamente del inventario.")
    return redirect('inventario')

@staff_member_required
def vista_usuarios_conectados(request):
    return render(request, 'usuarios_conectados.html')

@staff_member_required
def api_usuarios_conectados(request):
    usuarios = User.objects.all().order_by('-last_login')
    data = []
    ahora = datetime.datetime.now()
    
    for u in usuarios:
        cache_key = f'last_seen_{u.id}'
        last_seen = cache.get(cache_key)
        
        en_linea = False
        if last_seen:
            diferencia = (ahora - last_seen).total_seconds()
            if diferencia < 30:
                en_linea = True

        data.append({
            'username': u.username,
            'last_login': u.last_login.strftime('%Y-%m-%d %H:%M:%S') if u.last_login else 'Nunca',
            'is_online': en_linea
        })
        
    return JsonResponse({'usuarios': data})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            
            cache_key = f'last_seen_{user.id}'
            last_seen = cache.get(cache_key)
            
            if last_seen:
                diferencia = (datetime.datetime.now() - last_seen).total_seconds()
                if diferencia < 60:
                    messages.error(request, "Este usuario ya tiene una sesión activa en el sistema. Debe cerrar sesión en el otro dispositivo para poder ingresar.")
                    return render(request, 'login.html', {'form': form})

            login(request, user)
            request.session['bienvenida_mostrada'] = False 
            return redirect('dashboard')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@user_passes_test(lambda u: u.is_superuser)
def registrar_usuario(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado exitosamente.")
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'registrar_usuario.html', {'form': form})

@user_passes_test(lambda u: u.is_superuser)
def lista_auditoria(request):
    # Obtenemos todos los registros de auditoría ordenados del más reciente al más antiguo
    registros = RegistroAuditoria.objects.all().order_by('-fecha_hora') # Cambia '-fecha' por el campo de fecha que tenga tu modelo si difiere
    
    context = {
        'registros': registros
    }
    return render(request, 'core/lista_auditoria.html', context)
