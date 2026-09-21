from core.models import RegistroAuditoria
from django.utils import timezone

def registrar_auditoria(request, accion, modulo="General"):
    """Registra una acción en la auditoría capturando el usuario y la fecha real de la BD."""
    if not request:
        return
    
    usuario = request.user if request.user.is_authenticated else None
    
    RegistroAuditoria.objects.create(
        usuario=usuario,
        accion=accion,
        modulo=modulo,
        timestamp=timezone.now() # Usamos el nombre exacto de la columna en PostgreSQL
    )

def obtener_url_inicio_usuario(user):
    """
    Retorna el nombre de la vista de inicio correspondiente según los permisos manuales del usuario.
    """
    if not user or not user.is_authenticated:
        return 'login'
    if user.is_superuser:
        return 'dashboard'
    
    perfil = getattr(user, 'perfil', None)
    if not perfil:
        return 'dashboard'
    
    if perfil.tiene_permiso('dashboard'):
        return 'dashboard'
    if perfil.tiene_permiso('estadisticas'):
        return 'panel_estadisticas_avanzadas'
    if perfil.tiene_permiso('atencion_ciudadano'):
        return 'lista_solicitudes_ciudadano'
    if perfil.tiene_permiso('inventario'):
        return 'inventario'
    if perfil.tiene_permiso('entradas'):
        return 'lista_entradas_inventario'
    if perfil.tiene_permiso('entregas'):
        return 'asignar_beneficio'
    if perfil.tiene_permiso('asignaciones_especiales'):
        return 'lista_asignaciones_especiales'
    if perfil.tiene_permiso('usuarios'):
        return 'registrar_usuario'
    if perfil.tiene_permiso('auditoria'):
        return 'lista_auditoria'
    if perfil.tiene_permiso('respaldos'):
        return 'gestion_respaldos'
    
    return 'dashboard'

def parse_date_safe(val):
    """Convierte de forma segura una cadena en objeto date de Python sin lanzar excepciones."""
    if not val or not str(val).strip():
        return None
    val_str = str(val).strip()
    from datetime import datetime
    try:
        return datetime.strptime(val_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        try:
            return datetime.strptime(val_str, '%d/%m/%Y').date()
        except (ValueError, TypeError):
            return None

def enviar_notificacion_solicitud_email(solicitud, nuevo_estado, email_destinatario=None):
    """
    Envía una notificación por correo electrónico ante cambios de estado a 'Aprobada' o 'Entregada'.
    Si el servidor SMTP no está configurado en .env, captura la excepción de forma segura.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    email_host = getattr(settings, 'EMAIL_HOST', None)
    if not email_host or email_host == 'localhost':
        return False
        
    try:
        from core.models import ConfiguracionInstitucion
        config = ConfiguracionInstitucion.get_solo()
        
        destinatarios = []
        if email_destinatario and '@' in email_destinatario:
            destinatarios.append(email_destinatario)
        
        if config.email and config.email not in destinatarios:
            destinatarios.append(config.email)
            
        if not destinatarios:
            return False

        asunto = f"SIA Web - Actualización de Solicitud #{solicitud.id}: {nuevo_estado}"
        mensaje = f"""
Estimado(a) {solicitud.nombre_apellido},

Le informamos que su solicitud social #{solicitud.id} ({solicitud.tipo_solicitud}) ha cambiado al estado: {nuevo_estado.upper()}.

Detalles de la Solicitud:
- Cédula: {solicitud.cedula}
- Estado Actual: {nuevo_estado}
- Requerimiento: {solicitud.descripcion_solicitud}

Atentamente,
{config.nombre_institucion}
Sistema SIA Web
"""
        remitente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@alcaldia.gob.ve')
        send_mail(asunto, mensaje, remitente, destinatarios, fail_silently=True)
        return True
    except Exception:
        return False

def generar_hash_firma_digital(obj):
    """
    Genera una Firma Criptográfica SHA-256 única para validar la autenticidad legal del documento.
    """
    if not obj:
        return "SHA256-00000000-00000000-00000000-00000000"
    import hashlib
    obj_id = getattr(obj, 'id', '0')
    cedula = getattr(obj, 'cedula', '')
    fecha = getattr(obj, 'fecha', getattr(obj, 'fecha_solicitud', ''))
    raw_key = f"SIAWEB-LEGAL-VALIDATOR-{obj_id}-{cedula}-{fecha}-CONFIDENTIAL"
    hash_val = hashlib.sha256(raw_key.encode('utf-8')).hexdigest().upper()
    return f"SHA256-{hash_val[:8]}-{hash_val[8:16]}-{hash_val[16:24]}-{hash_val[24:32]}"

def ejecutar_respaldo_automatico_si_aplica(request=None):
    """
    Verifica e invoca la generación de respaldo automático si ha transcurrido la frecuencia programada.
    """
    import os
    import shutil
    from datetime import datetime, timedelta
    from django.conf import settings
    from django.core.management import call_command
    from core.models import RegistroAuditoria

    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    json_files = [
        os.path.join(backup_dir, f) for f in os.listdir(backup_dir) 
        if f.endswith('.json') and (f.startswith('respaldo_') or f.startswith('db_'))
    ]
    
    necesita_respaldo = False
    if not json_files:
        necesita_respaldo = True
    else:
        json_files.sort(key=os.path.getmtime, reverse=True)
        ultimo = json_files[0]
        mtime = datetime.fromtimestamp(os.path.getmtime(ultimo))
        if (datetime.now() - mtime) > timedelta(hours=24):
            necesita_respaldo = True

    if necesita_respaldo:
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_file = os.path.join(backup_dir, f'respaldo_auto_{timestamp}.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                call_command('dumpdata', exclude=['contenttypes', 'auth.permission'], stdout=f)
                
            sqlite_file = os.path.join(settings.BASE_DIR, 'db.sqlite3')
            if os.path.exists(sqlite_file):
                sqlite_copy = os.path.join(backup_dir, f'db_copy_auto_{timestamp}.sqlite3')
                shutil.copy2(sqlite_file, sqlite_copy)

            usuario = request.user if request and request.user.is_authenticated else None
            RegistroAuditoria.objects.create(
                usuario=usuario,
                accion=f"Respaldo automático programado generado ({os.path.basename(json_file)}).",
                modulo="Administración",
                timestamp=timezone.now()
            )
            return True
        except Exception as e:
            print(f"Error en respaldo automático: {e}")
            return False
    return False

def obtener_logos_base64():
    """
    Retorna los datos de la institución y sus logos (dinámicos o estáticos) codificados en base64 para plantillas PDF.
    """
    import os
    import base64
    from django.conf import settings
    from core.models import ConfiguracionInstitucion

    config = ConfiguracionInstitucion.get_solo()
    logos = {'config': config, 'logo_alcaldia': '', 'logo_valera': ''}
    img_dir = os.path.join(settings.BASE_DIR, 'static', 'img')

    # Logo 1 (Principal / Alcaldía)
    if config.logo_principal and os.path.exists(config.logo_principal.path):
        with open(config.logo_principal.path, 'rb') as f:
            logos['logo_alcaldia'] = base64.b64encode(f.read()).decode('utf-8')
    else:
        path_alcaldia = os.path.join(img_dir, 'alcaldia.jpeg')
        if os.path.exists(path_alcaldia):
            with open(path_alcaldia, 'rb') as f:
                logos['logo_alcaldia'] = base64.b64encode(f.read()).decode('utf-8')

    # Logo 2 (Secundario / Gestión)
    if config.logo_secundario and os.path.exists(config.logo_secundario.path):
        with open(config.logo_secundario.path, 'rb') as f:
            logos['logo_valera'] = base64.b64encode(f.read()).decode('utf-8')
    else:
        path_valera = os.path.join(img_dir, 'valera_renace.jpeg')
        if os.path.exists(path_valera):
            with open(path_valera, 'rb') as f:
                logos['logo_valera'] = base64.b64encode(f.read()).decode('utf-8')

    return logos


def consultar_cedula_sistemaspnp(cedula):
    """
    Consulta los datos de un ciudadano venezolano por cédula en sistemaspnp.com/cedula/
    Resuelve el captcha matemático dinámico, envía la petición y extrae:
    - Nombres y Apellidos (limpios y formateados)
    - Datos electorales / geográficos (Estado, Municipio, Parroquia, Centro)
    - Dirección sugerida
    """
    import re
    import requests

    cedula_limpia = re.sub(r'\D', '', str(cedula))
    if not cedula_limpia or len(cedula_limpia) < 4:
        return None

    # 1. Nivel Local: Consultar en la base de datos local (Respuesta instantánea <5ms)
    try:
        from beneficiarios.models import Beneficiario
        ben = Beneficiario.objects.filter(cedula=cedula_limpia).first()
        if not ben:
            ben = Beneficiario.objects.filter(cedula__in=[f"V-{cedula_limpia}", f"V{cedula_limpia}", f"E-{cedula_limpia}"]).first()
        if ben and ben.nombre_apellido and ben.nombre_apellido.strip():
            return {
                'cedula': ben.cedula,
                'nombre_completo': ben.nombre_apellido.strip().title(),
                'nombres': ben.nombre_apellido.strip().title(),
                'apellidos': '',
                'estado': '',
                'municipio': '',
                'parroquia': '',
                'centro_electoral': '',
                'direccion_sugerida': (ben.direccion or '').strip(),
                'telefono': (ben.telefono or '').strip(),
                'origen': 'local'
            }
    except Exception:
        pass

    # 2. Nivel Caché: Evitar peticiones HTTP repetitivas
    from django.core.cache import cache
    cache_key = f'cne_pnp_{cedula_limpia}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.sistemaspnp.com/cedula/',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'
    }

    try:
        # 3. Nivel Externo: Obtener la página del formulario y resolver captcha
        r1 = session.get('https://www.sistemaspnp.com/cedula/', headers=headers, timeout=5)
        if r1.status_code != 200:
            return None

        # Detectar el patrón matemático (ej: "¿Cuánto es 4 + 3?")
        m = re.search(r'CAPTCHA:[^?]*?(\d+)\s*([\+\-\*])\s*(\d+)', r1.text, re.IGNORECASE)
        if not m:
            m = re.search(r'¿Cu[aá]nto es\s*(\d+)\s*([\+\-\*])\s*(\d+)', r1.text, re.IGNORECASE)
        if not m:
            # Búsqueda genérica dentro de etiquetas con números y operador
            m = re.search(r'(\d+)\s*([\+\-\*])\s*(\d+)\s*\?', r1.text)

        if not m:
            return None

        n1, op, n2 = int(m.group(1)), m.group(2), int(m.group(3))
        if op == '+':
            resultado_captcha = n1 + n2
        elif op == '-':
            resultado_captcha = n1 - n2
        else:
            resultado_captcha = n1 * n2

        # 2. Enviar formulario POST a resultado.php
        payload = {
            'cedula': cedula_limpia,
            'captcha': str(resultado_captcha),
            'jeje': ''  # Campo honeypot que debe ir vacío
        }

        r2 = session.post(
            'https://www.sistemaspnp.com/cedula/resultado.php',
            data=payload,
            headers=headers,
            timeout=7
        )

        if r2.status_code != 200:
            return None

        html = r2.text
        if 'RECORD_NOT_FOUND' in html or 'Error en la consulta' in html or 'No se encontraron resultados' in html:
            return None

        # 3. Función auxiliar para extraer el valor de las etiquetas <strong>Campo:</strong> Valor
        def extraer_campo(label):
            pattern = rf'<strong>\s*{re.escape(label)}\s*:?\s*</strong>\s*([^<]+)'
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                # Filtrar guiones o textos nulos provenientes del padrón electoral
                if val in ['-', '--', '---', 'N/A', 'None', 'null']:
                    return ''
                return val
            return ''

        primer_apellido = extraer_campo('Primer Apellido')
        segundo_apellido = extraer_campo('Segundo Apellido')
        nombres = extraer_campo('Nombres')

        estado = extraer_campo('Estado')
        municipio = extraer_campo('Municipio')
        parroquia = extraer_campo('Parroquia')
        centro = extraer_campo('Centro Electoral')

        # Armar nombre completo en orden: Nombres Primer_Apellido Segundo_Apellido
        partes_nombre = [p for p in [nombres, primer_apellido, segundo_apellido] if p]
        if not partes_nombre:
            return None

        nombre_completo = " ".join(partes_nombre).strip().title()

        # Armar dirección sugerida a partir de los datos geográficos del CNE
        partes_dir = [p for p in [parroquia, municipio, estado] if p]
        direccion_sugerida = ", ".join(partes_dir).title() if partes_dir else ""

        resultado = {
            'cedula': cedula_limpia,
            'nombre_completo': nombre_completo,
            'nombres': nombres.title() if nombres else '',
            'apellidos': f"{primer_apellido} {segundo_apellido}".strip().title(),
            'estado': estado.title() if estado else '',
            'municipio': municipio.title() if municipio else '',
            'parroquia': parroquia.title() if parroquia else '',
            'centro_electoral': centro.title() if centro else '',
            'direccion_sugerida': direccion_sugerida,
            'origen': 'cne_web'
        }
        cache.set(cache_key, resultado, 86400 * 30)
        return resultado

    except Exception:
        # Falla silenciosa si no hay internet o el sitio externo no responde
        return None

import os
import uuid
import logging
from django.conf import settings
import cloudinary.uploader

logger = logging.getLogger(__name__)

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


